# X2.10 rvc/ development log: the C library through Qwen on qwenputer's RISC-V core

Development; no gate runs. This is qwenputer plus a program, not a new machine. Written as work proceeds; every number
names its file. Times are ET, 1 Nov 2026.

## Files
- `graphlib.c`: a copy of `cop/graphlib.c`, changed only under `-DBRIDGE`. The diff is `graphlib.diff` (from reading the
  text buffer as flat fields to reading the capture; the §6 wrapping in `main`).
- `box.py`: build, boot and one-call helpers on `bridge.Session` / `ref.Machine`; the capture rule on the Python side.
- `test_m1.py`: the M1 test. `ir_check.py`: the clang firmware on the circuit's IR, no weights.
- `decode.py`: teacher-forced checks on the merged checkpoint. `drive.py`: Qwen free-running, in lockstep.
- `results/`: saved outputs. `mem.log`: memguard's log for every process.

## Decisions
- **Build.** `--ld-path=/opt/homebrew/opt/lld/bin/ld.lld`, as cop does. The brief's `-fuse-ld=ld.lld` is refused by clang
  23.1.4 ("invalid linker name"). Other flags as briefed, plus `-DNO_GRAPH_OPS -DBRIDGE`.
- **Graph.** `cop/boot.py` unchanged: `boot(g, rodata, software=True)` gives the DROM image; the ELF holds no graph data.
- **Parser.** `host/tools.py parse_call` in C: first `<function=...>`, cut at the first `</function>`,
  `<parameter=NAME>(.*?)</parameter>`, one template newline dropped from each side, a repeated parameter's last value
  wins. Spans point into one buffer holding the captured bytes end to end, so there is one copy, not two.
- **Wrapping.** `\n<tool_response>\nRESULT\n</tool_response>\n<think>\n\n</think>\n`, and the bridge echoes HALT as `\n`:
  env/calc's pattern. The bytes SPEC §6 defines are exact.
- **New limit line `TOOLONG`** (proposed for SPEC §3; the machine cannot honour the call, so it says so):
  - a captured row with all 16 bytes set, since a row keeps only a token's first 16 bytes (3.0% of the vocabulary, 7,507
    of 248,070 tokens, are 16 bytes or longer; 626 of them are exactly 16 and are refused too, as the firmware cannot tell);
  - row 80 in use and no `</function>` captured: a call over 80 tokens has lost its middle.
  A call over 80 tokens whose `</function>` is still captured keeps every argument and is answered normally.
- **Setup calls.** A question's `setup` runs on the reference machine before the snapshot, as the host runs it before the
  prompt.

## M1: firmware on the reference machine (done 19:52)
Source hashes: `graphlib.c` 7efccc0e (from `cop/graphlib.c` 461abe99), ELF c46d1607, `lib/reflib.py` 2a406e3e.

**Byte comparison** (`results/m1_full.summary.json`, 346 s, 6 workers, memguard peak 4.64 GiB). A check is one call through
`<tool_call>` .. `</tool_call>` on `bridge.Session` / `ref.Machine`; the whole echo must equal the §6 wrapping around the
host tool's result (`host/tools.py parse_call`, reflib). 60 s alarm per call; none fired.

| Part | Checks | Match | TOOLONG, as predicted | Mismatches | Longest call (tokens) |
|---|---:|---:|---:|---:|---:|
| dev: all data/dev questions, setups, labels (127 graphs) | 29,186 | 29,186 | 0 | 0 | 70 |
| real: every call Qwen wrote in host/out dev1, dev2, dev2-repeat, dev3-clear, its own ids | 1,358 | 1,358 | 0 | 0 | 66 |
| random: cop's generator, 300 graphs, one state per graph | 24,000 | 22,788 | 1,212 | 0 | 171 |
| medium: 150-1,024 nodes, closures, edits | 512 | 497 | 15 | 0 | 163 |
| limits: every SPEC §3 result line, OVERFLOW, 255 / 256 steps, leg bounds, hubs of 1,000, hash collisions, FULL | 332 | 330 | 2 | 0 | 102 |
| framing: 30 malformed or unusual call texts against `parse_call`, plus long tokens and arguments | 33 | 31 | 2 | 0 | 80 |

All ten functions appear (per-function counts in the same file). The test can fail: with 20 edges removed from the machine's
graph, 17 of 100 c024 chases mismatch (`results/m1_probes.json`). No other mutation was tried. `DEGREE` does not occur in the
software build. `COLLIDE` and `PROBE` belong to the dropped E tables.

**The clang build on the circuit's IR** (`results/m1_ir.json`, `results/m1_probes.json`; no weights yet): 0 wrong predictions
and 0 owner mismatches on 120,499 owned positions over 121,545 stream positions (c024, r001, tiny), covering all ten
functions. So clang's output runs exactly at IR level. The merged weights are M2's check.

**What fits** (`results/m1_full.summary.json`, section `fit`, from `cop/boot.py` on the built ELF):
- **ROM:** 33,336 of 262,144 bytes. **DROM rodata:** 460 of 4,096 bytes.
- **RAM:** .bss ends at 23,424 bytes (with the 1,280-byte capture buffer). Lowest stack pointer over the whole run was
  0x7DD0 (560 bytes used; the same file). So 8,784 bytes stay free.
- **DROM image**, largest E that boots at 16-byte labels and 4 relations:

| N | 64 | 128 | 256 | 512 | 768 | 1,024 |
|---|---:|---:|---:|---:|---:|---:|
| max E | 9,726 | 9,577 | 9,278 | 8,681 | 8,084 | 7,486 |

- For scale: N = 500, E = 1,800 takes 48,160 of 131,072 bytes. That is the NYC estimate's order, built from synthetic labels;
  NYC itself was not read.
- **Hard limits of this image:** N ≤ 1,024 (compile-time RAM arrays), R ≤ 64, labels ≤ 64 bytes, 256 added edges (`FULL`,
  measured at exactly 256). At the frontier (N = 1,024, E = 7,486), 7 path / cheapest / close calls equal reflib.
