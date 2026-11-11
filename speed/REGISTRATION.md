# X2.10 speed/: registrations

Each measurement is written here, with its guess and budget, and committed alone before it runs. Results go in `DEVLOG.md` and `results/`. All on a shared GPU until the lead says otherwise, and labelled shared. Dev data only; `data/heldout/` is never read. Nothing here changes a bar or another folder's code. Budgets are not raised; a budget or memguard kill is a finding.

Environment for every run: `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 PYTHONDONTWRITEBYTECODE=1`, the qwenputer riscv venv read-only, under `../tools/memguard.py`, one process of mine at a time.

**What counts as a win.** A speedup counts only if the outputs equal the slow path's on the stated sample: the same tokens, and for real-weight changes every bit. Otherwise it is a finding.

## S0: kernel bit-equality on real weights (`kernels.py`)
**Question.** On MPS, bf16, on tensors read from the merged checkpoint: does a linear map give the same bits when (a) zero output rows are dropped, (b) zero input columns are dropped, (c) inputs are batched against one row at a time, and (d) the head is cut to Qwen's vocabulary rows? This decides which later candidates can be exact. Also times each on the shared GPU, A/B alternating.

**Sample.** Layers 11 (linear attention) and 25 (full attention), plus the output head. 64 input vectors: the first 2,560 dims of embedding rows of dev-prompt tokens plus seeded noise, zeros above.

**Guess.** Rows-only and head-rows equal. Batch equal, 60%. Dropping zero columns differs in some bits, 70%, since upstream's note says shorter sums round differently.

**Budget.** No measured rate for this script. Tensors about 4.7 GB at 90 MB/s from `m2` loads (52 s), plus 64 × 6 maps at the slow path's upper bound 0.2 s, ×1.5: about 3 minutes. Limit 300 s (`timeout`), memguard 28 GiB, floor 25% free.

## S1: where a text token's time goes, and which cuts keep every bit (`serve.py`, `s1_*.py`)
**Result of S0, for context** (`results/s0_kernels.json`, 64 inputs, 6 tensors): dropping zero rows or columns changed 0 of about 2.7M elements; batches up to 16 changed 0; batches of 32 and 64 changed 51-165 elements per tensor.

**Question.** On the merged checkpoint, Qwen's layers on chain3's questions, one process holding the model (`serve.py`, which takes each stage as a script, so a load is paid once):
- (a) Load, by phase. Per-question set-up by phase: machine, lock, prompt, prefill, snapshot, engine start, `empty_cache`.
- (b) One text step: time to encode against time to wait, layer by layer, head alone.
- (c) A/B alternating on the same tokens, with cloned caches, logits compared bit by bit at every step over Qwen's vocabulary, and tokens compared with chain3's saved calls: **V0** chain3's path (dense layers, full head, two argmaxes); **V1** head cut to Qwen's rows; **V2** Qwen's linear maps as nonzero blocks and the head as Qwen's rows on dims 0-2559 plus tau.
- (d) Batches of 1, 2, 4, 8, 16 on V0 and V2: step time, and row 0's logits against batch 1.
- (e) Prefill from the engine's residual, skipping the chip layers: residual against stock's over all dims at all prompt positions, final logits and every Qwen state against the stock prefill.
- (f) Prefill split into a shared prefix and the rest: logits and states against the whole prefill. Prefix lengths: the common tool block, and that rounded down to a multiple of 64.

**Memory note.** MPS's limit under the required ratio is 26.9 GiB (0.25 × 107.5). Chain3's path is 18.7 GiB and V2's blocks add about 8.4 GiB, so the chip layers are compacted on load (`fast.compact(qwen=False)`, exact on c024 at `rvc/results/m2_teacher_compact.json`, token-identical on two questions). V0 here therefore differs from chain3's in the prefill's chip layers only, and its tokens are checked against chain3's saved calls.

**Sample.** The first 12 executor questions of chain3's draw (`rvc/results/chain3/all.jsonl`), first attempt only, teacher-forced on their saved tokens (`<tool_call>` to `</tool_call>`, about 48 tokens each). Plus a free-running stretch of up to 200 tokens on 2 prose questions, for long context.

