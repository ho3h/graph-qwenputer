# X2.10 tok/ development log: the machine prints normal tokens

Development; no gate, not reviewed. Acceptance is `REGISTRATION.md`. Every number names its file. Times are ET, 2 Nov 2026.

## How it prints today (from reading the code; no run)
- **The firmware** calls `ecall` with a7 = 1 and a0 = a byte, or 256..259 for `<tool_response>`, `</tool_response>`, `<think>`, `</think>` (`fw/graphlib.c` `put`, `main`).
- **The circuit** turns that into chip token `BYTE(a0 & 511)`: 9 bits (`core.py` `case(nr + [ecall, a7_is[1]], "BYTE", B[0:9])`, `spec.py` `("BYTE", 512)`).
- **The next token is the echo:** at a BYTE token the exit writes output code family `Q` with the BYTE's own 9 payload bits (`cases.append(([fam["BYTE"]], "Q", c.pay["BYTE"]))`). The code is 5 family bits and 16 payload bits, 21 dims. So it says "printable entry p", and the code has room for far more than 9 bits.
- **What picks the token:** the output code is tied to the embedding. Only the 260 printable rows hold a code in those dims (`bridge.SPECIALS`, `core.py` `code_of`, `merge.py` `text_rows`). Every other row holds 0, so the stock head can't choose it, and `core.decode_code` has nothing to map it to (`printable[p]`, length 260).
- **Why only bytes:** three limits at once: 9 bits in BYTE, a table of 260 rows in the weights, and firmware that holds label bytes. Labels are bytes in the DROM.
- **HALT's echo** is a constant: `\n` (`cases.append(([fam["HALT"]], "Q", nl))`).
- **How a printed token reaches Qwen:** it is an ordinary text token. It goes in by its own id, runs every layer through its normal row, and is not muted (`rvc/drive.py`: `chat._layers(nxt, cache, pos)` for ids below `v0`). Only chip tokens are hidden from Qwen (`mu`). So visibility needs nothing new: any id that gets printed is read like any other token.