- **Dev graphs:** 127 of 128 fit (largest 128,428 bytes). r097 (928 nodes, 12,503 edges, 54 questions) does not; its
  questions were not run.

**The 80-token capture** (`results/m1_full.summary.json`, section `capture`; template text, `start` = `@123`):
- c024's relation names: every 6-leg chase fits (72-75 tokens), 7 legs sometimes (78-81), 8 or more never.
- A one-letter relation: 11 legs fit (80 tokens); 16 legs take 100. So **SPEC's 16 legs cannot reach the machine with any
  relation name**, and neither can `BADARG legs` at 17. The answer is `TOOLONG`, never a wrong result.
- Qwen's real calls: longest 66 tokens of 1,358; 2-leg chases use about 48. D1's chases fit.
- Widening the window is a circuit change (the docs: its thermometer weights overflow bf16 past 80), not firmware.

**Chip tokens per call**, mean (`results/m1_full.summary.json`, `tokens_per_call`):

| Function | Dev questions | Qwen's real calls | Echoed text tokens (real) |
|---|---:|---:|---:|
| find | 3,315 | 3,033 | 29 |
| follow | 6,200 | 6,342 | 32 |
| chase | 6,093 | 5,546 | 38 |
| neighbours | 4,728 | 6,058 | 23 |
| path | 16,225 | 7,409 | 85 |
| cheapest | 133,087 (max 1,717,803) | 46,713 | 126 |
| close | 2,624 | 2,702 | 31 |
| reopen | 3,012 | not called | |
| link | 6,997 | 8,763 | 62 |
| unlink | 6,150 | 7,191 | 55 |

- An unknown-function call of 23 tokens costs 1,628. Capture and parsing are a large share: each captured byte is a load, a
  4-token byte store (SB) and a scan.
- `cheapest` is the expensive one: real calls take about 47k tokens, and hub graphs reach 1.7M.

**Divergences from the host tool** (`results/m1_probes.json` unless named):
1. A call over 80 tokens, or holding any token of 16 or more bytes: `TOOLONG`, where the host answers. Loud, by design.
2. `FULL` after 256 added edges (overlay); reflib has no bound.
3. `</tool_call>` with no `<tool_call>` in the turn: the bridge re-reads the last capture and answers **the previous call**
   (`@1 Oak` where the host parses the turn and answers `@2 Elm`). This one is silent. It never occurs in the 1,358 real calls
   (`no_tco_call` notes: 0). A fix would need the firmware to know the capture is stale, which it cannot see today.
4. Non-ASCII digits: the host reads `@٣` as 3 (`@3 Ash`); the machine answers `NONE @٣`. Same for steps (`BADARG`).
5. A lone UTF-8 lead byte in an argument: the host prints U+FFFD, the machine the raw byte.
6. The NUL token ends the capture early: machine `BADARG find`, host `NONE Oak\0`.
7. Non-NFC arguments: not exercised. `T.encode` normalises to NFC, so my probe's arguments arrived NFC. The C library still
   does not normalise (cop/DEVLOG); real calls show no case.

Proposed for SPEC (not applied): add `TOOLONG` to §3; state that chase's reachable leg count depends on the capture window.

## M2: merged checkpoint (done 21:30)
- 19:52-20:01. **Merge.** Vendored `chipformer.rv.merge`, unchanged, to `<drive>/Models/x210-rvc/`: 497 s, memguard
  peak 43.12 GiB under the 60 limit (`mem.log`, `results/m2_merge.log`). Hidden 3968, 43 layers (11 chip + 32 Qwen), vocabulary
  484,800, 8 shards totalling 18.8 GB. `fit_anti_sink` ran on the CPU (the merge's own default without CUDA).
- 20:05. **Prompts.** The merged tokenizer gives the host's prompt token for token on all 50 dev2 questions (checked by a
  one-off script, not saved). Transformers warns about a regex on loading it; the check shows no effect on these prompts.
- 20:30. **First teacher run** (`results/m2_teacher_a.json`, `host/test/tiny`, all ten functions, stock modules, sdpa,
  RvChat on MPS): 69,846 positions, 69,300 owned, **0 wrong, 0 fired where not owned, 0 head mismatches**. This is also the
  clang check at circuit level on the merged weights. Peak 20.29 GiB under the 32 limit (MPS driver 18.67). Load 208.6 s.
- **Rates depend on what else runs.** `chip_per_s` 47.68, `text_per_s` 11.45 in that run. The next run dropped to 25.2 / 6.3 and
  20.8 / 5.1 (`results/m2_teacher_b.json`), with another X2.10 stream on the GPU and a game on this Mac (Valheim at 277% CPU,
  seen in `ps` at 20:51). So 47.68 is a measured rate on a shared machine, not a clean ceiling.

**Teacher-forced results, all on stock modules unless named** (MPS, bf16, sdpa, `RvChat(fast=False, executor=False)`, one token
at a time after a prefilled prompt and the injected snapshot; 0 wrong means every owned token equals `bridge.Session`):

| File | Graph, calls | Positions | Owned | Wrong | Fired where not owned | Head mismatch | Chip/s | Text/s |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `results/m2_teacher_a.json` | tiny, all ten functions, 14 calls | 69,846 | 69,300 | 0 | 0 | 0 | 47.68 | 11.45 |
| `results/m2_teacher_b.json` | c024, 3 chases | 16,217 | 16,084 | 0 | 0 | 0 | 25.23 | 6.26 |
| same | c025, 2 chases | 10,650 | 10,560 | 0 | 0 | 0 | 20.80 | 5.14 |
| same | r001: follow, path, neighbours, cheapest | 33,638 | 33,373 | 0 | 0 | 0 | 24.20 | 6.05 |
| `results/m2_teacher_compact.json` | c024 again, **chip layers compacted, not stock** | 16,217 | 16,084 | 0 | 0 | 0 | 39.02 | 5.16 |

