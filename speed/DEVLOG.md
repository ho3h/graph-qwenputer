# X2.10 speed/ development log

Registrations are in `REGISTRATION.md`. Every number names its file. Shared GPU throughout unless a line says otherwise. Times are ET, 2 Nov 2026.

## S0 to S5 (10:16-11:15; shared GPU, Device Utilization 100% in ioreg with other jobs on it)
**Where the time goes on chain3's records** (`flowsim.py`, `results/flowsim.json`, 98 executor questions, 3,255 s): text 2,784 s, set-up 433 s, chip 38 s. Of 27,106 text steps: prose 16,798, calls 5,880, echo 4,428. 62% of text time is prose, and the runner throws it away in print mode.

**Limit lines retry for nothing.** 16 of 100 first lines are limit lines (`END`, `MULTI`, `NOCHANGE`). Chain3 retries on them; d/PLAN's proposed flow doesn't. All 16 finals equal the first line. Those retries are 20% of all text steps (21,641 of 27,106 left), with 0 finals changed.

**A 96-token cap changes output.** On the saved records it loses all 4 rescues (77 to 73): the rescues write 70-244 tokens of prose before the call. 256 loses 1. 320 loses none and leaves 69% of steps, and it is fitted on these records. So "33 s rather than 41" in `d/PLAN.md` isn't a free cut as stated. With `rvc/`'s prefill-and-note retry (no prose before a retried call), the cap stops mattering for `NONE`; on `chain4_fresh` the mean is 123 Qwen tokens, not 240.

**S0 (`results/s0_kernels.json`).** Dropping zero rows or columns: 0 elements differ. Batches up to 16: 0. Batches of 32 and 64: 51-165 elements per tensor, so a different kernel starts somewhere above 16. The head takes 13.4 ms a token; Qwen's rows only 5.3; rows and Qwen's dims 4.6.

**S1(a), load (`cmd`, `results/s1a_setup.json`).** 620 s in all: `from_pretrained` 4.9 s (it maps the files), compacting chip layers 65 s, `.to("mps")` **532 s**. `sample` shows 3.8% CPU, waiting in `mps_copy_` on the GPU's queue, one blocking copy per tensor, 580 tensors. The LaCie isn't the bottleneck: reads came from page cache at 8.4 GB/s. D's table doesn't count load: 37 runs × 9 minutes is 5.5 hours on a busy GPU.

**S1(a), set-up.** Machine, prompt, lock, snapshot and engine start are together under 0.2 s. Python isn't the problem. All of it is the prefill.

**S1(e), prefill from the engine's residual: bit-equal.** On 12 of 12 prompts, the engine's residual equals stock's in all 3,968 dims at every prompt position, and Qwen's layers from it give the same logits and states (0 differing). The chip layers can leave the prefill. 8.6 s to 3.6 s on these prompts, the same GPU conditions but not alternated.

**S1(f), split prefill: not bit-equal.** About 70% of logit elements and all 32 layers' states differ, first token the same on 36 of 36. See S8.

**S1(c) (`results/s1b_steps.json`, 680 steps, 14 questions, A/B alternating).** V0 0.163 s a step, of which encoding 0.043 s; the rest is waiting. V1 (head rows) 0.156 s, every bit equal. V2 (blocks) 0.143 s; a few elements differed because I moved tau's column in the head. Tokens against chain3: 0 wrong, 14 of 14 first tokens.

**S3 (`results/s3_batchdiag.json`).** With the head positional (dims 0 to tau), blocks equal dense: 0 elements on 400 prose tokens, 0.21 s to 0.17 s (18-20%). S4a (`results/s4a_prefill.json`): prefill through blocks equals dense on 4 of 4 prompts. So Qwen's layers need only the blocks, and the dense copies can go: 8.4 GiB rather than 18.7.

**S1(d), batches (`results/s1c_layers.json`).** 4.8 tokens/s at 1, 7.6 at 2, 13.3 at 4, 22.6 at 8, 31.7 at 16. No argmax changed in 16 steps. Logits differed from batch 1 in 75% of elements. S3 ruled out the 32 layers and rotary on one step's input, so I blamed the head at batch above 1. Row-by-row head.

