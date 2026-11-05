# X2.10 exec/ development log: a Mac executor for the chip layers

Acceptance is `REGISTRATION.md`, not edited here. Every number names its file. Times are ET, 1 Nov 2026. All speed figures in this log before the
"clean" section are from a shared Mac (other X2.10 jobs on the GPU and CPU); each says so.

## Design note (22:55, before the build)

**What the circuit is** (`results/circuit_stats.json`, from `stats.py`): 2,918 IR dims, 11 layers (22 sublayers), 196 value heads, 42,114 FFN units.
Per token the sparse dot products have 522,851 `b` nonzeros (20,386 distinct `b` forms, 230,000 nonzeros once shared within a level), 52,826 `a` nonzeros
(39 distinct forms; most units read the constant), and about 270,000 head query/key nonzeros. A unit whose gate `b` is not positive adds nothing, so its `a`
is never needed. State is 196 x 128 x 128 fp32, 12.8 MB, of which a token touches a few rows.

**Baselines on this Mac, shared machine, not acceptance figures:**

| Path | Chip tokens/s | File |
|---|---:|---|
| vendored `fastexec.Executor(sparse=True)`, torch CPU, 1 thread | 170.8 | `results/bench_torch_cpu.json` |
| the same, torch MPS | 67.2 | `results/bench_torch_mps.json` |
| stock modules, MPS (rvc) | 20.8-47.68 | `../rvc/results/m2_teacher_a.json`, `m2_teacher_b.json` |

So MPS is worse than CPU here: 22 sublayers of small dispatches per token, and the GPU is shared. Sparse torch on CPU is about 26x short of 4,600. A Metal port would still pay one
command-buffer round trip per token (tokens are sequential; only separate streams batch), so it is not attempted. TorchScript runs the same torch kernels and cannot remove the dispatch cost.

**What I will build:** a small C engine (`engine.c`, a shared library, loaded with ctypes) that interprets a flat table compiled from the IR (`compile_ir.py`), rather than generated straight-line C:
- a table keeps 300k+ terms in cache-friendly arrays and compiles in a second; 42k units of straight-line code would be megabytes of cold instructions per token, and the table can be corrupted on purpose for the negative control;
- within a sublayer every distinct `b`, `a`, query and key form is evaluated once; a unit's `a` is used only if its gate is positive; `v` and `z` columns are evaluated only when the head actually writes or reads;
- lag windows hold only the dims a conv tap reads (about 400 dims), not 3 x 2,918 per layer.

**Arithmetic and format.** Upstream's executor is fp32 with `.to(bf16)` at the gate, the up factor, their product and the residual add; its check (`chat.py` `generate`, `execcheck.py`) compares `keep.to(bf16)` with the HF view by `==` at the kept dims on chip tokens and over the whole `hc` on text tokens. `==` hides `-0` against `+0`, and the HF side there is NVIDIA in compacted bf16, not MPS. The stock model here is HF bf16 on MPS, where rounding may differ and subnormals may flush. So:
- the engine computes in fp32 with the same bf16 rounding points as the HF MLP (gate, up, product, MLP output, residual add), via bit operations, no `-ffast-math`, no FMA contraction;
- acceptance compares **bit patterns of the bf16 residual over all 3,968 dims at every position**, against a saved stock trace from MPS (`stock_trace.py`), and reports `-0`/`+0` and any tiny residue separately rather than rounding them away. It also reports whether each fp32 kept value was exactly representable in bf16, so the cast hides nothing;
- values the IR marks as allowed to round (`tiny`, counters at 2^-90 and below) are the known risk. If they reach the exit residual on stock, that comes back as a measured difference.

**Range guard.** silu equals relu only at 0, >=18 and <=-104. The engine flags any gate outside that range and any multi-hot read that is not equal-valued, instead of quietly being wrong; `--verify` treats that as a stop.

**The check runs from a saved trace.** The stock residual is saved once per plan (`plan_accept.json`, fixed before any executor result: tiny with all ten functions, then limit graphs from `rvc/test_m1.py`, then c024, c025, r001). Any executor build can then be replayed against it with no 20 GB load. A firmware or circuit change needs a new stock trace.

**Speed.** A single-thread estimate from the nonzero counts is 100-200 microseconds a token, so 4,600 looks possible on one core, and independent streams can also run in separate processes. That is an estimate until `speed` results exist.

## Build (22:55-23:40)

All figures in this section: shared Mac, load average 20-41, another project and several X2.10 jobs on GPU and CPU. Not clean.