- **129,317 owned positions on stock modules, 0 wrong.** That settles the clang question at circuit level for this firmware:
  clang's output runs exactly on the merged weights, as far as these streams reach.
- **Memory:** peak 20.35 GiB under the 32 limit; MPS driver 18.67 GiB (`mem.log`). Load 208-227 s from the LaCie.
- **Rates.** Best stock measurement 47.68 chip tokens/s and 11.45 text tokens/s; the others ran with more on the machine. No
  run had the GPU alone (the CI stream was on MPS throughout, and for parts of them Valheim too; the compact run shared with
  stock r001 for its first 8 minutes). `snapshot_seconds` is 8-22 s per conversation. `prefill_seconds` in these files is not
  usable: MPS is lazy there and the wait lands in the next step.
- **Compaction** (`fast.compact(qwen=False)`, the step RvChat takes itself on CUDA; 1.63B dense chip weights to 185M) is exact on
  that stream. Its gain is not yet measured cleanly: compare with 25.23 / 20.8 under similar load.
- **For the Phase D budget (arithmetic, not a measurement).** Replaying Qwen's own dev2 sdpa calls on the reference gives 24,787
  chip tokens and 408 text tokens per question (`results/m3_forecast_from_host_calls.json`). At 47.68 and 11.45 that is 556 s per
  question. So DESIGN's D2m figure, 37.4M tokens at about 3,118 per chase, needs revising twice: this build's chase is 5,546
  chip tokens (M1), and 66.5M tokens at 47.68/s is about 387 hours. D2m is machine-only, so whether it must run through the
  merged weights rather than the reference is a decision for the lead.

## M3: Qwen drives it
- 21:24-21:52. **Control before the long run** (`wrap_control.py`, `results/wrapctl_bytes_compare.json`): base Qwen, the real host
  tool, no machine, no merged weights, but the response delivered exactly as the circuit delivers it (env/calc's wrapping, one
  byte token at a time). **19/49 correct, 23 at the 12-call cap, against 41/49 and 6 at the cap for the host baseline on the same
  50 questions.** Qwen keeps calling tools inside one assistant turn, and misreads byte-token text (`@3 Eastgate` comes back as
  "Eaasgate" in tiny q0). This is before any machine effect, so it is about delivery, not exactness.
- That also changes the cost: Qwen makes 358 calls instead of 190, so a full merged run would be 3.63M chip tokens
  (`results/m3_forecast_from_control_calls.json`), about 21 hours at 47.68/s. The 1.24M forecast from the host's calls no longer
  applies.
- 21:52-. Stock merged run on tiny q0 (`results/m3_stock/tiny.jsonl`): lock clean, 0 head mismatches, and Qwen's tokens equal the
  control's for the first two segments of three; its answer has the same "Eaasgate" misreading.
- 22:34-23:21. **Which part of delivery does the damage?** Same 50 questions, base Qwen, host tool, no machine
  (`results/wrapctl_*_compare.json`; the host baseline is 41/49, 190 calls, 6 at the cap):

| Response delivered as | Correct | At cap | Calls | Identical to host |
|---|---:|---:|---:|---:|
| circuit wrapping, normal tokens (`wrap`) | 38/49 | 10 | 227 | 13/50 |
| template wrapping, result as byte tokens (`template-bytes`) | 24/49 | 17 | 274 | 3/50 |
| circuit wrapping, byte tokens: what the machine does (`bytes`) | 19/49 | 23 | 358 | 1/50 |
| byte tokens plus `<|im_end|>` / `<|im_start|>` as special tokens (`im-bytes`) | 18/49 | 24 | 349 | 1/50 |

  **Byte tokens are the main cost.** The wrapping costs 3 of 41, byte tokens about 19 more, and adding the two turn tokens gains
  nothing. The floor for "identical" is eager against sdpa, 29/50.
- 22:27-23:52. **Stopped run.** Seven tiny questions on the merged weights, chip layers compacted (`results/m3_compact/tiny.jsonl`,
  `results/m3_sample_compare.json`), chosen from the cheap end of the control's costs, so not representative. Lock clean, 0 head
  mismatches, 100,848 owned positions, all 29 calls equal the host tool. All 7 match the byte control on status, calls and
  score. Stock and compacted agree token for token on the two questions run both ways (`results/m3_stock/tiny.jsonl`).
  Rate 26.65 chip/s and 4.85 text/s with other streams on the GPU. r001 and c024 did not start any question.
- 23:58. **Plan changed by the lead.** Theo set a ceiling of 4 hours for any single planned run, so the full 50-question run (3.63M
  chip tokens) is off. The sample above was stopped; everything saved is kept. Instead: the whole chain on the 17 dev2 chase
  questions (`chain.py`), following `rb/`: `chase` the only tool, rb's added sentence, the first clean machine line is the
  answer, up to 2 retries with the error delivered as the circuit delivers it.
  - **Build:** compacted chip layers. Exact on the c024 teacher run and token-identical to stock on the two questions above;
    every run token is locked to the reference anyway. The firmware's `TOOLONG` counts as an error line (rb's pattern lacks it,
    as the host never prints it).
  - **Budget:** forecast 23 calls × about 6k = about 140k chip tokens; at the lowest measured compact rate, 15.4/s, × 1.5, about 3.8
    hours; `timeout` set to 13,800 s, 2,400 s per question.
  - **Guesses before running (no bar):** first lines about equal rb's one-tool arm, 11/17, since the prompt matches and only the
    arithmetic differs; retries rescue 2-4 of the 6, fewer than rb's normal-token retries, because Qwen misreads bytes. Lock errors: 0.

### The whole chain on the merged weights (done 02:36 on 2 Nov; `results/chain/tally.json`, `results/chain/*.jsonl`, `results/chain.log`)
Compacted chip layers, not stock modules. The 17 dev2 chase questions. The answer is the line the circuit's own tokens spell.