**What stops `<|im_end|>` and `<|im_start|>` today (lead's question):**
1. Their rows hold no output code and they aren't in `bridge.SPECIALS`, so neither the head nor the decoder can pick them. This is the only hard stop, and it's in the weights.
2. The firmware has no number to print for them; 260 and up reach nothing (the reference echoes `\n` and the decoder raises).
3. `generation_config.json` in the merged checkpoint has `<|im_end|>` as EOS and `bad_words_ids: [[<|im_start|>]]`. Stock `model.generate` would stop at a machine-printed `<|im_end|>` and refuse the machine's `<|im_start|>`. Our runners decode by hand and look for stops only on Qwen's own tokens (`rvc/drive.py`: `expect` branch first), so they are unaffected. A plain `generate` needs its own stop rule.
4. HALT's `\n` can't equal the template's last token, `\n\n` (id 271): a constant in the exit.

**The reverse direction.** A call is captured as each token's first 16 bytes over 80 rows (`tbuf`), so any token Qwen writes reaches the firmware; only tokens of 16 bytes or more and calls past 80 tokens answer `TOOLONG`. Qwen's own tokens are normal already, so reading has no analogue of this problem. It bites once, here: the machine holds a call's bytes and not its token ids, so a line that echoes an argument (`NONE 109 Av station`) can't re-print Qwen's tokens.

## T1: stored tokens against the real tokenizer (done 12:56; `results/t1.json`, `tok_only.py`, `fragments.py`)
**A slip first.** Registration commit `00db48b949` hit another thread's git lock, and the run started in the same batch of tool calls, so the commit landed about a minute after the run. The text was written before the run and did not change. Later steps wait for the commit's result before anything runs.

No model, no machine. 24 s, peak 0.59 GiB. Tokenizer `~/Models/x210/Qwen3.5-4B/tokenizer.json`.

| Lines | Count | Bytes equal | Tokens equal to the real tokenizer on the whole wrapped response |
|---|---:|---:|---:|
| Synthetic: every node and relation of all 128 dev graphs, 13 SPEC line shapes | 339,612 | 339,612 | 339,612 |
| Real, no echoed argument: `answer_text` in `data/dev` | 17,432 | 17,432 | 17,432 |
| Real, no echoed argument: machine lines in chain3 and chain4_fresh | 184 | 184 | 184 |
| Real, echoed argument: `answer_text` | 493 | 493 | 100 |
| Real, echoed argument: machine lines | 80 | 80 | 0 |

- **Bytes:** exact on all 357,801 lines. **Tokens:** exact on every line that has no echoed argument, so stored tokens, tokenized once with a leading space and joined, are what the tokenizer would write, on these names.
- **The whole turn** includes `<|im_end|>`, `<|im_start|>`, `user`, `assistant` and `\n\n`: the fixed head and tail tokens are in the file.
- **Echoed arguments are the gap.** `NONE 109 Av station` prints the word part as single-byte tokens. All 80 machine-line misses are that case. Those are the error lines Qwen must read on a retry.
- **Boot data at 4 bytes a token:** 124 of 128 fit, against 127 today. r092, r096, r099 no longer fit (131,990, 143,684, 133,000 of 131,072), and r097 didn't before. 102,715 tokens in all, 8,619 at or above 65,536, at most 12 in a name.
- **Guesses against results:** bytes 100%, got it. Tokens at least 99.9% of label lines, got 100%. Misses at trailing punctuation: none here. At most three more graphs not fitting: exactly three.

## T1b: awkward names (done 12:59; `results/t1b.json`, `tok_adversarial.py`)
57 hand-made names in 25 lines each, and 300 random graphs from `cop/test_a1_dev.py`, 62,920 lines, 5 s.
- **What precedes a name doesn't matter on this interface.** A label always prints after `@h ` and a relation always after ` > `, so its left context is fixed: a space. Tokenized once with that space, every name matched at its start, including digits first, apostrophes, non-Latin and emoji.
- **What follows matters in one case:** a name ending in whitespace before a newline. `@9  ` then `\n` is one token, `ĠĠĊ`, in the real tokenizer, two here. 957 of 62,920 random lines, all of this kind in the 30 kept; `trail `, `\n` and ` ` in the hand list. My guess of trailing punctuation was wrong: `St.` + `\n` stays two tokens in this vocabulary. Bytes stay equal.
- **Bytes:** exact on all the random lines and on all hand names except one that isn't NFC, which boot refuses (`BootLimit`).
- **A real hazard:** a name holding `<tool_call>` or `<|im_end|>` tokenizes to the special itself. It matches what the host's tokenizer does, but the machine must never print `<tool_call>`: a printed `<tool_call>` would arm its own capture. So the boot builder keeps such a name as byte tokens, and the tool-call rows hold no code at all, so they can't be printed.
- **Guesses against results:** tokens differ at trailing punctuation: no. At trailing whitespace: yes. Bytes: as guessed.

## The options (reasoned from the code before building; numbers filled in from T2-T4 where they exist)
| Option | Changes | New heads | Checkpoint | Keeps generality | Echo count | Reads to Qwen |
|---|---|---:|---|---|---|---|
| **A. Widen the printable table only.** Use the 252 spare BYTE codes for `<|im_end|>`, `<|im_start|>`, `user`, `assistant`, `\n\n` and common tokens | Embedding rows only, no circuit | 0 | Same size | Yes, but 252 common tokens don't spell most names, so names stay mostly bytes | Barely changes | Yes |
| **B. Exit widened, id from a delay slot, labels as boot tokens (the pick)** | A few cases in the exit layer, code in every text row, firmware, boot data | 0 | Same size | Yes: any label, tokenized at load | One token per tokenizer token, except echoed arguments | Yes |
| **C. A BYTE family of 18 bits, no delay slot** | 2^18 new chip rows, two more code dims | 0 | +2.08 GB (262,144 × 3,968 × 2 bytes) | Yes | As B | Yes |
| **D. The vendored store's any-print** (`--store`) | Separate 18-bit id code plus input id dims; store heads along with it unless cut out | Store's heads, or new wiring | More; 36 more dims at least | Yes, except ids from 248,044 up, so no turn markers from it | As B | Yes |
| **E. A small word-to-token table** in firmware | Needs a route to print those tokens anyway (A or B). On A: at most 252 words | 0 | Same | No, not by itself: a name outside the list is bytes, and the list is what any map's names would be fitted to | Mixed | Yes |
| **F. Print a handle, keep names in stored tokens elsewhere** | Handle alone is what `rb/` tried: Qwen can't name the answer. Names in the prompt would be the map in visible text, against the design | 0 | Same | Not as a reply | Few | Handle only |

**Why B.** It's the only one that's general, has the whole vocabulary and the turn markers, and costs no head, no dim and no size. It's small because the output code already has 16 payload bits, 4 family ids are unused, and the exit already reads the `val` bits of the next instruction, so the id doesn't have to be carried anywhere new. The price: the next instruction after that `ecall` must be `addi x0, rs, 0`. The firmware's one inline routine holds that rule, and the reference machine asserts it.

**Weights or firmware?** Weights, necessarily. No firmware alone can print a token whose row has no code. So every option above touches at least the embedding.

**Not solved by any of these:** arguments echoed from the call. See T1. Options for later, not built:
- Id in the capture rows: the last 3 of a row's 16 bytes hold the token's 18-bit id, in the embedding, no new head. Tokens of 13 bytes or more would then answer `TOOLONG`. Firmware has to keep tokens' spans. The first token of an argument still differs (`Times` as Qwen wrote it, ` Times` as a tokenizer writes it after `NONE `).
- A new `tbuf` value head that captures ids: a new circuit head.

## T2: reference machine (done 13:20; `results/t2/m1_full.summary.json`, `results/t2/tok_by_task.jsonl`, `results/t2.log`, `test_ref_m1.py`)
**First attempt voided by my own slip.** While it ran I copied `exec/test_ref.py` into `tok/` under the same name as my test, overwriting it. Pool workers respawned from the wrong file and the run stuck at job 160 of 476. I stopped it and kept its output in `results/t2_aborted/`. Nothing else was lost. Renamed `test_ref_m1.py`; the second run is the result, at the registered budget.

247 s against the 830 s budget, 4 workers, peak 2.84 GiB under the 8 limit.

| Part | Checks | Bytes match | `TOOLONG` as predicted | Byte mismatches | Tokens equal real tokenizer | Echoed argument | Trailing whitespace | Other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | 29,047 | 29,047 | 0 | 0 | 28,662 | 385 | 0 | 0 |
| real | 1,358 | 1,358 | 0 | 0 | 1,152 of 1,408 lines | 256 | 0 | 0 |
| random | 24,000 | 22,788 | 1,212 | 0 | 17,090 | 6,644 | 266 | 0 |
| medium | 512 | 497 | 15 | 0 | 478 | 30 | 4 | 0 |
| limits | 332 | 330 | 2 | 0 | 322 of 333 lines | 11 | 0 | 0 |
| framing | 33 | 31 | 2 | 0 | 22 | 11 | 0 | 0 |

(The token count includes setup calls and `TOOLONG` lines, which is why two parts have a different base. `TOOLONG` is a fixed word, and is compared like any line.)

- **Bytes: exact, 0 mismatches,** the same result as `fw` on the same test, with all 10 functions and every limit line.
- **Tokens: the real tokenizer on every line,** apart from the two registered kinds. 0 "other".
- **Tokens per answer are not cheaper in chip tokens,** against my guess of 1.5× lower: dev `chase` 3,101 against 2,912, `find` 1,898 against 1,595, `close` 1,300 against 995; `cheapest` 36,240 against 37,995, `path` 12,129 against 12,755. Printing costs more per token than per byte, and the wrapper now has 18 tokens against 13.
- **Echoed text tokens fall:** dev `chase` 27.6 against 31.6, `path` 43.5 against 67.1, `cheapest` 81.9 against 145.1. Those run all of Qwen's layers, about 1,000× the time of a chip token in the earlier runs, so this is the cost that counts for a whole answer.
- **Fit:** ROM 26,904 bytes against 34,380, rodata 1,356 against 632 of 4,096, lowest stack 0x7D30. **Dev graphs: 126 of 128 fit** at about 2.2 bytes a token, against 127. r096 is the new one (137,334 of 131,072); r097 did not fit before. At 16-byte labels the largest E at N = 1,024 falls from 7,486 to 4,410: random 16-byte labels are the worst case for tokens, at about 8 bytes of token table each. NYC-scale: N = 500, E = 1,800 takes 66,216 bytes against 48,160.
- **Guesses against results:** byte mismatches 0, right. Tokens only those kinds, right, and no added-token cases arose. `chase` 1.5× lower: wrong, about 6.5% higher. `cheapest` same: about right. At least 126 of 128: exactly 126.

## T3: the circuit on its IR, then the executor, no weights (done 13:38)
**Shape** (`merge_tok.py --plan-only`, its output in `results/merge_report.json` once T4 writes it):

| | x210-rvc | tok | |
|---|---:|---:|---|
| FFN units | 42,114 | 42,199 | 85 new |
| Heads | 103 | 103 | none new |
| Chip layers | 11 | 11 | |
| IR dims | 2,918 | 2,919 | 1 new |
| Slots | 1,265 | 1,266 | |
| Hidden, ballast | 3,968, 62 | 3,968, 62 | same |
| Output code dims, `mu`, `tau` | | same positions | so Qwen's mute columns don't move |

So **no new head, no new layer, no new chip token, no new code dim:** 85 units in the exit. Guesses: under 200 units, 0 heads, 0 layers, at most 3 slots: right on all.

**IR** (`results/t3_ir.json`, `ir_tok.py`): `ir.evaluate` against the reference. c024: 17,641 positions, 17,302 owned. r001: 31,283, 30,699 owned. **0 wrong, 0 owner mismatches.** Calls: chase, close, find, follow, link, neighbours, reopen, unlink, an unknown function, a `NONE` line. `path` and `cheapest` are not in this one: they run on the engine below and the stock trace in T5. 146 s against 555 s.

**Executor** (engine 3f943a9e305c, a copy of `exec/engine.c` plus 1 line; tables `build/program-*.npz`, compile 23 s):
- Against the IR (`results/t3_engine_ir.json`, `test_ir.py`): 6,050 positions of tiny's first 3 calls, every one of 2,919 IR dims: 0 differ, no flags.
- Free-running against the reference machine (`results/t3_engine_ref.json`, `test_ref.py`, seed 5): 486 calls with all ten functions, **2,518,608 chip tokens, 0 wrong, 0 engine flags;** 13,160 chip tokens a second, shared machine; 1 call skipped for length (over 400,000 records), 2 graphs don't fit. 778 s against the 1,300 s hard limit. Peak 0.68 GiB.

**Guesses against results:** 0 wrong, 0 differ, no flags: right.

## T4: the merged checkpoint (done 13:44; `~/Models/x210/x210-tok`, `results/merge_report.json`, `results/t4_merge.log`, `results/t4_qwen_tensors.json`, `results/t4_weightcheck.json`)
**Memguard killed two attempts at the 32 GiB limit, as designed; the limit stayed.** First at 32.18 GiB and second at 32.63 GiB (`mem.log`, `results/t4_merge_killed.log`), in 20 seconds each, holding the embedding and the chip layers together. Memory freed inside the process isn't returned quickly, so the footprint stays high. The fix is order: the embedding first, written to its shard and released, then the chip layers. **Third attempt: 22 s, peak 31.11 GiB.** That's under the limit by less than 1 GiB, so the merge step has little room; the footprint falls to 3 GiB by the last shard. Most of the peak is `chip rows` at 21 GiB, a float array of all chip tokens, and could be cut if it matters.

**What's in it.** 18 GB, same 8 shard names and tensor names as `x210-rvc`. Mute columns didn't move.

| Check | Result |
|---|---|
| 424 tensors of Qwen's layers against `x210-rvc`, bit for bit | 424 same, 0 different |
| Qwen's dims of embedding and final norm | same |
| Chip-layer tensors | 114 same, 40 changed |
| Embedding rows with changed chip dims | 247,808, every printable-by-id row; the code only |
| `weightcheck.py` against tok/'s IR, chip layers | 0 problems over 1,045,099 nonzeros, 45,156 units, 1,652 handovers |
| The same, embedding | 250 rows differ: the known `<|reserved_0..249|>` difference, none new. That's why its exit code is 3 |
| Final norm | others -1, tau 2^60, code gain 2^22 |
| Seeded single-weight changes | 60 of 60 caught |

Guess: about 15 GiB peak. Got 31.11. 0 differences: right. Qwen's tensors equal: right.

## T5 part B: whole questions, stock and executor in lockstep (done 14:05; `results/t5b_stock/*.jsonl`, `results/t5b_compare.json`, `compare_host.py`)
**Two slips before this.** The first start ran `drive.py` with its `--ckpt` default from `rvc/decode.py`, which is `x210-rvc` on the LaCie, while it was still loading. I stopped it before any question and fixed the default to `x210-tok`. Its leftover file is `results/t5b/tiny.jsonl.verify.json`, nothing else.

Merged weights on stock modules on MPS, bf16, sdpa, with the C engine alongside, every position over all 3,968 dims, Qwen's own tokens included. Load 14 s from the SSD, against 208-227 s from the LaCie.

| Question | Status | Correct | Calls (host) | Identical to host | Lockstep positions | Mismatches | Head mismatches | End states |
|---|---|---|---:|---|---:|---:|---:|---|
| tiny q0 | answered | yes | 2 (2) | no: `NONE Eastgate station` | 2,922 | 0 | 0 | equal |
| c024 q0 | answered | yes | 2 (2) | **yes** | 5,021 | 0 | 0 | equal |
| r001 q0 | answered | yes | 1 (1) | **yes** | 1,792 | 0 | 0 | equal |
| r001 q17 | answered | yes | 1 (1) | **yes** | 3,219 | 0 | 0 | equal |
| r001 q25 | answered | yes | 1 (1) | no: Qwen adds ` (2 steps)` before its stop | 2,497 | 0 | 0 | equal |

- **15,451 positions, 0 differ, 0 head mismatches, 0 lock errors.** All on the stock head's argmax over the whole vocabulary, on every machine token printed by id.
- **All 5 ended on Qwen's own `<|im_end|>`** (status `answered`). So a machine-printed `<|im_end|>` before the response, and Qwen's own after its reply, both work in our runner: the runner looks for stops only on Qwen's tokens.
- **3 of 5 are token for token the host's transcript,** from the first generated token to the last. That's the target, on real questions.
- **The two differences.** tiny q0's first line is an echoed argument: `NONE`, ` `, `E`, `a`, `s`, `t`… where the host has `NONE`, ` East`, `gate`, ` station`. Qwen went on correctly. r001 q25's response tokens equal the host's; Qwen's own last words differ, as the earlier arms found on merged weights (`ctrl/results/a1_pairs.json`).
- **Qwen reads the names here,** where it misread them before: "Ruskunri Dagil", "Murbol", "Heron Pl". Five questions; T6 is the larger read.
- Peak 20.36 GiB. 838 s over questions against the 3,050 s budget.
- **Guesses against results:** 0 differ, 0 head: right. All five `answered`: right. Response tokens equal on all, none echoing: wrong, tiny q0 echoed. Qwen's tokens equal on 3-5 of 5: 4 of 5 on Qwen's tokens.

## T6: does Qwen read the machine? The 50 host questions on the executor (done 15:10; `results/t6/*.jsonl`, `results/t6_compare.json`, `results/t6_*.log`). Ran on the slow path, `drive.py`
Development, not reviewed. Chip side on the engine, Qwen's layers stock on MPS, lock to the reference on. 3,695 s over questions against the 7,200 s budget; peak 20.37 GiB.

| Of 49 scored (50 run) | Machine, bytes | Host, normal, circuit wrapping | **Machine, normal tokens (T6)** | Host, normal, template |
|---:|---:|---:|---:|---:|
| Correct | 19 | 38 | **35** | 41 |
| At the 12-call cap | 23 | 10 | **10**, plus 1 at the token budget | 6 |
| Calls | 358 | 227 | **234** | 190 |
| Identical to host's transcript, of 50 | 1 | 13 | **26** | floor 29 (eager against sdpa) |

- **Machine:** all 234 lines equal the host tool. 0 lock errors, 0 head mismatches. 537,002 chip, 13,731 Qwen, 8,111 echoed tokens. 39 turns ended by Qwen's own `<|im_end|>`.
- **Response tokens:** equal to the real tokenizer on 116 of 234 lines; the other 118 are the echoed-argument lines, and only those.
- **49 of 50 first calls equal the host's,** token for token (r001 q8 differs). Of the 50: 26 whole transcripts identical, 14 first differ at a machine response, 10 first differ in Qwen's own tokens.
- **The whole gap is one thing.** Against the host, 7 lost and 1 gained. **All 7 lost are `NONE <name> station`.** The machine's line is exact, the host's next call fixes the name, and here Qwen repeats the same call until the cap. In the 7, the host's second line is a clean line or a shorter query; here it is the same `NONE` 12 times. That's why 118 of 234 lines echo: the loops. Without them the machine would be at about 41-42.
- **So where a line has stored tokens, Qwen reads it as it reads the host.** Where the line spells a name in single bytes, Qwen doesn't recover. This fits `rvc/DEVLOG.md`'s control, and `ctrl/results/read_summary.json`'s clean reading test: normal delivery 85 right, 15 limit lines said as answers, 0 misread, against bytes.
- **Guesses against results:** correct 36-41, got 35, just below. At cap at most 10, got 10. Calls 190-240, got 234. Identical 15-30, got 26. Lock errors 0, got 0.

## Echoed arguments: what's left (a decision, not built)
Four routes for the `NONE <name>` family. None is built:
1. **t8's strict cleaner** (Theo's pick for the start name; a t8 build on this firmware) answers `name read as @h label`, in stored tokens, so that family stops echoing wherever a name is recognised. An unknown name still echoes.
2. **Capture ids in the embedding, no new head:** rows' last 3 bytes of 16 hold the 18-bit id, so the firmware can re-print Qwen's own tokens. Cost: a new checkpoint, tokens of 13 bytes or more answer `TOOLONG` (against 16 now), span tracking in firmware. The first token still lacks the tokenizer's leading space, and that's untested on reading.
3. **A new `tbuf` value head capturing ids:** the same without the shorter rows, but a new circuit head.
4. **Leave it:** an unknown name is rare once the cleaner is in, and the line stays loud.

