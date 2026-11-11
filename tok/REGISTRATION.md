# TOK: the machine prints normal tokens (Theo, 2 Nov)

Why, and what's asked: `PATH.md` "Answer mode". Development only, no gate, dev data only (`data/dev/`, never `data/heldout/`). Each step below is registered and committed before it runs; results go in `DEVLOG.md`. Limits for every step: `tools/memguard.py`, `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25`, `PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2`, `PYTHONDONTWRITEBYTECODE=1`, one process of mine at a time, no run over 4 hours, budgets never raised. Copies only: `fw/`, `rvc/`, `exec/`, `vendor/` and existing checkpoints stay as they are.

**The target (lead, 2 Nov).** After Qwen's `</tool_call>`, the stream equals a real tool turn token for token, that is the real tokenizer on `host/tools.py forced_text`:
`<|im_end|>` `\n` `<|im_start|>` `user` `\n` `<tool_response>` `\n` LINE `\n` `</tool_response>` `<|im_end|>` `\n` `<|im_start|>` `assistant` `\n` `<think>` `\n\n` `</think>` `\n\n`.

## Step T1: exactness by tokenizer alone (`tok_only.py`; registered before running)
No model, no machine, no firmware. Option under test: label and relation tokens stored as boot data, tokenized once by the real tokenizer with a leading space, and fixed words as stored tokens (`fragments.py`). A line is cut into parts by a fixed rule, and the parts' tokens are joined: fixed words, digits as digit tokens, `@` or ` @`, a label's stored tokens, a relation's stored tokens, and arguments echoed from the call as byte tokens, since the machine holds a call's bytes and no token ids.

**Lines tested.**
1. Synthetic: every node and relation of all 128 `data/dev` graphs in every SPEC §3 line shape.
2. Real: every `answer_text` in `data/dev`, and every machine line saved in `rvc/results/chain3/all.jsonl` and `rvc/results/chain4_fresh/all.jsonl`.

**Reported, separately.**
- Bytes: joined tokens decode to the line's bytes, by `bridge.Text`. Exact is the point: anything below 100% is a bug in the option.
- Tokens: joined tokens equal the real tokenizer on the whole wrapped response. Mismatches listed by kind.
- Arguments: lines with an echoed argument, reported apart, since these are bytes by design.
- Boot data: DROM image with the token table against the 131,072 bytes, per graph, at 4 bytes a token.
- Reserved: any label whose text contains an added token's string, which the machine must not print as that special.

**Budget.** Measured 169,577 encodes a second (one-off pilot on the 18,935 distinct labels). Lines: about 12 shapes × about 25,000 nodes + 30,000 real lines = about 330,000, each encoded once whole and split into parts, so about 1M encodes: 6 s × 1.5 = 9 s. Allowing for Python around it, `timeout 600`. CPU only, memguard 6 GiB.

**Guesses (no bar).** Bytes 100% on every line. Tokens equal on at least 99.9% of label lines; any miss is a label ending in punctuation before a newline. Lines with an echoed argument: tokens differ on most, bytes equal on all. Every dev graph but r097 fits the DROM at 4 bytes a token, or at most three more do not.

## Step T1b: names whose tokenization could depend on their neighbours (`tok_adversarial.py`; registered before running)
T1's data has no awkward names, so T1 can't say what breaks. The same joining rule, by tokenizer alone, on hand-made awkward names (trailing and leading punctuation, apostrophes, spaces, digits first, non-Latin, combining marks, emoji, added-token strings) and the random names `rvc/test_m1.py` already uses, in every line shape.

**Budget:** under 1 second of encodes; `timeout 120`, memguard 4 GiB.
**Guesses (no bar).** Bytes exact on all but names holding an added-token string, where the tokenizer turns the text into the special. Tokens differ only at a name ending in punctuation before a newline (`St.` + `\n` is one token, `.\n`) and at trailing whitespace.

