# X2.10 round 5: steel-man review (D161)

Claude (steel-man subagent), 3 Nov 2026. Covers the runs round 4 asked for (`exam/AFTER.md`) and the draft page. Written without reading this round's critic. No model was run. CPU only.

## Verdict

**The machine's gain over Qwen is larger than the page says, but the page compares it with the weakest baseline available.** The page is ready for Theo to review, and it isn't ready to publish. One sentence on it isn't backed by saved rows, and a visitor has nothing to check. The best next run is Qwen with the map in its prompt, not the sealed city, because it's the one run that could change what the page claims.

## What I checked

**Recomputed from saved rows:**
- **Qwen alone.** All 600 rows of `alone.jsonl` with my own marking: 10 strict, 12 generous, as saved.
- **The join.** The r1 D1m rows and the 300 in `after/other` have exactly the same 600 ids and the same question text as `alone.jsonl`. The printed line equals the gold on 600 of 600, all with one call.
- **Replies.** I classified all 600 r1 replies in `nyc_r1_d1r` and `after/other_r`.
- **Stop lines.** I read the 11 replies in `after/stops`. Only `900065` says it stopped.
- **The window.** All 51 jobs in `window_check.json` sum to 337,526 positions, 0 differing. `window_flip.json` shows 8 of 8 caught. `remainder.json` gives 21 of 11,589 gates and 169 of 5,418 channels left.
- **Sums.** 67,813 + 15,765 + 337,526 = 421,104. In all, 449,761 + 15,765 + 337,526 = 803,052 New York positions, 0 differing. The second sum takes round 4's 449,761 as given.
- **New York's graph.** 496 nodes and 76 names shared across 193 of them. 175 of the 300 start on a shared name, and none of the 300 has a stop-line answer.
- **Page details.** Qwen's 32 layers from its config, and the 85 exit units from `exam/REGISTRATION.md`. `nyc:198` ran in lockstep, 14,052 positions, on `bcf1a1dc`. I ran the demo's JavaScript logic for every closure and compared it with round 4's independent walker (`walk.py`).

**Read, not recomputed:** `other_score.json`'s stock sample and host agreement, which I took as saved; `X2.7/report.md`; round 4's false-close counts, which the page repeats.

**Not done:** I didn't view the page in a browser, or run it at phone width.

**Not opened:** the graph and question files of `nyc-cf` and `nyc-relabelled`. I read their rules in `data/README.md`, as round 4 did.

## 1. The fairest strong statement

> On New York's map, Qwen 3.5 4B alone gets 10 of 600 questions right, and 8 of those are trips that end where they began. Compile a RISC-V machine into its weights, with no training, load the map as data, and let Qwen write one call: at its one blind sitting it got 147 of 200, with no wrong line and 53 refusals. After one fix chosen on seeing those refusals, the same 600 questions print 600 right, 0 wrong, 0 refused, including 300 that had never been asked. An ordinary program outside the model, given the same calls, gives the same answers. So the machine doesn't beat a tool. What's new is that the map and an exact walker live in the model's own numbers.

**The numbers underneath, which are better than the page's:**

| Same 600 questions | Result |
|---|---|
| Alone, strict | 10 (Wilson 0.9-3.0%) |
| Alone, on the 582 not ending at the start | 2 (Wilson 0.1-1.2%) |
| Alone, one-leg trips | 1 of 300 |
| With the machine, r1, line printed | 600, 0 wrong, 0 refused |
| With the machine, r1, Qwen's own words, strict | 442 (Wilson 70-77%) |
| With the machine, r1, Qwen's own words, generous | 578 (Wilson 94.5-97.6%) |

**What the 158 strict reply misses are:** 136 the handle fused to the name, 11 a stop line named as a plain station, 11 "Wash Sq" for "W 4 St-Wash Sq". **None names a different station.** Those 11 stop-line replies do name the right place, but a reader can take them for a finished trip.