**The batched runner diverged, and why (`results/s4_dev.jsonl`, `results/debug/`).** With that fix, 2 of 9 questions diverged at 2, 4 and 8 rows, deterministically; 1 row matched. `s4c`: first difference at step 0, layer 22, input equal. `s4d`: `post_attention_layernorm`, 2 elements. S5 (`results/s5_reduce.json`, `s5b_reduce.json`): **the fp32 mean over 3,968 dims gives different bits for a tensor of more than one row, in 28-30% of rows, at any batch size**, in every form tried. A row-by-row mean keeps the bits. The head-sized means and sums keep them up to batch 8; the l2 sum differs at 16. So 8 rows is the top size. With `rms_rows`, the two questions match at 2 and 8 rows. My S3 conclusion was incomplete: one step's check missed a rare rounding.

**S2, the chip layers from the checkpoint's own tensors (`wexec.c`, `wexec.py`, `wcheck.py`, `results/s2_fw.json`, engine 319b5ad27dd4).** First whole pass, no code change after it: **276,899 positions, every one with the same bf16 bits as stock in all 3,968 dims**, by `exec/check_trace.py`'s `compare`. 0 positions with any other chip dim nonzero. 0 gates, betas or decays outside saturation. 1,044,349 nonzeros read, the same count as `exec/results/weightcheck.json`. About 1,000 positions a second on one CPU thread (706-1,210 by stream), against stock's 13-48. It reads the weights, not the IR. It is a different execution path, not the model on its usual kernel: C on the CPU, HF's equations by hand. No negative control has run on it yet. Coverage has the same limit as `exec/`: about 60% of units.

`check_trace.py` ends in a bare `main()`, so importing it ran it, and my first dev run used `exec/`'s engine for a moment and overwrote only my own `results/s2_dev.json`. `wcheck.py` now takes its functions without that last line.

**Network stop.** The session lost its network about 11:30; `serve.py` and S4's stage kept running. Nothing restarted.

## S4: chain3's whole flow, batched (11:17-11:50; shared GPU; `results/s4_replay.json`, `results/s4_replay.jsonl`)
**Same tokens on 98 of 98:** every call's ids, every response's ids, final line, status, prose text, chip, Qwen and echo counts equal chain3's saved record, 80 on the batched path at 8 rows and 18 on chain3's own path, 0 lock errors. The guess was 65%. So the runner's chain3 path reproduces yesterday's run bit for bit in tokens too, on a differently loaded GPU.

Alternating under the same conditions, three rounds, chain3's path against the batched path: 5.7, 6.0, 5.5 against 26.1, 16.5, 23.0 text tokens a second, prefill included. Over the three rounds: **5,006 tokens in 863 s against 19,900 in 924 s: 5.8 against 21.5 tokens/s, 3.7×.** 48 s a question against 13 s, on different questions of the same draw. The guess was 3-5× in tokens/s. Batched wall includes the prefill, which is serial: 239 s of 924 s, plus my Python.

The batched path drops the head-argmax check at owned positions. It keeps the reference lock. It doesn't run a stock sample, and neither do any of chain3's executor questions.

## S7: flow changes on the batched path (`results/s7_flow.json`, `s7_flow.jsonl`; shared GPU)
Limit line ends the turn, 320-token cap, echo through Qwen's layers only if a retry follows. **98 of 98 finals and scores equal chain3's**, first calls all equal, 0 lock errors. 12,414 text steps against 27,106 (46%, as `flowsim` said). 2,857 echo tokens never reached Qwen's layers. 977 s, 10 s a question: 357 s prefill, 579 s steps. So at this point the prefill is the largest single piece per clean question. The cap's 320 was chosen from these same records.

## S10: copies to the GPU (`results/s10_copy.json`)
The guess was wrong. Blocking copies aren't the cost: 1.4 GiB took 9.5 s the first time, 0.09 s after, and non-blocking 0.05 s. What S1's sample caught was the first touch of file-mapped pages, reading the LaCie (USB) by page faults inside the blit. So the load's 532 s is the disk, at 27-150 MB/s, not the GPU queue. The earlier note in this log blaming the queue is corrected here. My dd at 8.4 GB/s read a part already cached.