| | Merged, errors as bytes | rb one tool, no retry | rb one tool, retry in normal tokens |
|---|---:|---:|---:|
| Correct | **14/17** | 11/17 | 16/17 |
| Calls | 28 | 17 | 23 |

- **Machine:** 186,333 owned positions, 0 lock errors, 0 head mismatches, and all 28 lines equal the host tool. Longest call 55 tokens.
- **Cost:** 185,386 chip tokens (10,905 a question); 3,388 text tokens (2,441 Qwen's, 947 echoed; 199 a question). The forecast was
  140k chip tokens. 9,440 s over the questions, 555 s each; 9,747 s for the whole process, under the 13,800 s limit. Rates 22.29
  chip/s and 5.12 text/s, on a GPU shared with other streams throughout. Peak 21.51 GiB under the 32 limit (`mem.log`).
- **First lines:** 16 of 17 first calls have the same arguments as rb's one-tool arm. The other is c024 q1, where the merged run
  added "station". 10 first lines are clean and correct; 7 are `NONE`, all from "station".
- **Do retries work when the error arrives as bytes? Partly: 4 of the 7 errors were rescued.** rb's normal-token retries rescued 5 of
  6, on the rb arm's own first errors.
  - Rescued: c024 q1, c024 q201, c025 q1, c025 q100.
  - Stuck, repeating the same call 3 times, ending loud on `NONE`: c024 q101, c025 q0. Normal tokens rescued both of these.
  - **One silent wrong answer:** c025 q200. After `NONE 109 Av station`, Qwen wrote `@109`, a handle made from the name, and the machine
    correctly answered for node 109: `@133 Summit Av-Summit Junction`, gold `@27 37 Av`. The machine was exact on what it was asked.
    The rule "first clean line is the answer" makes this an answer. In rb's normal-token arm this question ended loud (no call).
- **Guesses against results:** first lines 11, got 10. Rescues 2-4 of 6, got 4 of 7. Lock errors 0, got 0.
- 17 questions decide a direction, not a claim. Not reviewed yet, as DESIGN's rules require each round to be.

### Status of M3 as first briefed
**Not run in full.** The 50-question merged run was stopped by the lead's ceiling. What exists on the merged weights: 7 tiny questions in the
normal tool loop, and the 17-question chain above. The 50-question comparison exists only for the no-machine controls.

### Every way the circuit differs from the host tool, as measured
1. **Byte tokens.** Each response byte is one token; the host's text is tokenised normally. Largest effect: `wrap` 38/49 against `bytes` 19/49.
2. **Turn markers.** No `<|im_end|>` / `<|im_start|>`: the bridge cannot print them, so newlines stand in. `host` 41/49 against `wrap` 38/49.
   SPEC §6's own bytes are exact, but the host's stream holds more than §6 states.
3. **`TOOLONG`** on a call over 80 tokens or a token of 16 or more bytes (M1). No real call reached it.
4. **`FULL`** after 256 added edges (M1).
5. **A stale capture.** `</tool_call>` with no `<tool_call>` re-runs the previous call, silently (M1). No real call did this.
6. **Non-ASCII digits, lone UTF-8 bytes, the NUL token** (M1). No real call did these.
7. **Feeding.** Host responses go in as one chunk, circuit echoes one token at a time. Not separated from 1.
8. **Cost.** A response costs thousands of chip tokens, not a host call.

**Decision for the lead:** the machine is exact, and delivery is what loses the answers. `core.py` already has an any-print that puts a token out
by its 18-bit id, in the store build (`--store`); the putchar path has none. Normal-token echo would be a circuit change plus
tokenising labels at boot, so I have not attempted it. The printout route avoids reading and needs an answer to the `@109` case.

### Follow-up chain: told sentence and handle rule (registered 02:39 on 2 Nov, before running; lead's request)
Same 17 questions, same firmware (ELF c46d1607), results in `results/chain2/`. Saved results stay as they are. Two general changes:
1. **Told.** `rb/delivery.py`'s `TOLD` sentence goes after rb's `EXTRA` in the system prompt.
2. **Handle rule.** The `chase` tool's description gains: "Use a handle in start only if a tool response has already printed it;
   otherwise give the node's exact name." It is enforced in the **runner, not the firmware**: a `start` beginning with `@` whose handle
   the machine has not printed earlier in this conversation gets the line `NONE <start>`, delivered as the circuit's byte tokens,
   and goes back like any other error. **For those calls the machine does not run and no chip tokens are spent.** Firmware would have to
   hold the rule later.

**One conflict with the rule's premise.** r001 q17 reads "Start at @6 (Tunrorku)", so a handle can come from the question and is not always
invented. The rule as asked rejects it. I run it as asked and, if q17 is rejected, add one labelled extra record of q17 allowing handles
named in the question.

**Runs on** `exec/` (`ExecChat`, engine 69df37e88e2c, unchanged) through my own loop, as `exec/drive.py`'s flow has no retries or runner
line. Lock against `bridge.Session` stays on. A stock-and-executor sample, every position compared bit for bit, is fixed now as c024 q1 and
c025 q200, the two that exercised retries and the invented handle last time. A runner line follows `</tool_call>` with no GO, which only
prompts have done so far, so it is first checked on the IR.

**Budget:** about 190k chip tokens, 4k text tokens, 17 questions. From 5.1 text/s and the executor's 42-95 s per question, plus the stock sample
at 22 chip/s, about 40 minutes; × 1.5 gives `timeout` 3,600 s, with 1,200 s per question.

**Guesses (no bar):** correct 14-16 of 17. Rescued about 5 of the errors, up from 4 of 7. Silent wrong answers 0-1. Rule fires on 1-3 calls.
r001 q17 most likely writes the name, because of the description. Lock errors 0.

**Result (03:26; `results/chain2/tally.json`, `results/chain2/*.jsonl`, `results/chain2.log`, `results/chain2_ir.json`). It went backwards: 9/17, against 14/17 without these changes.**
- **Ran on:** `exec/` engine 69df37e88e2c for the chip side; prefill and Qwen's layers stock on MPS. Firmware unchanged.
- **Correct:** 9/17; 17 calls (16 by the machine, 1 runner line). All 9 are clean first lines.
- **Retries rescued: 0 of 8.** No question reached a second call. After an error Qwen writes prose ("The tool response indicates...") until the
  768-token turn budget: all 8 errors end `no_call`, with the error line as the final answer. So Qwen reads the bytes better but stops calling.
- **Silent wrong answers: 0**, only because no retry happened. The handle rule **never met an invented handle**: c025 q200 stopped at
  `NONE 109 Av station`, so `@109` was never written. So the rule is untested on its target.
- **Its one firing was a false rejection,** the conflict registered above: r001 q17, `NONE @6`, a handle the question gives. Qwen wrote `@6`
  despite the description. Labelled extra allowing question handles (`results/chain2_q17_question_handles/`): q17 correct, `@2 Murbol`, which would make 10/17.
- **Machine:** 0 lock errors, 0 head mismatches, 109,244 owned positions, all 16 machine lines equal the host tool. The runner line is clean: IR
  check 0 wrong on 10,755 owned positions with two runner lines between machine calls, owner never fired on it. But in the real run no machine call
  followed a runner line, so only the IR tests that.
- **Stock sample:** c024 q1 and c025 q200, stock and executor together, 12,739 positions bit-equal over the whole residual, end states equal.
- **Tokens:** 108,740 chip, 6,972 Qwen, 504 echoed, 19 runner line.
- **Wall:** 2,612 s for the process, 2,306 s over questions. Clean executor questions take 20-26 s (555 s average in the stock-free compacted run before);
  a question that hits the budget takes 140-170 s; the two lockstep ones 500-672 s. Peak 20.30 GiB. Text is now nearly all the time: chip 33.6 s against text 1,025 s,
  about 4,270 chip tokens/s on the executor questions.
- **First lines:** 15 of 17 first calls as in the earlier chain. c025 q0 dropped "station" (now correct), c025 q201 added it (now wrong). So 9 here, 10 there, is one question's noise.
- **Guesses against results:** correct 14-16, got 9. Rescued about 5, got 0. Silent wrong 0-1, got 0. Rule fires 1-3, got 1. q17 writes the name: no, wrote `@6`. Lock errors 0, got 0.
- **Not separated:** told and the rule changed together. Told is the likely cause of the prose, as rb's told arm also hit budgets (4 of 50), but this run cannot show it. 17 questions decide a direction, not a claim.

### Separating the two changes (registered 03:35 on 2 Nov, before running; lead's request)
Two labelled arms, same 17 questions, same firmware, `exec/` engine, stock-and-executor lockstep on c024 q1 only (fixed now).
- **Rule only** (`results/arm_rule/`): no told sentence. The rule is corrected: a handle in the question's text is allowed. The description has to say the same,
  so it reads "only if the question gives it or a tool response has already printed it". That is the only wording change.
- **Told only** (`results/arm_told/`): told sentence, no rule in description or runner.

Compared with the 14/17 run (neither change, compacted stock path) and the 9/17 run (both).

**Budget:** 2,612 s for the last run; × 1.5 gives 3,900 s, set to 3,600 s each as the rule-only arm should be shorter. Two arms in sequence, under Theo's 4 hours.

**Guesses (no bar):**
- Told causes the prose: told only about 9-10/17, most errors ending `no_call`.
- Rule only about 14/17, retries like the 14/17 run, rescuing about 4; the rule fires on 0-2 calls and turns `@109` into a loud `NONE`, so silent wrong 0.

**Result (04:37; `results/arm_rule/tally.json`, `results/arm_told/tally.json`, logs beside them). Both guesses were wrong: told is not what hurts, the rule's description is.**

| Arm | Correct | Calls | Clean, correct first lines | First-line errors | Rescued | Silent wrong | Chip | Qwen | Echo | Seconds over questions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Neither (`results/chain/`, compacted stock path) | 14/17 | 28 | 10 | 7 | 4 | 1 | 185,386 | 2,441 | 947 | 9,440 |
| Both (`results/chain2/`) | 9/17 | 17 | 9 | 8 | 0 | 0 | 108,740 | 6,972 | 504 | 2,306 |
| Rule only | 9/17 | 26 | 5 | 12 | 4 | 0 | 167,321 | 6,827 | 860 | 2,517 |
| Told only | 14/17 | 17 | 14 | 3 | 0 | 0 | 117,101 | 3,128 | 485 | 844 |

- **The rule-only count is held down by my own limit.** c024 q1 ran on the lockstep path and hit the 1,200 s question limit during its third call (status `walltime`, scored wrong).
  Its third call was right. A labelled executor rerun, `results/arm_rule_q1_executor/`, is correct on the same three starts. So read rule only as 10/17, 5 rescued of 12. The table keeps what the run recorded.
- **After an error, rule only:** mixed. Six questions write prose to the 768-token budget (one misreads the bytes, "`NOON 14 St`"); others repeat the same `station` call, and 5 correct it. One gave up on three identical calls.
- **After an error, told only:** all 3 write prose to the budget and never call again. They read the line correctly and describe the fix ("with \"109 Av\" as the") without making the call.
- **What each change does.** The rule's description raises first-line errors from 7 to 12: telling Qwen to give "the node's exact name" seems to produce more "station". Told lowers them to 3, without a word about names, and cost it all retries.
  Why told helps the first line, before any byte is read, is not known.
- **Handle rule:** fired 0 times in rule only. No question wrote an invented handle, so its enforcement is still untested on its target. Silent wrong 0 here is not the rule's doing.
- **Told only has no silent wrong answer and needs no retry to reach 14**, on fewer tokens than the 14/17 run: 3 loud failures. On 17 questions that is a direction, not a claim; the same 14 are not the same questions, and the neither run was on the compacted path.
- **Machine:** 0 lock errors, 0 head mismatches in both arms; 17,522 + 5,993 stock positions bit-equal, end states equal. One machine line of rule only is missing because of the walltime stop. Process wall 2,668 s and 1,304 s; peak 20.29 GiB.
- **Guesses against results:** told only 9-10, got 14. Rule only about 14, got 9 (10 with the rerun). Rescues about 4, got 4-5. Rule fires 0-2, got 0.

### The told-only chain on 100 new dev questions (registered 06:25 on 2 Nov, before running; lead's request)
**Setup:** `TOLD` sentence, no handle rule or rule wording, `chase` only, up to 2 retries as in `results/arm_told/`. Firmware `fw/build/fw.elf` e908647b, read only. Chip side on `exec/`'s engine 69df37e88e2c; prefill and Qwen's layers stock on MPS. Lock against `bridge.Session` on.
**Draw** (`results/chain3_draw.json`, sha256 701a642e, `chain3_draw.py`): seed 20261102, 70 from `data/dev/cities` and 30 from `data/dev/random`, uniform within each. Stratified because a uniform draw over the pool (11,188 and 676) would give only about 6 random. Not the 13 of the 17 that are in `data/dev`; r097 left out, it does not fit. Nothing from `data/heldout/`. Before any model loaded, every canonical call on this firmware equals reflib and the gold line (0 of 100 differ); 316,975 chip tokens at one call each.
**Stock sample,** fixed by the draw as the first city and first random question: `cities/c006` q192, `random/r051` q21. Stock and executor together, every position compared.
**Questions whose gold is a limit line.** 12 random questions have `END`, `MULTI` or `NOCHANGE` as the true answer. The retry rule treats those as errors and retries them anyway, and the last line is the answer. Unchanged here, as in the arm; reported apart, with any first-correct answer lost by a retry.
**Outcomes:** correct by `host/score.py`, first-attempt correct, loud (an error line or no line at the end), silent (a clean line that scores wrong). Correct answers whose line is not the canonical line are counted, as the scorer takes a label anywhere in the line. Failure kinds by first error word, or for silent by wrong start or legs.
**Deadline:** the told-only arm's executor questions averaged 37 s (593 s over 16, `results/arm_told/tally.json`). Add up to 20 s for rebuilding the snapshot tables when the graph changes on most questions here (measured 8-22 s, `results/m2_teacher_*.json`): 57 s × 100 × 1.5 = 8,550 s. Stock sample: 671 s each, the slowest told lockstep question, × 2 × 1.5 = 2,013 s. Load 300 s × 1.5 = 450 s. Total **11,000 s, about 3.06 hours**, set in `timeout`; 1,800 s per question. Under Theo's 4 hours.
**Guesses (no bar):** correct 62-78 of 100; cities higher than random, as random graphs have invented names, several legs and limit cases. First-attempt correct about the same as final, a little lower. Silent 3-10, mostly wrong legs. Rescued under 10% of errors, as told's retries wrote prose: 0 of 3 last time. Lock errors 0.

**Result (07:41; `results/chain3/tally.json`, `results/chain3/all.jsonl`, `results/chain3.log`): 77 of 100 correct, 0 silent, 23 loud, 0 lock errors.**
- **Correct:** 77 by `host/score.py`, each one exactly the canonical line. **First attempt:** 73. **Random 30/30; cities 47/70.** So the guess that cities would do better was backwards.
- **Loud 23, silent 0.** Every failure is the same thing: `NONE` on a start with " station" added (`results/chain3/all.jsonl`), 14 of them then writing prose to the 768-token budget, 2 ending in a short prose answer that the flow does not use ("The station name is NONE."), and 7 repeating the same call until the retries ran out. No wrong clean line in 100.
- **Retries rescued 4** of the 27 first lines that were wrong. Another 16 first lines were limit lines that are the true answer (`END`, `MULTI`, `NOCHANGE`); the rule retried those for nothing, and none was lost.
- **Calls** 124; all 124 machine lines equal the host tool. **Lock errors 0, head mismatches 0,** 420,525 owned positions.
- **Tokens:** 415,894 chip (4,159 a question); 23,962 Qwen; 4,631 echoed.
- **Wall:** 4,594 s for the process against the 11,000 s deadline; 4,136 s over questions; load 452 s. Chip 43.8 s against text 2,784 s, so the machine is about 1% of the time. Peak 20.31 GiB.
- **Stock sample:** `cities/c006` q192 and `random/r051` q21, 15,244 positions bit-equal, end states equal.
- **Guesses against results:** correct 62-78, got 77. Cities higher, got the reverse. Silent 3-10, got 0. Rescued under 10% of errors, got 4 of 27 (15%). Lock errors 0, got 0.
- **What this is and isn't.** Development data on the dev cities, one call per question plus retries, with the machine's line as the answer and the told sentence. The cities' "X station" wording is what fails, on 23 of 70. Not reviewed. Not a gate.

### Can retries rescue the " station" misses? (registered 07:45 on 2 Nov, before anything runs; lead's request. Development, not reviewed)
**Setup unchanged from chain3:** `TOLD`, no rule, `chase` only, up to 2 retries, firmware e908647b, engine 69df37e88e2c, first attempt untouched. `chain4.py`.

**Step 1, on chain3's 27 wrong first lines** (all `NONE`, all " station" added). Each first attempt is regenerated, not skipped, and its tokens compared with chain3's (`first_same`), which is how I show it is unchanged. Four arms:

| Arm | Retry turn | Note |
|---|---|---|
| `prefill` | starts with `<tool_call>`, so it cannot open with prose | none |
| `note` | as before | "No node has exactly that name; call again with only the node's name, without any word that just describes it." |
| `both` | prefilled | the same note |
| `both_q` | prefilled | "No node has exactly that name; use the name as written in the question." |

- **Why two notes.** `both_q` is the wording asked for. The city questions all say "Start at X station", so "as written in the question" points at the miss. I think it will do worse, and it is cheap to measure.
- **Stays general:** no line names, nothing stripped in runner or firmware, the machine is asked exactly what Qwen wrote. The note is fixed text whatever the name is.
- **Where the note lives.** Firmware is read-only, so the runner prints it after the machine's echo, in byte tokens, then `\n\n`. It therefore follows `</think>`, where a firmware version could print it inside the response, so the placement is not what a machine would do. The prefill is also the runner's. Both go to the lock as history; machine tokens stay locked. `ir_check` first, on the same pattern.
- **Limit lines unchanged.** Prefill applies after a query error (`NONE`, `NORELATION`, `AMBIGUOUS`, `BADARG`, `NOFUNCTION`, `TOOLONG`), the note after `NONE` only. `END`, `MULTI`, `NOCHANGE` and other result lines keep chain3's flow, since forcing another call there could turn a true answer into a wrong one. Their retries are reported.
- **Stock sample in step 1:** arm `both`, on the first of the 27 (`cities/c006` q192), to exercise the runner's tokens on stock.

**Choosing the best arm, fixed now:** highest (correct − 3 × silent wrong) of 27; ties go to fewer calls. A silent wrong answer costs three correct ones, since it is the failure this machine exists to avoid.

**Step 2, the honest number:** the best arm on a fresh draw of 100 dev chase questions (`chain3_draw.py`'s method, new seed 20261103, 70 cities and 30 random, excluding chain3's 100 and the 13 of the 17 in `data/dev`), with a stock sample of 2 fixed by the draw. Reported beside chain3's 77. Step 1 is selected on failures, so its numbers are not the result. Its budget is registered from step 1's measured rate before it runs.

**Budget for step 1:** chain3's 26 executor questions among the 27 averaged 66.7 s (`results/chain3/all.jsonl`): 66.7 × 27 × 1.5 = 2,700 s; load 452 × 1.5 = 680 s; so **3,400 s per arm**, plus 910 s (606 s × 1.5) for `both`'s stock question: **4,300 s**. 1,800 s per question. Each arm is its own process; none near 4 hours; about 4.3 hours at most in sequence.

**Guesses (no bar):**
- `prefill`: rescues 8-14 of 27, mostly by repeating the same call less than prose would suggest, but many still repeat " station"; silent 0-2.
- `note`: 8-15 of 27, with some prose left; silent 0-1.
- `both`: 14-22 of 27; silent 0-3. Best arm.
- `both_q`: 5-12 of 27; repeats " station" most.
- Fresh draw: 80-88 of 100, silent 0-3, with first-attempt correct about 73 as first attempts are untouched. Lock errors 0 everywhere. Limit-line retries still gain nothing.

**Step 1 result (09:58; development, not reviewed; on failures, so not the result).** Scored by `chain4_report.py` over saved rows. `results/chain4/<arm>/tally.json`, `report.json`, `results/chain4_<arm>.log`. First attempts identical to chain3's in every row (`first_attempt_same_as_chain3`). IR check of the pattern: 0 wrong on 6,219 owned positions (`results/chain4_ir.json`).

| On the 27 wrong first lines | Rescued | Silent | Limit on wrong query | Loud | Calls | After the first error | Chip | Qwen | Seconds | Rows sha256 |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| chain3 as it was (same questions) | 4 | 0 | 0 | 23 | 45 | prose or repeats | 119,190 | 14,457 | 2,342 | 8fa39238 (all 100) |
| `prefill` | 0 | 0 | 0 | 27 | 81 | **27 repeat the same start** | 212,394 | 3,822 | 870 | 569087c4 |
| `note` (**22 of 27: deadline**) | 3 | 0 | 0 | 19 | 29 | 17 prose to budget, 4 changed, 1 repeated | 78,633 | 15,127 | 2,761 | ddbb4f3f |
| **`both`** | **19** | 0 | 0 | 8 | 62 | **19 changed the start, 8 repeated it** | 174,360 | 2,911 | 1,840 | 4cc028cd |
| `both_q` | 0 | 0 | 0 | 27 | 81 | 27 repeat the same start | 212,394 | 3,822 | 992 | 4048fdaf |

- **Neither half works alone.** Prefill stops the prose but Qwen copies its call; the note gets read but Qwen writes prose. Together: 19 of 27.
- **The wording asked for, `both_q`, rescued none.** "As written in the question" points at the name with " station", as I feared.
- **All 19 are the right node with the word removed**, same legs in all 27. The 8 misses repeat " station". Those are loud, with no silent wrong and no limit line on a wrong query, in any arm.
- **`note` hit its deadline** at 3,400 s with 22 done: the budget used chain3's mean, and prose runs 146 s a question. Kept as is; not raised. The 5 unrun can't change the pick, since at most 8 of 27.
- **Machine:** 0 lock errors, 0 head mismatches, 0 fired on runner tokens in all four. Stock sample, `both` on `cities/c006` q192: 8,731 positions bit-equal, end states equal.
- **Guesses against results:** `prefill` 8-14, got 0. `note` 8-15, got 3 of 22. `both` 14-22, got 19. `both_q` 5-12, got 0. Silent 0-3, got 0.
- **The pick, by the registered rule (correct − 3 × silent): `both`,** at 19. If limit lines on a wrong query counted as silent, it would still pick `both`; there were none here.
- **Reported as the reviews asked,** recomputed on chain3 (rows 8fa39238): 77 correct, limit on wrong query 0, silent 0, loud 23. Qwen's own text: right 5, misread 4 ("@9 (Mosiin)", "Dorbiu" on right lines; "**NORTH**", "NONE" on `NONE` lines), none 91 (71 stopped by the runner at the line, 20 cut at budget).
- **`*.jsonl` is ignored by git,** so the SHA-256 of each `all.jsonl` is in `report.json` and above. Earlier registrations reached git with their results; from here each goes first, in its own commit.
- **What this is not.** The note and prefill are the runner's, not the firmware's. And the note says to drop a word that describes the node: general wording, but written after seeing these failures. A fresh test can only lower it.

### Step 2, the honest number: registration and budget (09:58 on 2 Nov; committed before the run, in its own commit)
**Arm:** `both`, by the rule registered above. `chain4.py --arm both --questions results/chain4_draw.json --readback 96`.
**Draw** (`results/chain4_draw.json`, sha256 c170999d, `chain4_draw.py`, already done, CPU only): seed 20261103, 70 cities and 30 random; none of chain3's 100 (checked, 0 overlap), none of the 13 of the 17 in `data/dev`, no r097, nothing from `data/heldout/`. Canonical calls on this firmware: 0 of 100 differ from reflib and gold; 312,440 chip tokens. 16 random questions have a limit line as gold. Stock sample fixed by the draw: `cities/c006` q288, `random/r067` q21.
**Unchanged:** firmware e908647b, engine 69df37e88e2c, told sentence, first attempt, retries on limit lines in chain3's flow (no prefill, no note). No name-reading rule in runner or firmware.
**Added, not changing the graded answer:** after the graded line Qwen may write up to 96 more tokens, kept apart (`readback_text`), scored right, misread or none. Stops at a stop token, at `<tool_call>` or at the cap. Chain3's saved rows have this only where Qwen happened to write, so the columns are not the same measure.
**Report:** beside chain3's 77 and its 73 first-attempt; correct, first-attempt, rescued, **silent wrong and limit line on a wrong query side by side**, loud, calls, tokens, wall, lock errors, failure kinds, Qwen's own text. No baseline arm ran on this draw, so the difference from 77 mixes the two samples; the first-attempt count shows the samples, and rescued shows the arm.
**Deadline:** chain3's mean 33.2 s a question (`results/chain3/tally.json`, executor) × 100 × 1.5 = 4,980 s. `both` is no slower: 32.6 s on the 27. Readback 96 tokens at the lowest 5 text/s, 19 s × 100 × 1.5 = 2,880 s. Stock sample 993 s (`both`'s q192) × 2 × 1.5 = 2,980 s. Load 587 s × 1.5 = 880 s. **Total 11,700 s, 3.25 hours,** in `timeout`; 1,800 s per question. Not raised if it hits; rows saved are kept.
**Guess, updated after step 1 (the 80-88 registered before step 1 stands beside it):** correct 85-93, as first-attempt 70-76 plus about two thirds of the wrong first lines, less for fitting on failures. Silent 0-3 and limit on wrong query 0-2: the retries now change the call, which reopens the `@109` route. Qwen's own text: misread on 10-25% of finished statements. Lock errors 0.