**The limits, which must travel with the claim:**
- **Not a beat over a tool.** Same call and same outcome as the same-setup tool on 600 of 600. The page never says this, and a technical visitor will ask it first.
- **No map is the weakest baseline.** The fair rival is Qwen with the map. X2.7 has a number for that, on the same model and New York graph, but it comes from a run that failed technically twice, so it's descriptive and uses a different prompt: 2% on two-leg questions answering directly (100), 64% thinking step by step (25). So reasoning closes much of the gap. Nothing has been measured on these 600.
- **The 600 isn't a blind 600.** 147 are the blind sitting, 53 are re-scoring, 100 were built so they can't be refused, and 300 are fresh one-leg questions on a map already seen.
- **One template, with worked turns in the prompt.** Practice cities on harder wording give about 84 of 100.
- **Nothing here measures closures against Qwen alone or Qwen with the map.** The machine's largest claim has no baseline yet.
- **Slower.** On the real weights the 300's sample ran 67.6 positions a second, about 3,845 machine tokens a question, so about a minute a one-leg question, against 0.48 s for Qwen alone.
- **The rest stands:** simulator on a sample, runner outside the model, false closes on trick sentences.

## 2. What's undersold on the page

1. **10 of 600 is buried** as the last sentence of a section, and the 600 beside it never appears. The page's only comparison has no other side.
2. **The checker's sensitivity.** "No difference" means little without showing it could detect one. 8 of 8 flipped bits were caught at the exact position, on each of the two New York windows. It's nowhere on the page.
3. **The window on Qwen's own writes.** 337,526 positions on E1's and D1r's calls, 0 differing, took what was reached and never compared from 71 gates to 21 of 11,589. The page gives only a total, 421,104, and its "about 40" still describes the frozen build.
4. **Wrong closes need their other half.** The table shows 14 of 30 on trick sentences. Unasked `closed` on plain questions is 0 of 800 print rows (200 frozen, 300 r1, 300 unasked), and the page doesn't say so.
5. **The refusals.** 53 refusals and no wrong line on a blind surprise is the most trustworthy thing here, and the page reports it as a miss. It's a miss, and it's also the behaviour you'd want. Keep the limit that in reply mode the refusals became 25 wrong answers.
6. **The dek.** "Close a station, and the answers that depend on it change" is true of any program. The result is that all 264 changed, all 11,736 others stayed byte-identical and all 12,000 came back.

Round 4 also listed 80 of 80 closes and the independent walker's 24,600 matches. The first needs a line only if the table goes, and the second only counts once the rows are public.

## 3. The page, read as a sceptical visitor

**What works:** the misses sit beside the wins, the demo says it isn't the model, the failure transcript is shown, "Not done" is plain, and I found no number on it that's wrong. The page's tone is its best argument.

**What a sceptic would stop at:**
- **Nothing can be checked.** There isn't one link: no repo, map, questions, rows or SPEC, and no model name beyond "Qwen". Every number rests on our word.
- **"These are the machine's answers for this trip, written into the page."** I found saved machine rows for this trip only with nothing closed and with Bowling Green closed. All 20 D2m closures leave it at Borough Hall, and a search of `exam/results` finds no close of Wall St, Borough Hall, Nevins St or Atlantic Av-Barclays Ctr on any trip. The page's answers do match round 4's walker on all of them, so they're very likely right, but the sentence claims more than was saved. **Fix:** run those four on the executor, which takes seconds, or say "worked out by the same rules".
- **Terms arrive undefined.** "After the fix" appears in a table two sections before the fix is explained. "Positions" and "sittings" are never explained, and "the frozen build" appears first in passing.
- **"496 stations".** It's 496 nodes in the file, and a New Yorker counts differently. Say "496 stops in our map file".
- **"One-line trips"** on a subway page reads as one subway line. Say "single-leg".

**The two changes that would help most:**

**Add one line of links**, under the machine table: the map, the 600 questions, the saved rows, SPEC and the code. Round 4's 50-line walker matched all 24,600 answers at its first run, so a reader could do that too. It checks the answers, not that the weights produced them, and releasing 18.8 GB of weights stays Theo's call. No caption can do this job.

**Replace the Qwen table** with three rows, and cut the sentence that now trails it:

| New York | Right | Wrong | Refused |
|---|---|---:|---:|
| Blind sitting, 200 questions | 147 | 0 | 53 |
| After the fix, 600 questions, those 200 included | 600 | 0 | 0 |
| Qwen alone, the same 600, no machine, no map | 10 | 590 | 0 |