## The option chosen for building, and why (2 Nov, before any build)
**Bridge exit widened, labels as boot tokens.** Full reasoning and the other options are in `DEVLOG.md`.
- **Firmware:** `put_id`: `ecall` with a7 = 1, a0 = 511, followed by `addi x0, rs, 0` where `rs` holds a token id.
- **Circuit (exit layer only):** at chip token `BYTE(511)`, the echo's output code is the token id, read from the `val` bits of the next instruction, which the exit already reads. So the next instruction acts as a delay slot. Family `T0`..`T3` holds id bits 17..16, in the four unused family ids; payload holds bits 15..0. HALT's echo becomes `\n\n` (271).
- **Embedding:** every text row with a token gets its code in the 21 code dims. The tool-call rows and reserved rows stay empty, so they can't be printed. Qwen's dims are not touched.
- **Boot data:** label and relation tokens, tokenized once with a leading space when a graph loads; a name holding an added token's string stays bytes. Fixed words are firmware literals tokenized at build.
- **No new head, no new chip token, no new code dim, no new layer planned.** Old byte printing stays (BYTE(0..259)).

All in copies under `tok/`: `core.py` (copy of the vendored core), `boot_tok.py`, `gen_fw.py` (writes `graphlib.c` from `fw/graphlib.c`), engine and tables, and `overlay.py`, which patches only the running process.

## Step T2: reference machine (`test_ref.py`; registered before running)
`rvc/test_m1.py`'s whole test, through the new firmware on `ref.Machine` and a `bridge.Session` patched by `overlay.py`, on the same six parts (framing, real, limits, dev, random, medium), against `lib/reflib.py`.

**Reported.** Bytes: every check's line equals reflib's, with the new wrapping; `TOOLONG` as predicted. Tokens: printed tokens equal the real tokenizer on `forced_text(line)`, by part, with misses sorted into echoed argument, trailing whitespace, added-token string, other. Mean chip tokens per function, against `fw/results/m1_fw/m1_full.summary.json`. Fit: ROM, rodata, RAM, DROM, dev graphs that fit.

**Budget.** The same test on `fw` took 553 s (`fw/results/m1_fw`) at 4 workers; × 1.5 = 830 s. `timeout 900`. Memguard 8 GiB (peak 2.58 GiB then).

**Guesses (no bar).** Byte mismatches 0 on every part. Tokens: equal on all lines but those with echoed arguments, trailing whitespace before a newline, or an added-token string. Chip tokens: `chase` about 1.5× lower than `fw`'s, as printing was about a third of it; labels in tokens of about 5 against bytes of about 15. `find` lower, `cheapest` about the same. Dev graphs fitting at 2 to 4 bytes a token: at least 126 of 128. First run may expose bugs in my code; bug fixes before the full run are recorded, and the registered bar is the full run.