**Engine.** `compile_ir.py` turns the IR into tables; `engine.c` is an interpreter of them; `cexec.py` builds and drives it (clang 23, `-O3 -mcpu=native -ffp-contract=off`, no fast-math). Peak 1.8 GiB (`mem.log`, per process including the tokenizer); the state itself is 12.8 MB.

**Against the IR, no weights** (`test_ir.py`, `results/test_ir_dev.json`): every one of 2,918 IR dims at every one of 9,833 positions of a tiny stream equals `ir.evaluate` (exact float64, with its own `check=True`): 0 dims differ, engine flags none. Re-run after each engine change below; that is a dev test, not acceptance.

**Speed steps, same stream** (`speed_dev0/1/2.json`, 42,721 positions of tiny's first 8 calls, all teacher-forced in C, single thread):

| Step | Microseconds per position | Positions/s |
|---|---:|---:|
| table interpreter, each distinct form once per level (`speed_dev0.json`) | 469.2 | 2,131 |
| plus shared sums, Paar's algorithm: 495,252 terms become 103,526 terms and 5,407 sums (`speed_dev1.json`) | 303.4 | 3,296 |
| plus runs of equal length evaluated without a per-form branch, the constant folded (75,563 terms), only positive gates and channels visited, fewer roundings per active unit (`speed_dev2.json`) | 181.2 | 5,519 (median 5,165) |

Sums are moved only across dims that cannot hold tiny counters, and only with power-of-two ratios, so each moved sum stays exact.

**Free-running, one chase stream** (`results/speed_c024_shared.json`, c024's 3 chases, 16,002 chip tokens, 215 text tokens, the circuit picking each next chip token, load average 41 at the end): median **4,462 chip tokens/s**, best 4,617. Same run, per conversation: `core.snapshot` 35 ms once warm, the 1,700-token prompt through the circuit 354 ms once warm, restoring a saved state 0.8 ms. The prompt cost matters for a machine-only run of many short conversations; it can be cut by restoring a saved state, which is not built.

**Saved trace check** (`check_trace.py`): compares bf16 bit patterns over all 3,968 dims at every position with `results/trace/*.npz`, dims below `chip_dims_offset` through a digest of the checkpoint's embedding row.

**Not tried:** generated straight-line C. The table interpreter already reached the target region, so that comparison was not run.

## Dev results before the full acceptance (to 23:55)

All on engine 69df37e88e2c, shared Mac. The trace was partial at the time; the acceptance figures are in their own section below.

- **Machine-level long run** (`results/test_ref.json`): the engine free-running against the reference machine on 164 calls (dev questions across graphs, plus one 1,000-node hub, whose `cheapest` is 468,672 chip tokens): 2,501,086 chip tokens, **0 wrong, 0 engine flags**, 4,849 chip tokens/s. One call was skipped for going over 400,000 records and one graph does not fit the image. This does not touch the weights.
- **Several processes** (`results/speed_c024_5procs_shared.json`): 5 engine processes at once on c024's chases, each 3,752-3,948 chip tokens/s, **19,310 in all**, load average 28-30, peak 8.81 GiB for the group.
- **Same tokens, first two questions** (`results/same_tokens_tiny.json`): tiny q0 and q1 on the executor against the stock free-running records `../rvc/results/m3_stock/tiny.jsonl`: every Qwen and tool segment identical (679 tokens), the same chip count per call (5,531 and 19,113 chip tokens), the same final text and status, lock clean, 0 head mismatches. Whole-question time 51 s against 448 s and 95 s against 1,209 s, under different loads. Chip side 3,496 and 5,804 tokens/s; the text side is still Qwen on MPS, about 4.4 tokens/s here (`results/drive_exec/tiny.jsonl`).
- **The verify mode stops on a wrong executor** (`results/negative_verify.json`): one weight changed from 256 to 258 in a second engine; `--verify` stopped at position 130 of q0 with dims 2759, 2767-2771 listed. Peak 20.39 GiB under the 32 limit (`mem.log`).
- **Negative controls on 12,000 positions of the partial trace** (`results/negative_tables_dev.json`): of 24 single-number table corruptions, 9 reached the residual and were caught. The other 15 did not change any residual in that stretch. So this check catches what a stream exercises: a wrong DIV unit or a wrong state row that is never read is invisible until something reads it. Coverage of the streams is what limits it, not the comparison. For that reason `--verify` also compares every head's state at the end of a verified conversation.
- **Flipped stock bits** (`results/negative_flips_dev.json`): 6 single bits flipped in the saved data (kept dims and the low digest), each caught at exactly that position and nowhere else.
- **A build with no bf16 rounding** (`results/negative_noround_dev.json`, engine e701d858b57a, `-DNO_ROUNDING`): **not caught** on the first 15,000 positions of tiny-ten. No value there needed rounding, so those rounding points are not yet exercised by this stretch. To be repeated on the whole trace; if it still passes, the rounding is unexercised on these streams and that goes in the report.

**00:00: the verify run was killed by memguard, as designed.** `mem.log`: "KILL: system free 19% < 20% (group at 20.1 GiB)", after 467 s and before any question finished (`results/drive_verify/tiny.jsonl` is empty). Its own footprint was 20.34 GiB under the 32 limit. The system level fell from 56% to 19% in under 2 minutes as other jobs loaded. I had set `--min-free-pct 20` for my own runs, above the default 15, so that mine goes first and other jobs' guards don't trip. I am keeping 20 and waiting until the system is at 45% or more before the retry.

## Verify mode and same tokens (to 00:50)

Engine 69df37e88e2c, shared Mac. Stock path figures here are shared too.

**Periodic comparison, as it would run at a gate** (`results/drive_verify/tiny.jsonl`, `results/drive_verify.log`, `--verify seed:7:10000:3600` on tiny's questions 0, 1, 2, 4, 5, 6, 11; the order 6, 11, 5, 0, 4, 1, 2 saved first in `tiny.jsonl.verify.json`): q6 and q11 ran through stock chip layers in lockstep, **16,145 owned positions in 1,310 s, 0 residual mismatches** over all 3,968 dims, 0 kept values that were not exactly bf16, and **every head's state equal at the end of both** (`end_state_diff` 0 small, 0 big). The remaining five questions then ran on the executor alone. Peak 20.39 GiB (`mem.log`).

**Criterion 3, same tokens against stock** (`results/same_tokens_stock.json`): 4 of 4 questions identical: every Qwen and tool segment (1,014 tokens), chip tokens per call (40,705 in all), final text, status; lock clean and 0 head mismatches both ways. Sources: q0 and q1 against the stock free-running records `../rvc/results/m3_stock/tiny.jsonl`, q6 and q11 against the stock path that drove `drive_verify`. Chip tokens themselves are compared through the reference lock and per-call counts, not saved one by one on the stock side.

Further, not against stock: q2 (984 tokens, 31,976 chip, ends at the 12-call cap), q4, q5 on the executor equal `../rvc/results/m3_compact/tiny.jsonl`, which is compacted chip layers (`results/same_tokens_verify_vs_compact.json`, 7 of 7 with q0, q1, q6, q11).

The four questions compared: 42-95 s on the executor against 448-1,209 s on stock, different loads. Text tokens now dominate: Qwen on MPS is untouched.

## Acceptance (02:30, engine 69df37e88e2c, firmware ELF c46d1607)

**Criterion 1, exact: met.** `results/acceptance_check.json`, `check_trace.py` against `results/trace/*.npz`: **260,597 positions, 258,530 of them owned; every position has the same bf16 bit pattern as stock in all 3,968 dims.** 0 positions differ, 0 dims differ, 0 sign-of-zero cases, 0 low-dim digests differ, 0 stock residue outside the kept dims, 0 kept fp32 values that were not exactly bf16, no engine flags. Stock here is HF modules, bf16, MPS, sdpa, nothing compacted (`stock_trace.py`).

| Stream | Positions | Owned | Differing |
|---|---:|---:|---:|
| tiny-ten: all ten functions and an unknown function | 69,846 | 69,300 | 0 |
| lim-bounds: OVERFLOW, 255 and 256 steps, 8-leg chase, 17 legs (TOOLONG) | 62,243 | 61,882 | 0 |
| lim-full: FULL after 256 added edges | 7,858 | 7,803 | 0 |
| lim-collide: a 12-bit hash collision | 8,022 | 7,941 | 0 |
| lim-lines: SPEC result lines, **partial, 52,123 of 107,236: the 3.5-hour limit stopped it** | 52,123 | 51,587 | 0 |
| c024 chases | 16,217 | 16,084 | 0 |
| c025 chases | 10,650 | 10,560 | 0 |
| r001: follow, path, neighbours, cheapest | 33,638 | 33,373 | 0 |

Stock itself in those traces: 0 wrong tokens, 0 fired where not owned, 0 head mismatches. The later calls of lim-lines (from about the 14th of 27) were not traced. The 1,000-node hub was not traced on stock; it ran only against the reference. The trace check does not re-run stock, so a firmware or circuit change needs new traces.

**Format: no difference found.** Upstream's check compares `keep.to(bf16)` with `==`, kept dims only on chip tokens, against an NVIDIA compacted view. This one compares bit patterns of the full residual against MPS stock. Every kept fp32 value was already exactly bf16, so the cast hides nothing and needs no tolerance.

**What rounding does.** A build with no rounding at all (`-DNO_ROUNDING`) also passes (`results/negative_noround_tinyten.json`, `negative_noround_limbounds.json`). It is not caught because on these streams it is not wrong in the residual. Rounding does act: in `results/diag_rounding.json` it changed a value 29,398,312 times of 8,957,110,688 over 802,909 chip tokens, for example a gate of 894 to 896, but no result depended on it, which fits the IR's own check that the bf16 value equals the exact one. Rounding stays in the engine, because a tiny counter past its bound could depend on it, and no stream here shows that.

**Criterion 2, can fail: met, with a limit on what it can see.**
- `results/negative_tables_tinyten.json`: 24 single-number table corruptions chosen by seed 0, run over the whole of tiny-ten: **10 caught, 14 not** (they reach no residual on that stream). The earlier 12,000-position run caught 9 (`negative_tables_dev.json`).
- `results/negative_flips_tinyten.json`: 8 of 8 single-bit flips in the saved stock data caught, each at exactly that position.
- `results/negative_verify.json`: `--verify` stopped a wrong engine at position 130.
- **The limit, measured** (`results/diag_coverage.json`, the plan's streams): 11,268 of 20,388 gates ever fired (24,417 of 42,114 units), and 128 of 196 value heads were read, 76 written. A gate that never fires is only shown to stay off. This firmware never writes the digit-file or quotient heads and reads only part of the ROM, so the circuit's unused parts are not tested by this check. A firmware that reaches them needs its own check, which the registration already requires.

**Criterion 3, same tokens: met on 4 of 4 questions compared with stock** (`results/same_tokens_stock.json`, 1,014 segment tokens, 40,705 chip tokens, all tiny). No stock free-running record exists yet for c024, c025 or r001, so their free decoding has not been compared. At teacher-forced level their stock tokens and residual are in the table above.

**Criterion 4, speed: shared figures only, no clean figure.** c024 chases, free-running, chip side only, one thread:

| Conditions | Chip tokens/s (median) | File |
|---|---:|---|
| load average 41; another project, stock trace, several X2.10 streams | 4,462 | `results/speed_c024_shared.json` |
| load average 7; another project at 124% CPU, 4 other jobs | 6,629 | `results/speed_c024_lighter.json` |
| load average 6.5; same | 6,838 | `results/speed_c024_final.json` |
| 5 processes at once, load average 6.5 before they start | 25,562 in all, 5,078-5,151 each | `results/speed_c024_5procs_final.json` |
| 5 processes at once, load average 28-30 | 19,310 in all | `results/speed_c024_5procs_shared.json` |

**The 4,600 target.** One process reached it at load 7 and fell just short at load 41. **Estimate, not measured:** 66.5M chip tokens is 2.7 hours at 6,838/s on one process, and under 1 hour at 25,562/s if the run splits into separate conversations. Per-conversation start-up is on top: 232-354 ms for the 1,700-token prompt and 27-35 ms for the snapshot, about 1.2 hours in all if each of about 12,000 chases starts fresh on one process, unless a saved state is restored (0.8 ms), which is not built. No run of that size was made. The longest was 2.5M chip tokens against the reference (`results/test_ref.json`).

**Text tokens are unchanged.** The four questions compared take 42-95 s on the executor against 448-1,209 s on stock, and Qwen's layers on MPS are now most of that. A question-level gate is limited by them, not by the machine.

**Memory.** 20.70 GiB peak for a stock trace under the 32 limit, 20.39 GiB for the executor with Qwen, 1.76 GiB for the engine alone with the tokenizer, 8.81 GiB for 5 processes under the 12 limit (`mem.log`). One memguard kill, recorded above: my own 20% free-memory floor.

## Integration

- `chat.py` `ExecChat` wraps the vendored `RvChat` (stock modules, unchanged). `drive.py` is a copy of `rvc/drive.py`'s `run_question`. Its changes: a chip token runs as a burst on the engine with the lock checked over the burst; a text token's residual is built from the embedding row and kept dims and goes to `RvChat._qwen_step`; `--verify` runs stock and executor together and compares all 3,968 dims; records carry `ran_on`. Nothing under `vendor/` or `rvc/` is edited.
- `--verify all` or `--verify seed:S:MIN_OWNED:MAX_S`. A mismatch or engine flag stops the run with exit code 3.
- **The prompt's prefill still runs the whole stock model, chip layers included**, so loading is unchanged and a question-level run needs the same 20 GB.
- A sample is whole conversations, from their start. A window deep inside one long stream is not supported, since stock would have to run everything before it, or take a transplant of the executor's state, which is not built.
- Saved stock traces and question records are `.npz` and `.jsonl`, which the repo's `.gitignore` excludes: they are on disk in `results/`, not committed, about 1.3 MB in all.

## Not run
A clean speed figure with the Mac to itself. Stock free decoding on c024, c025 or r001. The rest of lim-lines on stock. A 66.5M-token run. The D161 reviews of this acceptance.

## New firmware (fw/build/fw.elf e908647b), started 02:32

The lead's request: the registered repeat after a firmware change, on `fw/`'s tighter firmware, plus the coverage gaps, within 4 hours. Same engine 69df37e88e2c, unchanged, booted through `CHIP_FIRMWARE` in `common.py`; `fw/` is only read, never rebuilt. Plan `plan_fw.json`: the earlier plan plus `lim-hub` (the 1,000-node hub) and `lim-lines-b` (the last 13 lim-lines calls, on a fresh machine, after a kill cost the first attempt's tail).

**Window verifier, a bug of mine, found by its own control (04:10-04:25).** `window.py` transplants the executor's state into the stock cache. `results/windows_blank_control.json`, 40 seeded points with every lag window blanked and then true: blank caught at 21 of 40, but **true also failed the end-state compare at 2** (93100, 415264), residuals equal. I treated this as a possible mismatch and diagnosed before anything else. `results/windows_diag.json`: 0 state differences right after transplant; the difference appears at the second token, always a store (`SS1`), and stock wrote a RAM row the executor had not (ram7 row 78, ram14 row 92). The cause is in `window.py`, not in stock or the engine: I filled only the lags that have a tap, but a conv window shifts, so a tap at lag 2 reads next token what sits at lag 1 now, and that slot held a stale value from an earlier run. Fixed: all three lags are filled for any channel with a lag tap. The earlier 21,000 window positions (`windows_hub_fw.json`, `windows_hub_fw_early.json`) passed under the bug because no store fell in their first tokens; the bug could only add false alarms there, but they ran on the old tool and are labelled so.

**Memory, and the lead's rule (04:33).** Four of my processes were killed on this firmware, all by my own 20% floor (`mem.log`): one at 03:30 and one at 03:33 when other jobs loaded, two at 04:31 when I had launched too many at once, which was my mistake. No other job's guard was involved, as far as `mem.log` shows; I did not read theirs. Finished jobs were saved; partial ones lost only their last flush. At 04:33 the lead asked for at most one stock-weights process at a time, none started under 35% free, while a sealed run is active. I stopped the hub trace, the executor-with-Qwen run, the old-firmware run and their queues, all three still loading, and left only `window.py` running. What remains runs strictly in sequence (floor raised to 25% for these). The executor-with-Qwen runs count as holding the weights, since they hold 20 GB.

**The repeat check on firmware e908647b, as of 05:20** (engine 69df37e88e2c, unchanged). The final total, with the hub, is at the end of this section.

| Stream | Positions | Owned | Differing |
|---|---:|---:|---:|
| tiny-ten: all ten functions, unknown function | 28,959 | 28,413 | 0 |
| lim-bounds: OVERFLOW, 255/256 steps, 8 legs, TOOLONG | 43,401 | 43,040 | 0 |
| lim-full: FULL | 4,410 | 4,355 | 0 |
| lim-collide | 3,728 | 3,647 | 0 |
| lim-lines, first attempt, killed at 25,000 of 38,413 | 25,000 | 24,321 | 0 |
| lim-lines-b: its last 13 calls, whole, on a fresh machine | 16,597 | 16,102 | 0 |
| c024 chases | 7,261 | 7,128 | 0 |
| c025 chases | 4,762 | 4,672 | 0 |
| r001 | 12,781 | 12,516 | 0 |

146,899 positions, 144,194 owned, every one of 3,968 dims the same bf16 bit pattern as stock on MPS; 0 kept values not exactly bf16; no engine flags. Stock in those traces: 0 wrong, 0 fired where not owned, 0 head mismatches. Together the two lim-lines runs cover all 27 calls, but lim-lines-b starts from a fresh machine, not from the state the first 14 calls leave (those 14 change no state).

**Free decoding through stock on c024, new firmware** (`results/drive_fw_verify/c024.jsonl`, `--verify all`, questions 100 and 201): 38,515 positions, 35,301 owned, every position compared over all dims, 0 mismatches, every head's state equal at the end of both. **Same tokens** (`results/same_tokens_fw_c024.json`): the executor alone gives the identical run on both: 3,856 segment tokens, 34,661 chip tokens, same chip count per call, same text, same status. Qwen's own results on these two: q100 ran out of budget after 11 calls, q201 answered wrongly. Those are Qwen's, and they are not scored here. **Stock free decoding on the old firmware was not run**: the lead's one-process rule came first, and I stopped it while it was loading.

**Windows deep in the hub** (`window.py`; the hub is 496,620 positions, 254,506 chip tokens for `cheapest` alone). On the fixed tool, `results/windows_hub_fw_fixed.json`: 12 windows chosen by seed 21, 1,000 positions each, from position 111,312 to 466,951: 12,000 owned, 0 mismatches, all end states equal. On the tool before the fix, `windows_hub_fw.json` and `windows_hub_fw_early.json`: 21,000 more positions (20,950 owned), same result.

Controls for the window check (`results/windows_blank_control_fixed.json`, 40 seeded points, 6 positions each): every lag window blanked is caught at 21 of 40 points; the true windows fail at 0 of 40. The other 19 points had no write depending on a lag in those 6 positions. A corrupted engine weight is caught 2 positions into a window (`windows_hub_fw.json`, `negative_engine`). A single blanked lag slot was not caught in 200 positions (`negative_lag_slot`): a lag window lasts 3 tokens, so one slot often means nothing.
A transplant checks the window, not the road to it. The road is covered by the reference lock (tokens) and by a state error reaching a residual or the end-state compare inside a window.

**Tokens per call, through the executor, reference lock on every burst** (`results/fw_calls_fw.json`, `fw_calls_rvc.json`, `plan_fw.json`'s calls on both firmwares, 0 wrong on both):

| Function | Calls | New mean | Old mean | Old / new |
|---|---:|---:|---:|---:|
| find | 9 | 1,328 | 2,914 | 2.19 |
| follow | 12 | 8,058 | 11,591 | 1.44 |
| chase | 10 | 2,953 | 5,830 | 1.97 |
| neighbours | 4 | 1,726 | 4,641 | 2.69 |
| path | 8 | 25,060 | 28,442 | 1.13 |
| cheapest | 6 | 44,012 | 83,330 | 1.89 |
| close | 5 | 879 | 2,587 | 2.94 |
| reopen | 4 | 854 | 2,397 | 2.81 |
| link | 4 | 2,702 | 6,737 | 2.49 |
| unlink | 3 | 2,093 | 5,715 | 2.73 |
| unknown function | 2 | 478 | 1,650 | 3.45 |

These are limit-heavy graphs, the hub among them, so the means are not a typical mix. c024's chases: 2,325, 2,251, 2,470 against 5,282, 5,155, 5,565. Plan total 635,486 chip tokens against 1,039,622. On dev questions, the new firmware against the reference (`results/test_ref_fw.json`): 452 calls, 2,512,116 chip tokens, 0 wrong, no flags, 10,480 chip tokens/s, load average about 5-7 with another project, my stock traces and other jobs running. One call skipped for its length, one graph does not fit.

**Chip tokens per second, new firmware, c024 chases, free-running, shared Mac, no clean figure:**

| Conditions | Chip tokens/s (median) | File |
|---|---:|---|
| 1 process; load average 5, another project at 130% CPU, one stock trace, system daemons | 10,762 (best 12,290) | `results/speed_fw_c024_light.json` |
| 1 process; load average 5.5, another project, 4 other Python jobs | 5,491 (best 9,356) | `results/speed_fw_c024.json` |
| 5 processes; load average 5 before, 8 after | 27,015 in all, about 5,400 each | `results/speed_fw_c024_5procs_light.json` |
| 5 processes; load average 6 before, 17 after | 20,392 in all | `results/speed_fw_c024_5procs.json` |
| chip side inside whole questions, q100 and q201, Qwen on MPS beside it, load average about 5 | 11,821 and 11,690 | `results/drive_fw_exec/c024.jsonl` |
| all plan calls, including the hub, load average 42 | 3,581 | `results/fw_calls_fw.json` |

The swing between the first two rows at about the same load average shows how much the machine's other work moves this number. Per conversation: snapshot 17 ms, prompt through the circuit 131 ms once warm (`speed_fw_c024_light.json`).

**Final total for firmware e908647b (06:22): exact on all it ran.** `results/fw_acceptance_check.json`: **276,899 positions, 274,110 owned; every position has the same bf16 bit pattern as stock on MPS in all 3,968 dims.** 0 positions differ, 0 sign-of-zero cases, 0 low-dim digests differ, 0 stock residue, 0 kept fp32 values not exactly bf16, no engine flags. That is the table above plus the hub from its start, 130,000 of 496,620 positions (129,916 owned), stopped by the time limit (`stock_trace_fw_hub.log`, exit 124; `path`'s 37,837 chip tokens and part of `cheapest`). Separately through stock, not in that total: 38,515 positions of c024 free decoding and 33,000 in hub windows, 0 mismatches. Adoption is the lead's decision after review.

**Coverage on this firmware** (`results/diag_coverage_fw.json`, 10 traces): 11,572 of 20,388 gates ever fired, 25,059 of 42,114 units; 128 of 196 value heads read, 76 written. Digit-file and quotient heads are still never written. Slightly more than the old firmware's 11,268 gates (`diag_coverage.json`), mostly because of the hub. For review at the end of the round.

**Not run:** on stock, the hub past position 130,000 except in windows; a clean speed figure; a negative-control table run on this firmware's traces (the checker and engine are the ones controlled above, and the window and verify controls ran on this firmware); on the old firmware, the rest of lim-lines, the hub and stock free decoding on c024, set aside under the one-process rule. Peak memory 20.70 GiB (earlier firmware's trace), 20.42 GiB here (`mem.log`).

## Whole-table check and coverage difference (2 Nov, round 2 critical review, finding 4, conditions 1 and 2)

Registered first (`REGISTRATION.md`, commit 047141d471; revision commit 21cd158342). CPU only, no MPS, no forward pass, nice, under memguard at 12 GiB, no kill. `engine.c`, `cexec.py` and firmware unchanged. Development, not reviewed.

**A real difference, for the lead (`results/weightcheck.json`).** 250 embedding rows of 484,800 differ between the checkpoint and the token features the engine uses: ids 248070 to 248319, exactly `<|reserved_0|>` to `<|reserved_249|>`, as guessed. Only byte-feature dims (`tb*.b*`, 79 dims) differ: the merge read the source tokenizer (248,070 tokens), so those rows hold zeros, while the executor and the reference read the merged tokenizer and see the bytes of the string. So if one of these ids entered a stream, stock and the engine would hold different text bytes. It would matter where the firmware reads text, as in a call. None occurs in the saved traces or their prompts: 0 of 537,496 positions. I have not tested what would happen, and nothing is masked in the check. A fix would touch `cexec.py`, a driver or the merge, so it is the lead's call.

**A. Tables against the IR (`tablecheck.py`).**
- Real tables, `results/tablecheck_fw.json`, `tablecheck_rvc.json`: **0 differences; every one of 490,468 numbers read** (`unread` empty): 42,114 units, 20,388 gates, 11,879 channels with 16,504 uses, 196 value heads, 4,939 value columns, 10,883 head outputs, 5,353 shared sums, 362 lag dims. About 1 s a pass. No unit could not be checked.
- **Both firmwares load the same tables:** sha256 3180f8ff…, `program-1f9794d5bab0.npz`. The compiled tables don't depend on firmware. The firmware's numbers are head state rows, loaded at run time.
- ROM rows against each ELF by a separate small reader: 0 of 8,595 words differ on fw, 0 of 8,334 on rvc, all in heads rom0-rom4. The DROM rows equal the machine's image and contain the ELF's read-only data. This leaves out registers, RAM, counters and digit-file rows, which `core.snapshot` builds for stock and engine alike.
- **Where it shares code:** the IR objects (`core.build`), numpy, the `.npz` itself and `ref.rom_word`. It repeats the file key and two rules that have no other source (`vh_nrows`, `h_always`). Same author, reading `engine.c`. It does not import `compile_ir.py` or `cexec.py`.

**Catch rate.**
| Run | Cases | Caught | File |
|---|---:|---:|---|
| First, seed 20261102 | 1,030 | 1,029: **the registered "all" bar missed by one** | `results/tablecheck_corrupt_run1.json` |
| After the one revision, same cases | 1,030 | 1,030 | `results/tablecheck_corrupt_20261102.json` |
| After the revision, new seed 20261103 | 1,030 | 1,030 | `results/tablecheck_corrupt_20261103.json` |

The miss moved one `v_expr` pointer from expression 12172 to 12173. Both are the same constant, 2^24, with no terms, so the engine computes the same value. The check had listed the orphaned number as unread without failing on it. The revision fails on any number no entry reaches. All 30 earlier cases are caught in every run, against 12 of 30 by streams then (10 of 24, 2 of 6); their recorded old values all match this program. Each 1,030 includes those 30, and at least 10 cases in each of the 38 arrays.

**B. IR against the merged weights (`weightcheck.py`): it can be done on CPU, and it was.** 288 s, peak 1.19 GiB, tensors read lazily with safetensors, no model object.
- **The 11 chip layers: 0 differences** over 1,044,349 nonzeros and 45,070 units (42,114 IR units plus 2,956 for slot handover, exit clears and ballast), order-free for units, by position for heads. No negative zeros. Fixed tensors have their values. Final norm: chip dims -1, code dims one gain, tau 2^60.
- **Shared code:** `emit.allocate`, because the slot map isn't saved in the checkpoint. Its 1,652 handovers pass a separate lifetime check (0 bad), and `chipformer.json`'s slot count, code, tau and mu dims match it. It repeats emit's handover and exit rules, which are what it checks. It does not import `emit_layers`.
- **Embedding:** all 484,800 rows' chip dims compared, by direct feature calls. 484,550 equal; the 250 above differ. Chip rows and padding: 0 differ. This also tests the merge's linearity shortcut for large families on every token. Qwen's own 2,560 dims and Qwen's layers are not read here.
- **Controls:** 60 of 60 seeded single-weight changes caught (27 on nonzeros and 33 from zero, not the registered half and half, because a draw landing on an empty tensor went to a zero; 10 of the 60 on embedding rows). `weightcheck.py`'s exit code ignored the embedding when this ran (it exited 0); I fixed that line afterwards, so a rerun exits 3. The saved results are the run's.

**C. Coverage difference (`covdiff.py`, `covdiff_test.py`, `results/covdiff_test.json`).**
- **The baseline, `results/cov_baseline.json`:** 18 saved traces, 537,496 positions, each replayed through the patched engine and compared with the saved stock kept bits: **0 positions differ** (`results/cov/*/tally.json`). 11,563 of 20,388 gates, 24,916 of 42,114 units (59%), 5,136 of 11,879 channels, 132 value heads read, 76 written. Windows and free-decoding runs on stock have no saved trace of tokens in that form and are not counted, so the baseline is on the small side.
- **The reported figure counted prompts.** `diag_coverage.py` left its flags on through `start()`, and the prompt is not compared on stock. On fw, 11,572 falls to 11,507 compared; I guessed under 50 and it is 65. The union with rvc is 11,563. Reads are 128 on either firmware alone and 132 together.
- **Tests:** 18 of 18 saved streams give 0 new against the full baseline; leave-one-out equals separate set arithmetic in 72 of 72 cases; gates, channels and heads taken out of the baseline are listed exactly; a log from other tables is refused. On the command line: exit 0 on a saved stream, 1 on a finding, 2 on other tables.
- **A stream that should differ:** vendored `calc-bridge.elf`, 11 big-number calls, 38,881 positions: **1,652 new gates** (819 `div`, 576 `bn`), 242 channels, 10 heads read, 18 written, first at position 765, listed in `results/covdiff_calc_bridge.json`. Written heads as guessed, except only `quo0` of the quotient heads. These have not been run on stock.
- **The hub from its start, past where the stock trace stopped:** 496,620 positions: **11 new gates**, 382 new channels, 0 new heads, first at position 130,118, and none first fired inside the traced 130,000 (`results/covdiff_hub_whole.json`). By the rule, these are findings that need a stock window. The earlier hub windows may have covered some; they weren't logged, so that is unknown.
- **In a gate run:** `import covdiff` before `cexec`, `Cov(ex, label)` after `ex.start`, `save`, then `covdiff.py diff`. This rule is not yet wired into `drive.py` or any gate runner.

**What this closes, and what it does not.** For the units streams never reach, the tables now equal the IR and the IR equals the merged weights, exactly. Before, there was no evidence on them. It does not show:
- that the C loops do on those rows what this reading says, or that fp32 sums in the engine's grouping equal stock's matmul at values never seen. Rounding remains unexercised by these streams;
- that the circuit itself is right on those parts: that rests on upstream's tests;
- the next-token tables `cexec.py` builds at run time (`fam_kind`, `fam_base`, `fam_size`, `printable`, beyond the printable list matching `chipformer.json`);
- conditions 3 and 4 of the finding, which this work did not touch.

**Budget.** All under the registered estimates: real tables 3 s; each corruption run 410-520 s on 4 processes at load about 10; weights 288 s; baseline 157 s; tool tests 113 s. Peak 3.35 GiB for 4 workers.