## T7: refused names through a piece table, by tokenizer alone (done 15:40; `results/t7.json`, `refused.py`)
No model, no machine, 3 s. Boot data and firmware only: the graph's names cut into the tokenizer's regex pieces, each with its bytes and tokens; a refused argument is cut by the same rule, pieces found print tokens, the rest bytes. A first run found a bug of mine in the cutter (a space before `(` stood alone), fixed and rerun; the numbers are the rerun's.

| Echoed lines | Lines | Bytes equal | Tokens equal |
|---|---:|---:|---:|
| Machine lines in chain3, chain4_fresh, all `NONE` on cities | 80 | 80 | **80** |
| T6's lines on c024, c025, r001, all `NONE` on cities (tiny isn't in `data/dev`, left out) | 99 | 99 | **99** |
| `answer_text`, `NONE` on random graphs, invented names | 293 | 293 | 193 |
| `answer_text`, `NORELATION` on random graphs | 100 | 100 | 0 |
| `answer_text`, `BADARG` | 100 | 100 | 100 |

So every city `NONE` line in the saved runs, the 7 lost questions' lines among them, comes out exactly as the tokenizer would write it. Invented names aren't in the graph's vocabulary, so they stay bytes: `NONE Ginlu Zq`, `NORELATION zzqx`. The noun comes from boot data (t8's), here `station` on cities. Table: mean 3.9 KB, largest 15.9 KB, before fit.
**Guesses against results:** bytes all, right. Cities at least 90%, got 100%. Random at most 50%: 193 of 293 on `NONE` and 0 of 100 on `NORELATION`, above on the first. Mean about 6 KB, got 3.9.

