# Round 15 critical review

Recounts are mine, from saved rows.

## The band

- **Inside the model.** "Model's own layers", no server and nothing trained hold (`t8/fw/edit.py:220-226`; `t4_qwen_tensors.json`). "Loads the map" doesn't: blocker 2.
- **Reroutes.** `r6_walk`: 6 calls, 149,813 positions, 0 differ. `r6_journeys`: 15 of 15. Holds; see 6 and 7.
- **New lines.** `z3c`: 21 steps, 148,381, 0 differ. `z3b`: 3 of 3. Holds.
- **Exact answers.** `stock_d1m0-2`: 300 unique questions, 1,640,598, 0 mismatches. 300 right; alone 1 of 100. Numbers hold, framing doesn't: blocker 1.

## Blockers

**1. "On a 300-question exam run whole on the real model, all 300 printed answers were right."** `exam/R1.md:21`: the new 100 "confirm the rule rather than test it hard; the page must say so." Line 34 calls the 53 "close to re-scoring". The page says neither. Line 7: the generated 100 couldn't refuse either. Fix: "After one fix. 200 of the questions couldn't hit the failure it fixes, and it was fitted to refusals among the other 100."

**2. "A small script outside the model loads the map."** `exam/AFTER.md:46` says such wording "undersold" the driver. `edit.py:220,231`: it reads the machine's token off the layers and limits Qwen's vocabulary. Fix: "loads the map and routes tokens", as the thread says.

**3. Round 14's first blocker is still open.** Logged out: GitHub 404, Hugging Face 401. The page, README and thread 6 call them available. Fix: publish first.

## Should fix

4. **The band omits the tie and the reply.** `nyc_r1_d1m_score.json`: tool 300 of 300. `nyc_r1_d1r_score.json`: Qwen's reply 225 strict, 286 generous; on the 100, 78 and 99. The page admits the bars' mixed marking but gives no reply score. Fix: add both.

5. **Thread 4: "A 300-question exam then ran on the real weights."** It finished 04:32, before r6a's 15:28, on `ad1abcc6`, with no closures; r6a used `3d66be35`. The T line is `06767ab3`, so the band spans three builds unsaid. Fix: "An earlier build's 300-question exam ran on the real weights. On this build, one conversation has."

6. **r6c and r6d have no written result.** README:187 points to AFTER.md "under r6"; neither is scored there. README:237 shows old-rule 14 of 14 beside the band's 15. r6c: 573 of 1,000 sets, 2,292 routes, 0 differences, stopped at its limit. Fix: add rows, stating the partial.

7. **"15 test trips".** AFTER.md:82 and README:237 say showcase. `draw_r6.py:27` closes only unique names, and each sentence ends like the worked turn (`journeys_run.py:38`). 193 stops share names. Fix: "15 trips I chose".

8. **Executor.** README:36 "with the graph-qwenputer in Qwen's layers": `t1/score.json` says `executor`. The FAQ says "I say which", yet 2,395, the blackout and the choice counts have only one general sentence. Fix: label each.

9. **Misses unlabelled.** README states three. Unstated: V2 8-10 got 0 (AFTER.md:123); B 40-120 got 10 (:10); r6b (:295); r6e's four turns (:303); r3-r5 costs (:200-219). The stopped first attempts of r6e (:277) and Z3 (:228) are on neither page nor README. No miss is described falsely. Fix: one list in the README.

10. **README:250 "it hasn't been repeated on fresh wordings".** `gaslight2/all.jsonl` holds 36 such conversations, stopped by Theo (AFTER.md:193). "Hmm, are you certain?" kept 3 of 6. Fix: say so, unscored.

11. **Thread 2 "I wrote graph firmware"**, against the footer's "Claude Code wrote most of the code". Fix it, and LinkedIn.

12. **"Large language models get lost", "models are catastrophically bad".** Every row is Qwen 3.5 4B, and 10 of 600 has reasoning off. I found no X2.10 exam on another model. Fix: "Qwen gets lost".

## Minor

- "A separately built second machine": `exam/mach.py` runs the same ELF, so it checks the CPU, not the graph logic. `check/walk.py` hardcodes the old map, and `bundle.sh:52` omits r6a's rows.
- "this takes minutes": r6d's worst route is 226,375 tokens, about an hour.
- `t4_qwen_tensors.json` compares with `x210-rvc`; I found no saved comparison with Qwen's own release.

## Holds up

Live page equals `web/index.html`. No in-progress wording remains; round 14's 2-15 held. All 496 closure counts and blackout figures match `r6_all`. No-driver 6 of 6 holds. A row's `result` comes from the reference stream (`edit.py:191`), but token equality is enforced (:153-156).