Then one sentence: "An ordinary program given the same calls gets the same answers: the point isn't accuracy, it's that this runs inside the model." The 47 of 100 on the file's own questions has to survive this, in the sentence on refusals. That's two rows fewer and a clearer claim.

**Keep the state digests:** they look like clutter, but they're the proof of return.

## 4. Ready for Wednesday?

**Ready for Theo to review now. Publishable on Wednesday if these are done first:**
1. The demo sentence above is fixed. This is the only claim I'd call unsupported.
2. This round's critic is read and this page is corrected against it. The runs are still marked unreviewed.
3. Theo decides what can be linked, and whether r1 stands: PATH records that using the revision on a missed prediction stretched the rule, and that it's his call.
4. "Not done" gains "Qwen with the map in its prompt", unless the run below has happened.

A New York-only page is the right scope for a fast publication, because the page is honest about what that excludes. What it can't yet say is whether reasoning over a pasted map gets close.

## 5. The single best next run

**For the sealed rerouted map (`nyc-cf`), frozen r1:**
- It's the only test that removes "the fix wasn't blind", the largest asterisk on the page. The 300 fresh questions are one-leg, and r1's rule has never met two-leg shared starts blind.
- Sealed data exists to be spent on a frozen build, and r1 is the build being published. Reporting a miss costs little, since this page already reports misses well.
- It's cheap: at this round's measured pace, about 5.8 s a question printed and 4.2 s with the tool, 200 of each is about 33 minutes of GPU, plus round 4's estimated 2 hours of CPU.
- It supports "the same machine takes any graph that fits", which currently rests on New York and the practice graphs.
- It leaves `nyc-relabelled` still sealed.

**Against it:**
- **Tonight's result weakens its main reason.** The rerouted map was designed to close "Qwen just knows the map". At 2 of 582, without counting trips that end at the start, Qwen doesn't know the map. The machine half should pass, as 24,600 answers and practice cities suggest, so the run mostly re-tests r1's naming rule.
- **It's irreversible, for a page caveat.** No revision is left, so a miss is r1's permanent record, and any later build with the trap or handle fixes (both named by round 4 as after launch) would have one less sealed city for the summit's gates.
- **It doesn't answer the visitor's first question.** It says nothing about what the machine adds over the model with the map.
- **It would land unreviewed under a day before publishing,** on a page it would then partly rewrite.

**My pick: Qwen with the map in its prompt, on the same questions. No machine, nothing sealed.**
- **It's the only run that could change the page's thesis.** If reasoning over a pasted map got near 600, we'd need to know before publishing. If it gets near X2.7's 64%, then the claim gets a real number, and wrong answers there will be silent, against the machine's 0 wrong and its refusals.
- **It's already owed.** `DESIGN.md` lists it as a baseline, `d/PLAN.md` says to redo it on the frozen tool, and the design steel-man required it as a control.
- **Shape:** a direct arm on all 600, and a step-by-step arm on the frozen 200, in X2.7's prompt form so the earlier numbers have a comparator. Add the closure sentence on the E1 draw, if budget allows, as that's the first baseline for the headline.
- **Cost:** the map as plain text is about 74,000 characters, very roughly 25,000 tokens if every edge is listed, and X2.7's two failures were memory on long prompts, so check the memory first. Time 4 questions, then set the budget from that rate, under the 4-hour ceiling. Register predictions first. Mine: direct 1-5% on two-leg questions, step by step 40-70%, with nearly every miss a confident wrong station.

**What would change my pick:** Theo saying r1 is the build the summit gates will rest on, or that "blind" matters more to Wednesday's readers than the baseline. Then run `nyc-cf`, not relabelled, since a wrong answer from memory only shows up on the rerouted map. It stays his call either way.

## Where the best case still fails

- The advantage over a plain tool is zero on accuracy, and the model is far slower. The case is that the machine runs in the weights, and only a reader who cares about that will be impressed.
- Almost all machine evidence is the simulator: 803,052 real-weight positions is a sample of the machine's work.
- Qwen's part is one template with worked turns, r1 isn't blind, and shared-name closures haven't been tried.
- Qwen wrongly closed on 14 of 30 trick sentences, and 6 of 15 on the route gave a wrong station with no warning.
- No closure result has any baseline at all.