**Guesses.** (a) Set-up is mostly prefill, at least 2.5 s of the 4.4 s. Load is mostly reading the LaCie. (b) Encoding is at least half of a step; the head 10-15%. (c) V1 and V2 keep every bit, 70%; V1 saves 8-15%, V2 20-40%. (d) Batch 8 at 2-3 times a single step, every bit equal, 60%. (e) Bit-equal, 85%; saves 20-30% of the prefill. (f) Not bit-equal at the common length; at a multiple of 64 equal, 35%.

**Budget.** Load: slowest recorded 587 s (`rvc/DEVLOG.md`). Set-up 12 × 4.4 s. Steps: 12 × 50 tokens + 2 × 200, × 3 variants × 0.104 s (chain3's rate) = 312 s. Batches: 5 × 2 × 20 steps × at most 0.5 s = 100 s. (e) and (f): 12 prefills at 3 s and 6 more stock at 4 s = 60 s. So (587 + 53 + 312 + 100 + 60) × 1.5 = 1,670 s. **Limit: stages together under 1,700 s of work.** `serve.py` itself has a 4-hour `timeout`, memguard 32 GiB, floor 25% free; it holds the model idle between stages and is stopped when work ends.

## S2: the chip layers run from the checkpoint's tensors, against saved stock traces (`wexec.c`, `wexec.py`, `wcheck.py`)
**Why.** Stock chip tokens run at 13-48 a second. A chip token is 22 sublayers of small GPU operations on tensors of which 1.04M numbers are nonzero (`exec/DEVLOG.md`, weight check). The hypothesis: the rate is set by dispatching operations, not by arithmetic.

**What it is.** A C program that takes every weight from the merged safetensors, not from the IR or `exec/`'s tables, and does HF's `Qwen3_5DecoderLayer` forward in order with its bf16 rounding points, skipping only what zeros settle: zero weights, zero inputs, value heads with no weights, units whose gate is not positive. **This is a different execution path from stock modules on MPS, and is labelled so.** It reads the weights where `exec/`'s engine reads the circuit; it is not "the model running on its usual kernel".

**Test.** `wcheck.py` calls `exec/check_trace.py`'s `compare` unmodified, on firmware e908647b's traces (`exec/results/trace_fw`, 10 jobs, 276,899 positions): bf16 bits at every position, kept dims and low-dims digest. Added: a count of positions where any other chip dim is nonzero after layer 11, which must be 0. Counts of gates, betas and decays outside saturation are reported.

**Dev revisions.** The first runs will find my own bugs. Each is fixed and logged. The result that counts is a whole pass with no code change after it.

**Guess.** After debugging, 0 differing, 80%. Speed 2,000-5,000 positions a second on one CPU thread, shared Mac. Then the claim stays narrow: 276,899 positions; about 60% of units exercised, as with `exec/`.

**Budget.** No measured rate. Assume 500 positions/s, the low end of a sparse count of 1M terms × 2 ns: 276,899 / 500 × 1.5 = 830 s. Plus tables and tokens' rows 60 s × 1.5. **Limit 1,000 s a pass, memguard 16 GiB.** CPU only, no MPS; not run while a `serve.py` stage runs.

## S3: why batched rows differ, and the head fix (`stages/s3_batchdiag.py`)
**Result of S1 so far, for context** (`results/s1a_setup.json`, `s1b_steps.json`, `s1c_layers.json`; shared GPU, device utilisation at 100% from other jobs): 12 of 12 prefills from the engine's residual equal stock in all residual dims, logits and states. Split prefills differ in about 70% of logits and all states, with the first token the same. V1 equals V0 at all 680 steps. V2 equals V0 in tokens at all non-owned positions, but a few elements a step differ; my head moved tau's column. Batches: 22.6 tokens/s at 8 and 31.7 at 16, against 4.8 at 1, with no argmax change in 16 steps, but about 75% of logit elements differ from batch 1 at the same step, at any batch above 1.

**Question.** (a) Which operation changes bits between a batch of 1 and a batch of 2? Layer by layer on one question, then op by op in the first differing layer of each type, same inputs. (b) V2 with the head on dims 0 to tau (positional, not moved): equal? (c) V0 against V2-fixed on 2 long free-running stretches, 200 tokens of prose.

**Guess.** One op type, attention or the delta rule's reductions, 55%; a single fix possible, 40%. Head fix makes every non-owned position equal, 75%.

**Budget.** 4 steps × 43 layers × 2 at most 0.2 s = 70 s; 400 tokens × 2 paths × 0.2 s = 160 s; ×1.5 = 350 s. Model already loaded. **Limit 400 s.**

## S4: chain3's whole flow, batched, against chain3's saved tokens (`batchrun.py`, `stages/s4_replay.py`)
**Result of S3** (`results/s3_batchdiag.json`): on the same input at batch 1 and 2, all 32 Qwen layers and the rotary table are bit-equal, so S1(d)'s difference came from the head at batch above 1. Blocks plus a positional head: 0 elements differ on 400 prose tokens, 18-20% faster.

**Question.** A batched runner with Qwen's layers as blocks, one head per row, attention per row, prefill from the engine's residual, one chip engine per row: does it give chain3's tokens? Compared with `rvc/results/chain3/all.jsonl`: every call's ids, every response's ids, final line, status, prose text. How long does it take, against chain3's own path run alternately under the same conditions?

**Design.** Rounds, alternating: 6 questions on chain3's unchanged path (`chain2.run_question`, V0), then 24 on the batched path at 8 rows. Three rounds, then the rest on the batched path. Slow-path tokens are compared with chain3's too. Same flow: 2 retries, 768 budget, reference lock on. The batched path drops the head-argmax check at owned positions (`head_mismatch`; 0 in all of chain3) and no stock sample runs here; the 2 stock questions of the draw are left out.

**Also at the start.** Prefill through the blocks instead of the dense layers: bits against the dense on 4 prompts. It is adopted only if equal.

**Guess.** Same tokens on all 98, 65%; if not, the likely place is prose after many steps. Batched path over the slow path: 3-5× in tokens per second, about 2-3× per question, because prefills do not batch.

**Budget.** Slow: 18 questions at chain3's 33.2 s, at S1's rate 1.6× slower: 53 s each = 960 s. Batched: 80 questions × 4 s prefill = 320 s, plus 22,000 tokens at S1(d)'s 22 a second = 1,000 s. Sum 2,280 s × 1.5 = **3,420 s limit**. MPS 26.9 GiB limit, memguard 32 GiB. Model already loaded.

## S5: which reductions change bits between a batch of 1 and more (`stages/s5_reduce.py`)
**Result so far** (`cmd/s4dev`, `s4b`, `s4c`, `s4d`, kept in `results/s4_dev.jsonl`): the batched runner at 1 row gives chain3's tokens on the 2 questions tried; at 2, 4 and 8 rows, 2 of 9 questions diverge, deterministically. First difference: layer 22 at step 0, in `post_attention_layernorm` alone, 2 elements, with its input equal: the mean over 3,968 dims in fp32 rounds differently when the tensor has more rows.

**Question.** Over 2,000 real-valued rows on MPS: for each reduction Qwen's layers use (RMS mean over 3,968; head mean over 256; gated-norm mean over 128; l2 sum over 128; state sum over 128), do these shapes give the row-alone bits at batch 2, 4, 8, 16? And is there a form of the wide mean that keeps them?

**Guess.** Only the wide means differ, 55%. A flatten-and-index form that keeps bits, 30%; otherwise row-by-row means, which add ops but few.

**Budget.** About 8 forms × 2,000 rows × 5 ms = 80 s × 1.5. **Limit 200 s.**

## S6: the wide mean row by row, S4 rerun under the same registration
`rms_rows` in `batchrun.py` takes the mean over 3,968 dims per row (`results/s5b_reduce.json`: a batched mean differs from a row alone in 302 of 1,024 rows at any batch; row by row, 0. The l2 sum differs at batch 16 and not at 8, so 8 is the top size). 2 of 2 diverging questions now match at 2 and 8 rows. S4 runs as registered.

## S7: the flow changes, on the batched path, against chain3's finals (`stages/s7_flows.py`)
**Question.** Same 98 questions, 8 rows, with: a limit line ends the turn; an attempt ends at 320 tokens without a call; echo tokens skip Qwen's layers until a retry needs them. Same final line and same score as chain3? Text steps and seconds.

Cap 320 is chosen from `results/flowsim.json`: 96 and 256 lose rescues on chain3's records (4 and 1). So it is fitted on these records, and a fresh draw can only lower it; the flow change belongs to the lead, this only measures what it would cost and save.

**Print mode only.** These change what Qwen's layers see after the last line, so they don't apply to pass to Qwen, which is the default mode. They are not measured for that mode.

**Guess.** 98 of 98 same finals, 80%. Text steps 46% of chain3's (`flowsim`), about 12,500. Seconds per question about 40% of the same-flow batched path.

**Budget.** 12,500 steps at 22/s = 570 s, 98 prefills × 4 s = 392 s, ×1.5 = **1,450 s limit**.

## S8: a shared prefix for the prefill (`stages/s8_prefix.py`)
**Result so far.** Splitting a prefill changes logits and states (`results/s1a_setup.json`, about 70% of elements), with the first token equal on 36 of 36 splits. So this cannot be bit-equal. Prompts share their first 300 or more tokens across graphs (tools and header).

**Question.** Prefill the common prefix once, restore a clone per question, prefill the rest: same tokens as chain3 on all 98 questions, in chain3's flow? Seconds per prefill against the whole prefill, alternating on 12 prompts.

**Guess.** Most questions same, 1-5 of 98 differ, 70%, since the noise floor says small rounding changes do flip Qwen sometimes (wording corrected before running). Prefill about 55% of whole. If any question changes, it is a finding, not a win, on the rule above.

**Budget.** As S4's batched part, 2,000 s × 1.5 = **3,000 s limit**.

## S9: whole questions with the chip layers on the checkpoint's tensors (`stages/s9_wexec_path.py`)
**Question.** The batched path with `wexec` in place of `exec/`'s engine, 8 rows, first 32 questions of the sample: chain3's tokens? Chip tokens a second? Its prompt residuals also come from `wexec`.

**Guess.** 32 of 32 the same, 85%. About 1,000 chip tokens/s, so about 4 s a question beside 13 s.

**Budget.** 32 questions: 13 s × 32 / 8-row-share as measured = 420 s, plus chip 133k tokens at 1,000/s = 133 s (serial in a row), plus tables 100 s: 650 s × 1.5 = **1,000 s limit.**

## S10: blocking against non-blocking copies to the GPU (`stages/s10_copy.py`)
**Why.** S1's load spent 532 s in `.to("mps")`, 3.8% CPU, waiting per tensor. **Question.** 12 real tensors, alternating `.to("mps")` and `.to("mps", non_blocking=True)` then one synchronize. Bytes equal on a sample.

**Guess.** Non-blocking 3-10× faster on the shared GPU, 60%.

**Budget.** 1.4 GiB × 2 × 3 rounds at the S1 rate of 27 MB/s = 310 s × 1.5. **Limit 470 s.**

## S11: more rows, one head (`stages/s11_rows.py`)
**Why.** S1(d)'s 75% difference at batch above 1 is now better explained by the final norm's wide mean than by the head; S5 shows the l2 sum differing at batch 16, whose 16 × 32 × 128 is exactly 65,536 elements, so 15 may hold. **Question.** (a) A batched head at 2, 8, 15 against row by row on real normed vectors: bits. (b) l2 sum, gated-norm mean and state sum at 9, 12, 15, 16: bits. (c) If both hold: alternating 24 questions at 8 rows row-by-row head against 24 at 15 rows batched head, tokens against chain3, three rounds, 72 questions.

**Guess.** (a) equal, 65%. (b) 15 holds, 50%. (c) same tokens on all, given (a) and (b), 75%; 15 rows 1.3× tokens/s.

**Budget.** (a), (b) 60 s. (c): chain3's mix at S4's 21.5 tokens/s: 19,900 tokens = 925 s × 1.5 = 1,390 s. **Limit 1,500 s.**

## S12: can wexec's check fail, and where its time goes (`wneg.py`, `sample`)
**Breach, recorded.** This entry was written before S12(a) ran, but its commit failed on another agent's git index lock and I ran it anyway without checking. S12(a) therefore ran before its registration was committed. The guess and budget below are unchanged from what was written then. `gitc.sh` now waits for the lock and stops on failure.

**Question.** (a) 30 seeded changes to wexec's weight tables (one nonzero doubled, drawn by array and index), on the first 12,000 positions of `tiny-ten`, by the same compare: how many are caught? The same limit as `exec/`: a weight never read on the stream can't be caught. The state is reset per case. (b) `sample` on a whole `r001` pass: which lines take the time.

**Guess.** (a) 8-15 of 30 caught (`exec/` caught 9 of 24 on 12,000). (b) Most of it in the two norm passes and gate accumulation, a few places.

**Budget.** 12,000 positions at 1,000/s × 30 = 360 s × 1.5 = 540 s; tables 100 s; (b) 30 s. **Limit 700 s**, memguard 16 GiB, no MPS.

## S13: wexec with the ballast's partial sums memoised (`wexec.c`, `wexec.py`)
**Result of S12** (`results/s12_negative.json`, `s12_profile.json`): 9 of 30 single-weight changes caught on 12,000 positions, the same order as `exec/`'s 9 of 24; none of the 12 changes in `in_proj_qkv` caught on that stretch. Time on `r001`, region timers, a lighter moment: 3,326 positions/s, 21% q, k, v, z, a, b sums; 23% gate sums; 25% active units; 13% conv; 12% norms. The rate is 3× what S2 saw on the same stream, so the Mac's other work moves it a lot.

**Change.** The ballast columns are first in every sum. If all ballast dims hold one normed value, start from a stored partial sum, computed from the same weights and that value, instead of redoing it each sublayer. Same terms in the same order; each stored value is what the loop would reach at that point. It re-checks the value at every sublayer and falls back otherwise.

**Question.** Whole-trace pass as S2: 276,899 positions bit-equal? A/B alternating with the S2 build on `lim-bounds`, same process.

**Guess.** All equal, 95%. 1.5-2× faster. 

**Budget.** Pass: 276,899 at S2's 1,000/s = 277 s, tables 100 s, × 1.5 = 570 s. A/B: 3 rounds × 2 × 20,000 positions at 1,000/s = 120 s × 1.5. **Limit 800 s**, memguard 16 GiB, no MPS.

## S14: wexec free-running, 1 and 5 processes (`wspeed.py`)
**Question.** Chip tokens a second with the circuit picking each next token, c024's chases, 1 process then 5 at once, as `exec/speed.py` measures its engine, for D2m's arithmetic. Lock on every burst, against the reference. Same stream on `exec/`'s engine alongside, one at a time, for the ratio.

**Guess.** 2,000-3,000 alone; 8,000-12,000 for 5; `exec/`'s engine 3-5× faster.

**Budget.** 16,000 chip tokens × 5 passes × 6 process-sets at the 1,000/s floor = 480 s, ×1.5. **Limit 720 s**, memguard 16 GiB, no MPS.

## S15: the fast path from a cold process: blocks only, from the internal disk (`stages`/`fastrun.py`)
**Why.** S10 shows the load is the LaCie. S3 and S4a show Qwen's layers need only the blocks, and S1(e) that the chip layers aren't needed for the prefill. So a run needs only Qwen's blocks, 8.4 GiB rather than 18.7.

**Question.** One script: write Qwen's blocks once to the internal disk (scratch, 8.4 GiB, removed after; the LaCie stays read-only); load from there; run the 98 questions, 8 rows, chain3's flow; same tokens? Load time? Peak memory? Then the 98 questions with S7's flow. Alternation: chain3's unchanged path can't run in this process, having no dense weights; so its rate comes from one more run of it right before and after, 6 questions each, in its own processes, with its 10-minute load counted apart.

**Revision (14:15, lead's instruction, before the rest ran).** Blocks live at `~/Models/x210/x210-rvc-blocks`, not scratch; slow_b reads `x210-rvc` from the SSD too. The file was just moved within one disk, so the OS file cache may still be warm; no purge is run. Slow_a stays as run at 13:59, from the LaCie.

**Guess.** Load under 60 s, 90%. Peak 11-13 GiB. Same tokens on 98, 90%. Per question within 10% of S4 and S7 at like load.

**Budget.** Block file: 18.7 GiB read at 27 MB/s, the worst seen = 710 s, × 1.5 = 1,060 s. Batched 98 questions: 1,060 s from S4's 21.5 tokens/s, plus S7's 980 s = 2,040 s × 1.5 = 3,060 s. Chain3's path: 2 × (620 s load + 6 × 53 s) × 1.5 = 2,800 s. **Limit: 3,000 s for the fast process, 1,500 s each for the two others. Memguard 28 GiB fast, 32 slow; 25% floor.**

## S16: stock HF chip-layer modules on MPS, in batch (`s16_stockbatch.py`)
**Why.** T7's "the summit can't be met whole on stock" rests on one row at 13-48 chip tokens/s. Rows are independent streams, and chip arithmetic has no rounding to keep. If S1(d)'s batch gain holds for chip layers, a route test stays in HF modules on the GPU, closer to "runs in the model" than `wexec`.

**Question.** HF decoder-layer modules on MPS, linear maps as blocks (dense also, at 1 row, for scale), teacher-forced on `exec/`'s c024 firmware trace, 2,000 positions, rows 1, 2, 4, 8, 15, one stream repeated per row. Rate? Each row's kept dims against the trace's bits, and every other chip dim zero. Prompt prefill and `hf.inject`, then repeated across rows.

**Guess.** 30-50 steps/s at 1 row; 8 rows about 15-25 steps/s, 150-200 row-tokens/s. Every bit equal, 85%; the wide mean may differ, but the bf16 cast hides it there.

**Budget.** 5 row counts × 2,000 steps at the slowest 13.6 steps/s = 735 s, plus load 60 s and prefills: 830 s × 1.5. **Limit 1,250 s**, memguard 16 GiB. Runs after S15 ends.

## S17: the standard runner (`fast.py`, `README.md`, `proofs.json`), proved per firmware and flow
**Rule the runner enforces.** A firmware (by hash) and flow with no proof entry run slow, on stock modules, and say so in every record. Proofs are same tokens against a slow path on a stated sample.

**Proofs registered, normal-token firmware (`tok.elf`, `x210-tok`):**
- **P1, read flow (`read-t6`):** ten tools, Qwen's own words. Fast at 8 rows against tok's own T6 records (`tok/results/t6/`, its `drive.py`, the slow path), every segment, on every question T6 has finished when this runs, up to 50. Then against `drive_slow` on 5 of them, to check my slow driver.
- **P2, print flow (`print-chain3`):** chain3's draw, first 32 questions. No slow record exists on this firmware, so `drive_slow` runs them, one block alternating with fast at 8 rows on the same questions: 8 and 8, four rounds. That A/B is the speed on the new firmware.
- **P3, print + flags (`--speed-flags`):** the same 32 on fast. Against P2's records: every first call and line equal; finals equal.
- **P4, retry note (`print-chain4`):** 32 questions from `rvc/results/chain4_draw.json`, fast and `drive_slow`. The note on this firmware is the fixed sentence in normal tokens, unlike chain4's bytes, so the first check against `rvc/` runs on the byte firmware:
- **P5, byte firmware (`fw.elf`, `x210-rvc`):** `print-chain3` on the 98 (S15 ran it through `fastrun.py`; here 16 through `fast.py`, against chain3's saved tokens). `print-chain4` on 32 against `rvc/results/chain4_fresh/`.
- **Stock sample:** 2 whole questions per flow on the normal-token firmware, lockstep over all dims, plus tokens against the fast record.

**The limit stop and the retry note** (`results/limit_stop_note.json`, from saved records): on `chain4_fresh`, 18 of 100 questions reach a limit line; all 18 at the first line, all 18 finals equal it, so no note ever preceded one, and stopping there saves 36% of text steps. Saved data has 0 cases of a note retry ending on a limit line, so this says nothing about that path. The flag's stated risk stands: a limit line after a note-led retry ends the turn, with no second retry. P4 with flags reports any such case.

**Guesses.** P1 same on all, 80%; the prefill on this firmware is new. P2 same on 32, 85%; 3-4× tokens/s, shared. P3 all finals same, 85%. P4 same, 80%. P5 same, 90%. Stock samples 0 mismatches, 90%.

**Budget.** Measured rates: T6 at about 100 s for its heavy questions, 33-41 s on the 50 (tok's registration) → P1 fast at 21.5 tokens/s on at most 50 × 1,200 tokens = 2,800 s; slow check 5 × 100 s. P2: 16 slow × 53 s + 16 fast × 13 s = 1,060 s. P3: 32 × 10 s = 320 s. P4: 32 × 53 s + 32 × 13 s = 2,100 s. P5: 16 × 13 + 32 × 13 + 32 × 53 s = 2,300 s. Stock: 4 flows × 2 × 300 s = 2,400 s. Blocks 250 s. Sum 11,190 s × 1.5 = 16,800 s across separate processes, each under 4 hours. **Limits: P1 4,700 s; P2 1,600 s; P3 500 s; P4 3,200 s; P5 3,500 s; each with its stock sample 900 s more.** Memguard 28 GiB fast, 32 slow and stock, floor 25%. One process of mine at a time; running jobs untouched.

**What's not proved by this.** Whole-gate behaviour; other tools than those flows use; `path` and `cheapest` at NYC's size; a stock window for units never fired (`exec/`'s condition 2 isn't wired in here either); the strict cleaner firmware, which needs its own proofs. Results stay dev, unreviewed.

## S18: proofs on t8's final firmware (`prove_clean.py`, `proofs_clean.sh`; supersedes S17's remaining P1, P4, P5 for now)
**Instruction (lead, 16:05):** on the GPU, only the final build's fast-runner proofs and the real-weight sample; S16 and the clean rate skipped. P1 was stopped at 38 of 50 (38 of 38 same as T6, `results/proofs/p1_partial.json`, no proof entry, its stock sample unrun). P4 and P5 were stopped before starting.

**Firmware.** `t8/fw/build/clean.elf`, sha256 278e96aa…5581, on `x210-tok`, machine `clean`. **Flows.** `print-one` and `read-one`.

**Sample, fixed here.** 32 spent dev questions: `ctrl/results/arm4_draw.json`'s first 16 dev cities (about 40% read a name, says t8); 8 random chases from `rvc/results/chain4_draw.json` whose `answer_text` is a limit line; first 8 of `t8/results/panels.json`'s hard panel. Not t8's F3 draw. Split in two halves, alternate items.

**Test.** Each flow: slow half 0, fast half 0, fast half 1 plus 2 stock questions, slow half 1. Fast against slow: every token, line and final. Stock sample: whole questions, stock and engine in lockstep over all dims, head check, tokens against the fast record. A proof entry needs all of it. The sample reports how many read a name and how many hit a limit line; if either is 0 the proof doesn't cover it and says so.

**Guess.** Same on 32 of 32 in both flows, 85%. Stock 0 mismatches, 90%. Print-one 1.5-2× per question, read-one 2-3×, shared.

**Budget.** Measured on `x210-tok`: slow print 30.6 s a question, fast 17.6 (`results/proofs/p2_*`); read 73.9 s slow (`tok/results/t6`), fast 34 s (P1's 38 in about 1,300 s). 16 × (30.6 + 17.6) × 2 = 1,540 s; 16 × (73.9 + 34) × 2 = 3,450 s; stock 4 × 400 s = 1,600 s; loads 8 × 50 s = 400 s. Sum 7,000 s × 1.5 = 10,500 s. **Limits per arm in `proofs_clean.sh`; 4-hour rule holds.** Memguard 28 GiB fast, 32 where stock runs.