## S9: whole questions with the chip layers on the checkpoint's tensors (`results/s9_wexec_path.json`, `s9_wexec_path.jsonl`; shared GPU)
**32 of 32 the same as chain3:** every call, response, final, status and count. 125,942 chip tokens in 85.9 s, 1,466 a second, with Qwen on the GPU beside it. 0 flags, 0 residue, 0 values outside saturation. Its prompt residuals came from it too. So on these 32, Qwen stock-kernel on MPS plus the checkpoint's chip tensors run in C answers exactly as chain3 did. Stock modules ran on neither side of this comparison except through chain3's own executor record, whose engine has its own stock comparison: **this path has not been compared with stock on free decoding.**

## S8: a shared prefix for the prefill: a finding, not a win (`results/s8_prefix.json`, `s8_prefix.jsonl`; shared GPU)
All 98 prompts share their first 373 of about 580 tokens. Restoring that prefix and prefilling the rest takes 1.32 s against 3.14 s alternating. **It changes output: 66 of 98 questions exactly the same; 3 finals differ, 2 scores flip, 4 first attempts differ, prose differs on 24.** So it fails the rule. It also measures what a pure rounding change does to Qwen, at no change in weights or tokens fed: 32 of 98 transcripts move, 3 of 98 finals. That's the noise floor seen from a new side, and it says any kernel or dtype change on Qwen's own arithmetic must be checked by tokens and will often fail. If a future gate were frozen with prefix reuse from the start, it would be one more kernel choice, not an error; that is the lead's and Theo's call.

## S11(a,b) (`results/s11_rows.json`)
A batched head equals row by row at 2, 4, 8, 12, 15 rows: 0 elements, 3.5 ms against 51 ms at 8. So S1(d)'s 75% came from the final norm's wide mean, as re-guessed, and my row-by-row head was unnecessary. The l2 sum, gated-norm mean and state sum hold through 15; at 16 the l2 sum and gated mean differ (16 × 32 × 128 = 65,536). So 15 rows is the top size.

S11(c) now uses the same 24 questions on both arms of a round instead of different ones, for a fairer A/B; the limit is unchanged.

## S11(c) (`results/s11c_rows.json`, `s11c_rows.jsonl`; shared GPU)
24 + 24 questions, each run at 8 rows and at 15, batched head on both: **96 of 96 runs the same as chain3.** Time doesn't separate them: 170 s (8) and 302 s (15) in round one, 325 s (15) and 358 s (8) in round two, on the same questions. The same arm moved by 2× between rounds, so the GPU's other work swamps it. 8 stays the default; 15 waits for a clean GPU.

`serve.py` stopped here, 13:0x, to give back its memory; S12 on is CPU until the block-only load.

## S12: wexec's negative control and profile (`results/s12_negative.json`, `s12_profile.json`)
S12(a) ran before its registration was committed, because of a failed `git commit` I didn't check; recorded in the entry. **9 of 30 single-weight doublings caught** on 12,000 positions of `tiny-ten`, against the guess of 8-15 and `exec/`'s 9 of 24 on a similar stretch. By array: `gate_proj` 8 of 12, `down_proj` 1 of 1; `in_proj_qkv` 0 of 12, and 0 of 5 in z, up and out. A changed weight on a unit or row these 12,000 positions don't exercise can't show. After restoring, 0 positions differ. So the same limit holds as `exec/`: this check sees what a stream exercises, and no more.

## S13: ballast memo (`results/s13_fw.json`, `results/s13_ab.log`; shared CPU)
Same bits, engine c3d187bfcdee. A/B alternating in separate processes on 20,000 positions of `lim-bounds`, 4 rounds: 2,042 against 2,376 positions/s, 1.16×, below the guess of 1.5-2×. The ballast's terms aren't the bulk. One round reversed: the Mac's other work is larger than this effect. Same-process A/B crashed at first because the two builds' structs differed in size (`p->L + l`); the old build then got padding, logic unchanged, as `abbd6100eb22`. Stopping here on wexec's single thread.

## S14: wexec free-running (`results/s14/`; shared CPU, load about 7)
c024's chases, circuit picking each next token, reference compared on every burst, 0 wrong: 2,370-2,665 chip tokens/s alone (median of 5), 5 processes at once 1,090-1,110 each, about 5,500 together. `exec/`'s engine alone 15,500. So wexec is about 6× slower than the engine, about 100× stock's 13-48, and 5 processes give 2× here, not 5×.

