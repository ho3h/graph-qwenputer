# Revision r1, pre-run review: critic (2 Nov)

Read: `exam/R1.md`, `exam/REGISTRATION.md`, PATH.md 24-33, commit 4ed129d292's code, `go_r1.sh`, `p_r1.sh`, `r1.sh`, and what they call. No model or GPU run. CPU checks used `reflib`, `generate_shared` and the saved rows. `t8/fw/r1.sh` was still running (at `labels`), so its last three steps are unseen.

**The code rule is sound: I found no firmware/reflib disagreement and no path that overwrites a frozen result. The blockers are in the registration and the run script, and five must be fixed first. All five are short edits.**

## Blockers

**1. The stock job doesn't exist, and its three questions aren't chosen.** `exam/R1.md:23`, `:28`; absent from `exam/go_r1.sh`.
No script runs it, and `go_r1.sh` ends without it. `R1.md:28` makes "0 not differing on stock" a stop, so that stop can't fire. "Three shared-name chases from the new 100" names no selection rule, so they could be picked after seeing the results. Its order against `exam/x_nyc.sh` (3.5 hours of GPU) and the exams is also unset.
The budget doesn't add up: 25,000 / 18 × 1.5 = 2,083 s, about 35 minutes, not "about 1 hour".
Fix: choose the three by seed now, write the script, state the order, and state one limit in seconds.

**2. A proof miss has three different outcomes.** `exam/R1.md:15`, `exam/R1.md:28`, `exam/d1m.py:168`.
- `R1.md:15` says "a miss runs slow and says so".
- `R1.md:28` says any mismatch in the proofs stops r1.
- `d1m.py:168` is `assert fast.proof(fl)`, which crashes.

`prove.py --add` refuses a miss, so the assert is what happens. `go_r1.sh` then doesn't stop: it spends up to 3,150 s on the host before `score_d1m.py` fails on the missing rows, and the stop reads "D1m bar missed or void". That is a harness failure in the only revision. A slow run also wouldn't fit the stated budgets.
Fix: delete "a miss runs slow", and add a proof check at the top of `go_r1.sh`.

**3. The script's preconditions aren't enforced, and `exam/FREEZE_r1.json` doesn't exist.** `exam/go_r1.sh:2`, `:7`; `t8/fw/r1.sh:14-17`.
- `go_r1.sh:7` stops without the freeze file. Nothing in `R1.md` says what it lists or when it's made.
- It has to be hashed after `p_r1.sh`, because that edits `speed/proofs.json`.
- "Needs t8/fw/results/r1 clean" is only a comment.
- `r1.sh`'s header says it stops at the first failure, but `tablecheck`, `labels`, `fuzzfw` and `closures` have no `|| exit 1`.
- `fuzzfw` exits 1 on any mismatch, so the 80 known cases make it exit 1 every time. Nothing compares the classes, so "any mismatch beyond the 80 known fuzz classes stops r1" (`R1.md:15`) isn't implemented.

Fix: a small check reads `results/r1/*`, compares fuzz classes against `t8/fw/results/writes_fuzzfw.json`, and exits non-zero. `go_r1.sh` calls it. The freeze lists `build_r1/writes.elf`, `R1.md`, `go_r1.sh` and every changed file.

**4. "The real test" has no way to fail.** `exam/R1.md:20`, `:28`, `:33`.
The new 100 are called the real test, but the only bar is machine against host, and the host now runs the same rule. If Qwen got 60 of 100, the bar would pass, nothing would stop, and only a prediction would be missed. `REGISTRATION.md` says this bar tests little, and `R1.md` doesn't repeat that. A pass line can only be added before the run.
Fix: register a reading now, not a bar. For example: "under 90 of 100, or more than 2 clean wrong, means r1 is not adopted, whatever the bar says." Repeat that the bar tests little.

**5. The revision's main safety cost has lost its prediction.** `exam/R1.md:35`, `:12`; `exam/REGISTRATION.md:51`.
The frozen E1 predicted "false closes that move the answer" (2-7 of 15). `R1.md:35` drops it, and this is the number r1 makes worse. In the frozen run, 7 of 13 false closes were saved by the refusal on the start, and 3 moved the answer silently. On r1's actual draw (I ran `edit_draw.py` to the scratchpad), a false close on any of the 15 on-route traps moves the answer, assuming a right call, and none would be refused. 15 of the 30 traps start on a shared name. `R1.md:12` only mentions a wrong line, not this.
Fix: add the prediction, with the frozen 3 of 13 beside it, and say in `R1.md` that the rule trades refusals for silent moves here.

## Should fix (same edit)