**Step 2 result (10:56; development, not reviewed). `both` on 100 fresh dev chases: 94 correct, 0 silent, 0 limit lines on a wrong query, 6 loud.** `results/chain4_fresh/tally.json`, `report.json`, `results/chain4_fresh.log`; rows `all.jsonl` sha256 1dbb6bff. `results/chain4_fresh/meta.json` holds the setup. Machine tokens on `exec/`; the note and prefill are the runner's.

| | chain3 (seed 20261102) | `both` (seed 20261103, fresh) |
|---|---:|---:|
| Correct, all exactly the canonical line | 77 | **94** (Wilson 87.5-97.2) |
| First-attempt correct | 73 | 73 |
| Rescued, of wrong first lines | 4 of 27 | **21 of 27** |
| Silent wrong | 0 | 0 (Wilson upper bound about 3.7%) |
| Limit line on a wrong query | 0 | 0 |
| Loud | 23 | 6 |
| Random / cities | 30/30, 47/70 | 30/30, 64/70 |
| Calls | 124 | 140 |
| Chip / Qwen / echo tokens | 415,894 / 23,962 / 4,631 | 458,838 / 12,266 / 4,953, plus 3,696 runner tokens |
| Seconds over questions / process | 4,136 / 4,594 | 3,214 / 3,442 (deadline 11,700) |
| Lock errors, head mismatches | 0, 0 | 0, 0 |