## Hold (13:59; lead's instruction: GPU at 100% across five jobs, no new GPU run until the normal-token and clean reading tests report)
**S15 didn't finish.** Its first arm, chain3's path, had just ended (`results/s15_slow_a.json`: 6 of 6 same, 4.49 tokens/s, shared, load 301 s). My chain then started the fast arm at 13:59:35, after the instruction had reached me and 14 s before I set the hold. I stopped it at about 30 s, with no question finished, and removed its empty output; the last arm refused by `HOLD` (`run.sh`). So S15's fast arm and second baseline are UNRUN.

From S15's smoke run on 8 questions before the chain (`results/s15_dev.json`, `fastrun.py`, warm file cache): **blocks only, from the internal disk: load 9.6 s against 620 s** (18.5 s on the stopped run), peak 11.4 GiB against 20.3, 8 of 8 the same tokens in chain3's flow, finals the same on 8 of 8 in S7's flow. S1 and slow_a loaded the merged weights in 620 s and 301 s. Block file 8.0 GiB, 252 s to build, in my scratch; the LaCie stays read-only.

**S16 is UNRUN.** Registered, code committed, held.

**Phase D table** (`phase_d.py`, `results/phase_d.json`), arithmetic on shared factors: 86.8 hours to 20.0; 12.9 without D3's two rows, which Theo dropped as a requirement.

## S15 finished (14:15-14:53; shared GPU, load average up to 29; `results/s15_fast.json`, `s15_slow_a.json`, `s15_slow_b.json`)
From a new process, blocks from the SSD: load 22.6 s, peak 11.7 GiB driver. **Chain3's flow: 98 of 98 the same tokens, 1,343 s, 20.2 tokens/s.** S7's flow: 98 of 98 finals and scores, 907 s, 9.3 s a question, 37% prefill. Chain3's own path before and after: 4.49 and 4.02 tokens/s, 6 of 6 same both times; load 301 s from the LaCie, 43 s from the SSD. So 4.7×, though only roughly alternating. Guess on load was under 60 s: right.

## S17: `fast.py`, proofs on the normal-token firmware (`results/proofs/`; shared GPU, other jobs on it throughout)
**P2, `print-chain3`, `tok.elf` 541e9ec9:** 32 of 32 fast at 8 rows the same as `drive_slow`, alternating on the same questions. Stock sample 2 whole questions, 9,627 positions, 0 mismatches, 0 head mismatches, tokens equal. **Speed: 7.46 against 4.30 tokens/s, 17.6 against 30.6 s a question, 1.7×.** Below the guess of 3-4×, and well below 4.7× on the byte firmware. These are 8-question runs in fresh processes, about 130 tokens a question: prefills are serial, each process first fills its token table in Python, and rows thin out at once.

**P3, flags:** 32 of 32 first calls, lines and finals equal P2's. 1,908 text steps of 3,479, 309 s against 487 s. Its proof entry leans on P2's stock sample.

**P1, `read-t6`:** stopped by the lead's instruction at 38 of 50: **38 of 38 same as tok's T6 records** in every segment. 12,888 tokens in about 1,300 s against T6's 2,030 s on those 38, about 1.5×; no stats saved, since the run was stopped. No stock sample, **no proof entry**, so it still runs slow. P4 and P5 not run.

**The lock isn't the gap** (`results/lockprof.json`): 0.02-0.06 s a call.

**Limit stop and the retry note:** see `results/limit_stop_note.json`. 18 of 100 on `chain4_fresh` hit a limit line, all at the first line, never after a note. So on saved data the two don't meet; the case is unmeasured. A limit line after a note-led retry would end the turn with no second try. On t8's firmware, where a refusal gets no note and no retry, the case doesn't arise in `print-one`.

## S18: both flows proved on t8's final firmware (`results/proofs/clean/`; shared GPU)
`clean.elf` 278e96aa on `x210-tok`. `print-one` and `read-one`: 32 of 32 same as the slow path each, on 16 dev cities, 8 limit lines, 8 hard. Stock lockstep 2 questions each, 5,669 and 8,664 positions, 0 differ, 0 head mismatches, tokens equal. Entries in `proofs.json`. Guess 85%: right. Speed in `print-one_speed.json`, `read-one_speed.json`.