- **The machine exams never reach the new rule.** All 600 D2m chases and all 500 D4m paths start from handles (checked in `exam/items/nyc.json`), so they test only for regressions. The rule's first run on New York's real labels is D1m, on the executor with no reference machine beside it. Add a CPU unit before D1m: all 694 shared label-and-line pairs through `exam/mach.py`'s `Pair`, with reflib beside it.
- **The fast proofs can't fire the rule either.** The practice cities share no names. In D1m's stock sample, seed 20261103 over 300 gives one shared question (index 221, id 910021), and it's chance that it's there. `R1.md` should say so.
- **Machine differing from host isn't a stop.** `machine_equals_host_tool` is only reported. Up to 2 points (6 rows) of firmware/reflib disagreement on the new path would pass the bar. Add it to `R1.md:28`.
- **Which firmware ran isn't saved for the machine exams or E1.** `exam/run_machine.py` and `t8/fw/edit.py` save no ELF hash. With no name starts in D2m or D4m, losing `T8_R1` would look like a pass. `t8/fw/closures.py:100` writes "writes.elf" whatever ran. Save the hash.
- **Gate on the wrong file.** `exam/d1m.py:161` checks the frozen `nyc_score.json`, so D1m's own "machine exams first" check passes on the frozen result. `go_r1.sh` covers it only when run in order. Point it at `nyc_r1_score.json` under `T8_R1`.
- **A prediction that can't hold.** `R1.md:34` says "3 to 6 of 5-8" stop lines. The draw has 11 gold stop lines: 5 generated and 6 new. Fix the denominator.
- **What carries r1's executor results.** `exam/x_nyc.sh` runs the window on the frozen ELF `bcf1…`, and r1's rows are on `ad1a…`. `REGISTRATION.md`'s stock bar says "or the executor can't carry these results". `R1.md` should say that window doesn't cover r1's firmware, and that only the sample and the stock job do.
- **Name-cleaner limit, undisclosed.** "86 St station" on a shared name stays `NONE` in both implementations. That matches, but `R1.md`'s wording suggests it narrows. It was 0 of the frozen 53.

## By question

**1. Firmware and reflib: no disagreement found.**
- Both count open nodes with the exact name, then open nodes where the first leg is non-empty. Both narrow only at k>1 and on=1.
- Handles skip the rule on both sides. Writes apply first on both sides.
- `eff_any` follows the same splice as `eff`.
- A cleaned name finds no exact match, so it gets `NONE` on both sides.
- `lr[0]` and `plan[0][0]` are the same leg.
- Part `r1` matched 4,800 of 4,800. I replayed its random draws on reflib, and the branch does fire: 631 narrowed (341 with writes in the call), 1,822 still ambiguous, 1,505 `NONE` on " station".
- Rule gap, not a disagreement: closing every other node with a name makes k=1, so the chase starts there whatever the leg, and can print a stop line from the wrong platform. That's frozen behaviour, and E1 closes only unique labels, so the exams don't reach it.

**2. Overwrites and reads.** No overwrite found.
- All r1 output paths are new.
- `prove.py --add` replaces only an entry with the same ELF and flow, so frozen proof entries survive. It does change `speed/proofs.json`.
- `T8_R1` reaches the subprocesses: exported in `go_r1.sh`, inherited by `r.sh`, not touched by memguard.
- `tokrun.py` and `fast.py` both pick `build_r1`, and `fwb.py` builds there. `edit_run.py` goes through tokrun.
- There's one reflib copy, so host and `same_as_host` get the rule.
- The ELF hashes match `R1.md`, and the frozen ELF is intact.
- Seven paths in `FREEZE.json` now differ by design (`check_freeze.py` run), `speed/proofs.json` will be the eighth, and `x_nyc.sh` runs through two of them (`lib/reflib.py`, `t8/fw/tokrun.py`). With the flag off they behave the same by reading, but that isn't tested.
- The one frozen read is `d1m.py:161`, above.

**3. `generate_shared` is honest but easy.**
- Gold is by handle, so it doesn't depend on the rule. The rule on names gives gold on 100 of 100.
- It isn't rigged: only 4 of 694 label-and-line pairs have two nodes on the line (36 St on the R, 7 Av on the B, each direction). All 228 shared-name starts among the file's 400 chases have exactly one.
- It's slightly harder than the file: first leg up to 4 stops (file 1-3), and 6 stop-line golds (file 0).
- Coverage: 94 distinct name-and-line pairs, 49 of the 76 shared labels. 11 of the 100 reuse a pair from the 53.
- But it repeats the frozen flaw in a new form: by construction it can't hit `AMBIGUOUS`, and a right call is automatically right. The same template gave 100 of 100 last time, and Qwen's call was right on all 200. So it measures Qwen's line-writing on a template it already writes without error. It's a confirmation, not "the real test". And the rule was built on this one city: the relabelled and rerouted cities remain UNRUN.

**4. Post-hoc disclosure is good, with gaps.**
- The header, the "no bar missed" line and the E1 wordings note are plain.
- `REGISTRATION.md` allows a revision "after a miss", and this is a prediction miss, not a bar miss. `R1.md` shows the facts but never says that's a reading of the rule. Say so to Theo.
- The "same bar" is now on 300 pooled rows. Also report it on the 200 alone.
- E1's new pairing means any change against the frozen E1 mixes the rule with the draw. Say so.

**5. Predictions.**
- The 200 are already known. I recomputed from saved rows: 53 of 53 calls give gold under the rule, so 147 + 53 = 200 if the calls repeat, and the same call on all 200 was already seen. "The 53 become right: 50-53" isn't a prediction. Label it re-scoring, and don't count it as evidence.
- The new 100's 85-98 is wide on the low side, as 200 of 200 right calls put a miss rate near 2%. It also excludes the likeliest result, 99-100.
- "Bar passes: 95%" can't be judged from one run and tests little.
- "Chip tokens on a handle start: unchanged" may be false, since `chase_start` runs `trim` and `parse_handle` before `node_or_print` on every start. I didn't measure it. It can be checked row by row against `exam/results/nyc/`, and a miss is harmless.
- The D1m, host, D1r and E1 budgets are ample: frozen D1m took 1,094 s for 200 questions, about 5.5 s each, against 9 s budgeted.