## Step T3: the circuit on its IR, then the executor, no weights (`ir_tok.py`, `test_ref.py`; registered before running)
**A. Shape.** `core.build` with tok/'s exit against the vendored one: FFN units, heads, layers, slots, hidden size (`merge_tok.py --plan-only`, no writing).
**B. IR.** `rvc/ir_check.py`'s check on tok/'s firmware: every circuit-owned token of real sessions, all ten functions, on `cities/c024` and `random/r001`, against `ir.evaluate`, owner bit at every position.
**C. Executor.** `exec/test_ir.py` (a copy with tok/'s tables): every IR dim at every position of 3 tiny calls against `ir.evaluate`. Then `exec/test_ref.py` (a copy): the engine free-running against the reference machine on dev calls, seed 5.

**Budget.** A build 30 s. B: 159.5 s + 189.2 s measured on the old firmware (`rvc/results/m1_ir.json`), × 1.5 = 525 s. C: `exec/results/test_ir_dev.json`'s run plus compile, 300 s; `test_ref` 2.5M chip tokens at 10,480/s (`exec/DEVLOG.md`) is 240 s, plus reference and prompt overhead; `--limit-s 1200`, its registered cap. Memguard 12 GiB; CPU only.

**Guesses (no bar).** A: fewer than 200 new units, 0 new heads, 0 new layers, at most 3 new slots, hidden stays 3968. B: 0 wrong, 0 owner mismatches. C: 0 dims differ, 0 wrong, no engine flags. If the shape changes, I stop and report, as a change of shape would be a fork.

## Step T4: the merged checkpoint (`merge_tok.py`; registered before running)
To `~/Models/x210/x210-tok` on the SSD, by replacing the chip side of a copy of `x210-rvc`, shard by shard: Qwen's layers copied bit for bit (the mute columns move if the mu dim moved). Not re-fitted, so memory stays under the limit that the vendored merge's 43 GiB would exceed.
**One deliberate change in the final norm:** the output code's gain goes from 2^20 to 2^22. Every text row now has a code one bit from another, so a Qwen logit could otherwise bring a neighbour close. The vendored store's `ID_GAIN = 4` is the same reasoning. No effect at Qwen's own positions, where the code is 0.
**`generation_config.json`:** `bad_words_ids` removed, because the machine prints `<|im_start|>`.

**Budget.** The vendored merge took 497 s (`rvc/DEVLOG.md`); this does less: × 1.5 = 750 s, `timeout 900`. Memguard 32 GiB; a kill is a finding and the limit stays. Disk 18.8 GB; free space checked first.

**Checks.** `exec/weightcheck.py` (a copy) against tok/'s IR: 0 differences in chip layers, embedding and final norm. Its budget: 288 s measured × 1.5 = 432 s. Separately, each Qwen-layer tensor against `x210-rvc`: equal bit for bit, by streaming hash, about 19 GB at disk speed, `timeout 600`.
**Guesses (no bar).** Under 32 GiB, about 15 GiB peak. 0 differences. Qwen's tensors equal apart from any moved mute columns.

## Step T5: the executor against the new weights, bit for bit (`stock_trace.py`, `check_trace.py`, `drive.py --verify all`; registered before running)
**A. Teacher-forced.** Stock modules on MPS, bf16, sdpa, nothing compacted, on `plan_tok.json`: tiny-ten (all ten functions, an unknown function), c024 chases, r001 mixed, lim-lines-b (limit lines, `NONE`). Saved residual over all 3,968 dims; the executor replayed against it. Also reported: `wrong`, `not_owned_fired`, `head_mismatch`, and a new figure, the smallest logit gap between the chosen token and the next at owned text positions.
**B. Whole questions, the answer included.** `drive.py --verify all`: stock and executor in lockstep, every position over all dims, Qwen's own tokens included, every head's state at the end. Ten tools, as `host/out/dev2`: r001 q0, q17, q25; c024 q0; tiny q0. Fixed now, chosen for one call each in the host's transcripts and a mix of `find`, `chase`, `path`, by reading those transcripts, not any new result.
**C. A control.** `check_trace.py --flip-trace seed:0:8`: 8 flipped bits in the saved stock data, on tiny-ten.

**Reported for B:** does Qwen's own `<|im_end|>` end the turn (status `answered`); the machine's response tokens against the real tokenizer on `forced_text(host line)`; Qwen's tokens against the host transcript.

**Budget.**
- A: about 66,000 positions at the lowest measured stock rate, 20.8 chip/s (`rvc/DEVLOG.md`) = 3,170 s, + load 230 s, × 1.5 = 5,100 s, `--hours 1.42`, `timeout 5400`.
- B: 25,000 chip tokens at 22 chip/s + 300 text tokens at 5/s + prefill 30 s × 5 = 1,340 s; 3 loads 690 s; × 1.5 = 3,050 s; r001 1,800 s, c024 and tiny 625 s each; 1,200 s a question.
- Replay and control: 300 s.
- Memguard 32 GiB. One stock-weights process at a time, none below 30% free, as other streams are on the GPU.

**Guesses (no bar).** 0 positions differ, 0 wrong, 0 head mismatches. Smallest margin well above 0: about 2 code bits at gain 2^22. All five end `answered`, on their own `<|im_end|>`. Response tokens equal on all, as none echoes an argument. Qwen's tokens equal the host's on 3-5 of 5; earlier arms show the merged path sometimes differs from base Qwen on first calls.

## Step T6: does Qwen read the machine? Executor, the 50 host questions (`drive.py`; registered before running)
The flow `rvc/results/wrapctl_*` and `host/out/dev2` used: ten tools, Qwen answers in its own words, 12 calls, 768 tokens per turn, 3,072 per question. The same 50 questions, c024, c025, r001, tiny. Executor for the chip side, Qwen's layers stock on MPS, lock against the reference machine on. Scored by `host/score.py` on Qwen's final text.

**Beside:** host in normal tokens 41/49, 6 at cap, 190 calls; circuit wrapping in normal tokens 38/49; machine bytes 19/49, 23 at cap, 358 calls; floor for "identical to host" 29/50 (`rvc/DEVLOG.md`). Reported: correct, at cap, calls, questions identical to the host transcript, response tokens equal to the real tokenizer, lock errors, chip, Qwen and echo tokens. No bar, and not reviewed; a small dev sample.

**Budget.** Executor questions took 33-41 s (`rvc/results/chain3/tally.json`); here up to 12 calls: assume 60 s × 50 × 1.5 = 4,500 s; 4 loads 450 s × 1.5 = 2,700 s; 7,200 s across 4 processes, each under its own `timeout 2400`; 600 s a question.

**Guesses (no bar).** Correct 36-41 of 49, against 19 for bytes. At cap at most 10. Calls 190-240. Identical to host 15-30 of 50. Lock errors 0.

## Step T7: can a refused name print in normal tokens with no weights change? By tokenizer alone (`refused.py`; registered before running)
**Why.** T6 lost 7 questions to `NONE <name> station` spelled in bytes. Theo has approved the final build with t8's cleaner; the lead asks whether what the cleaner still refuses can print in tokens at low cost.
**The idea: firmware and boot data only, no new head, no new checkpoint.** At boot, the graph's own names (labels, relations, t8's noun) are cut into the tokenizer's regex pieces (` Falcon`, ` Av`, `-In`), and a piece table holds each piece's bytes and tokens, with a hash on the bytes. Printing a refused argument: firmware cuts the bytes by the same rule for ASCII and looks each piece up, comparing bytes exactly. A piece found prints its tokens; not found, or at any non-ASCII byte, prints bytes. So bytes stay exact by construction. No word list: only the graph's own names, so generality stays.
**Reported.** On every saved echoed line (T6's 118, the machine lines in chain3 and chain4_fresh, `answer_text` in `data/dev`, and noun-stripped forms): bytes equal; tokens equal the real tokenizer; share of bytes printed through pieces. DROM added per graph, and how many of 128 graphs still fit. A table that doesn't fit is left out at boot, and that graph prints bytes.
**Budget.** T1's 24 s over 357,801 lines; here far fewer lines, plus table building: 60 s × 1.5, `timeout 120`. Memguard 4 GiB.
**Guesses (no bar).** Bytes exact on all. On city `NONE X station` lines: tokens equal on at least 90%. Random graphs' invented or malformed arguments: at most 50%. Added DROM mean about 6 KB; at most 4 more graphs lose the table.
**Not settled by this:** whether Qwen recovers. That needs a run on the final firmware.

## Step T8: the piece table in firmware, on the reference machine (`pieces.py`, `test_pieces.py`; registered before running)
`put_span`, the only path for echoed arguments, prints through the table. Boot appends the table after the image, in header words 28 and 29 (t8 holds 26 and 27); if the image wouldn't fit, the words stay 0 and that graph prints bytes as now. Firmware only, on this checkpoint: no head, no weights. Its source is `tok/graphlib.c` with one function replaced, written to `tok/pieces/graphlib.c`, so `tok/graphlib.c` stays pinned, and t8 can apply the same function.
**Test:** `test_ref_m1.py`'s whole test on it, the same parts. **Budget:** T2's 247 s × 1.5 = 370 s, `timeout 600`, 8 GiB.
**Reported:** byte mismatches; tokens equal, by kind; chip tokens on `NONE` lines against T2; graphs with and without a table.
**Guesses (no bar).** 0 byte mismatches. "Echoed argument" misses fall on dev cities to about 0; random stays high. A `NONE` call costs 300-800 more chip tokens. 120-126 of 128 graphs hold their table.

## T8b: the rest of T8's test (registered before running)
T8 hit its 600 s limit at job 416 of 476, on a machine shared with T5 A and other streams, and rebuilding the table for every fresh box in Python. No bad check by then. Not raised. The rest: `--parts medium,fit`, the jobs a limit stopped, and the fit figures that only print at the end, with the table cached per graph. The 60 random jobs left aren't repeated. Budget: 300 s, `timeout 300`, 8 GiB. Guess: 0 byte mismatches.

## Step T9: does the piece table bring the 7 back? (`drive_pieces.py`; registered before running)
T6's flow on `tok/build/tok-pieces.elf`, on the same checkpoint, on T6's c024 and c025, 16 questions, the 7 lost among them. No cleaner here, so this tests the table alone. **Ran on the slow path, `drive.py`,** as the fast runner isn't proven on this firmware. c024 q1 runs in stock lockstep, to cover the new firmware: every position over all dims.
**Budget.** T6's c024 + c025: 15 + 15 minutes = 1,830 s, × 1.5 = 2,745 s, plus lockstep 400 s × 1.5 = 600 s, `timeout 1800` each graph. After T5 A, one process at a time.
**Guesses (no bar).** The 7 lost: 4-7 recover. Correct on the 16: 12-15, against T6's 9. At cap: 0-3 against 6. Lockstep mismatches 0, lock errors 0.