## T8: the piece table in firmware, reference machine (done 15:48; `results/t8/`, `results/t8.log`, `results/t8b.log`, `pieces.py`, `test_pieces.py`)
**T8 hit its limit** at 416 of 476 jobs (my wrapper's `timeout 590`; machine shared, table rebuilt per box in Python). **T8b** ran the rest: medium and fit, table cached. 60 random jobs weren't repeated. Together: dev 29,047, real 1,358, random 20,480, medium 512, limits 332, framing 33: **0 byte mismatches on 51,762 checks,** 15 + the same `TOOLONG` as predicted.
| Part | Echoed lines not equal: tok (T2) | With the table (T8) |
|---|---:|---:|
| dev | 385 | 204 |
| real | 256 | 76 |
| limits | 11 | 10 |
| framing | 11 | 10 |
| random | 6,644 of 24,000 | 4,988 of 20,480 |
Remaining misses are arguments the graph has no pieces for. No "other" kind. rodata 1,356 bytes, ROM 28,156 (+1,252).
**Fit:** 122 of 126 images hold their table (mean 3.8 KB, largest 16.4 KB). r088, r090, r092, r099 boot without it and print bytes, as designed. r096 and r097 don't boot at all (T2). **Guesses:** 0 byte mismatches, right. Dev-city echoes about 0: the dev figure halved, the rest are in random graphs. 120-126 tables: 122. Chip cost not yet compared.

## T5 part A: teacher-forced against stock (stopped 16:08 on the lead's order; `results/trace/`, `results/t5a_check.json`, `results/t5a_flips.json`, `results/t5a_stock.log`)
The GPU is being cleared for Wednesday's target. The lead ordered no further GPU work after this trace, and it had more than 20 minutes left. **Done: 2 of 4 jobs.** r001-mixed and lim-lines-b did not finish: no trace saved, so unrun. **`path` and `cheapest` are in tiny-ten, limit lines are not traced on this firmware.** The first start failed in seconds: `set_text` missing in `stock_trace.py`, fixed.

| Stream | Positions | Owned | Differing | Stock wrong | Head mismatches | Smallest logit gap |
|---|---:|---:|---:|---:|---:|---:|
| tiny-ten: all ten functions, unknown function | 33,001 | 32,455 | 0 | 0 | 0 | 512 |
| c024 chases | 7,854 | 7,721 | 0 | 0 | 0 | 544 |

**40,855 positions, every one of 3,968 dims the same bf16 bit pattern on stock and the engine;** 0 sign-of-zero cases, 0 low-dim digests differ, 0 kept values not exactly bf16. Bit flips in the saved stock data: each caught exactly there (`results/t5a_flips.json`). Stock rates 14-20 chip/s, shared GPU.
The logit gap, 512 or more at owned text positions, is what the 2^22 gain was for. **Guesses:** 0 differ, 0 wrong, 0 head: right.

## Stopped
**T9 not run: pieces are out of this build (lead).** `pieces.py`, `test_pieces.py`, `drive_pieces.py`, `run_t9.sh` stay as written; `build/tok-pieces.elf` is unused. So whether the table brings the 7 back is unmeasured. Stock on the piece firmware is unrun too.