- **What failed:** 6 loud, every one repeating " station" through all 3 calls. All 27 wrong first lines were `NONE` with " station" added.
- **Limit lines:** 18 had a true limit line first. They kept chain3's flow: 7 more calls and 6 prose runs to budget, 26,954 chip tokens for nothing, none lost.
- **Stock sample:** `cities/c006` q288, `random/r067` q21: 8,912 positions bit-equal, including the runner's tokens and readback, end states equal.
- **Qwen's own text after the line is much worse than the line** (`--readback 96`; not graded): right 38, **misread 44**, none 18 (9 cut at the cap, 6 at the budget, 3 called again). All 44 misreads follow right lines. Of them, 27 keep the right handle and 12 have the right label if spaces are ignored; others are plainly wrong ("Av", "St-Hu", "Barro St-SummitTech"). So 54% of finished statements misstate a right answer, and told does not fix reading. This is the same effect as "Eaasgate", and it is why the machine's line has to be the answer.
- **Limits on the reading.**
  - The difference from 77 mixes two draws, though first-attempt is 73 on both. Rescued is the cleaner number.
  - The note was written after seeing these failures, and all 70 city questions share one wording. "Describes" fits " station" and may not fit other shapes or a name that holds such a word; no such case arose here.
  - A retry can change the start, which is how `@109` arose earlier. 0 here, but 21 changed starts is a small test.
  - The note and prefill are not in firmware. The note's placement, after `</think>`, is not what firmware would do.
- **Guesses against results:** correct 85-93 (80-88 before step 1), got 94. Silent 0-3, got 0. Limit on wrong query 0-2, got 0. Misread 10-25% of finished statements, got 54%. Lock errors 0, got 0.
