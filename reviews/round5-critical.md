# X2.10 round 5: critical review (the runs round 4 asked for, the web page, the status page)

Reviewer: critic subagent, 3 Nov. CPU only, no GPU, no sealed data. The only repo file written is this one; scripts and outputs stayed in the scratchpad. I didn't read `reviews/round5-steelman.md`, so as not to anchor on it.

## Verdict

**The counts hold and the registration held. The page isn't ready: it uses two of the new numbers to say more than they show, and its demo is wrong about what the machine does.** Every number I recounted matches, apart from "51 calls" in PATH. Nothing needs rerunning.

The real findings:

- **300 of 300 can't test the fix.** None of the 300 could be refused. It can fail only if Qwen miscopies a trip.
- **10 of 600 says Qwen can't recall the map, and nothing about what the machine adds.** Repeating the start name would score 18. An ordinary tool outside the model ties the machine on every row, and the page doesn't say so.
- **The demo:** closed by name, the machine refuses 3 of its 5 tappable stations.

Replacement wording for each is below.

## BLOCKERS

### B1. 300 of 300 reads as a test of the fix, and it isn't
`web/index.html:136`, `:138`; `status/climb.html:69`, `:112`, `:142`; `PATH.md:42`.

**How many of the 300 could refuse: 0.** I counted, for each question, the same-name nodes that have the first leg's line. It's exactly 1 on all 300. All 300 start from a handle on that line, so if Qwen copies the line right, the rule must pick the gold start. Across the whole map only 4 route pairs still refuse (36 St on the R, 7 Av on the B, each direction), and no file question starts on one. So the registered "refused 0-15" could only ever be 0, and a one-line count would have shown that before the run.

**Can it fail at all? Yes, one way: Qwen miscopies.** All 300 calls copy the name and the legs exactly, by my regex. So this is a real measure of copying one template, as line 130 says. It says nothing about whether the rule is right.

**"Never been asked" and "first fresh questions" oversell it.** `orig_id` doesn't show this, but the calls do:
- All 100 `split1` are the first legs of the file's 100 two-leg questions, start and leg identical. 53 of them are the first legs of the 53 frozen refusals, the data the rule was chosen on.
- All 100 `split2` are those same questions' second legs, so their start names are new to Qwen but the trips aren't new to the file.
- Only the 100 `one` questions are unrelated to what was asked.
- 21 are repeats: 279 different questions, 251 different name-and-line pairs. Of the 175 shared starts, 59 use a name-and-line pair from the refusals, and 116 don't.

The page says the new 100 "confirm the fix and don't test it", then lists the 300 with no such limit, so a reader takes the 300 as the test.

**Replace `web:136`'s label with:** "After the fix, the file's other 300, one-line trips"

**Replace the sentences of `web:138` from "We chose it after seeing New York" to "175 from shared names" with:** "We chose it after seeing New York. Neither row after the fix tests that choice: the new 100 were built so they can't be refused, and none of the other 300 can be either, as each starts from the only stop of that name on that line. All they can catch is Qwen miscopying the trip, and it didn't. The 300 are 279 different questions, 175 from shared names; 200 are the two halves of the file's two-leg trips, including the first legs of the 53 refused."

**`climb:69`, replace the "300 of 300" sentence with:** "The file's other 300, one leg and one template, went 300 of 300, but none could be refused, so that measures copying, not the fix."

**`climb:112`, replace "and all 300 of New York's questions it hadn't been asked, simple one-line trips" with:** "and all 300 of New York's one-line trips, which couldn't trip the fix either."

**`climb:142`, add to Standing:** "0 of 300 could be refused; 200 are halves of questions already asked; 279 different."

**`PATH.md:42`, replace "The first fresh questions of New York's own on r1, with the map already seen" with:** "Not a test of the rule: 0 of 300 could refuse, by count. 200 are the halves of the 100 two-leg questions, 53 of them the first legs of the refusals; 279 different. It measures copying one template."

### B2. 10 of 600 stands in for what the machine adds
`web:140`; `climb:69`, `:112`, `:143`; `PATH.md:43`.

**Is the strict marking unfair? A little, and it doesn't change the reading.**

| Marking | Count of 600 |
|---|---|
| Strict | 10 |
| Generous (the script's, gold text anywhere in the reply) | 12 |
| Lenient, mine: "14th St" = "14 St", "Street" = "St", "Avenue" = "Av", case and punctuation ignored | **15** |
| Lenient, plus partial credit ("14th St" for "14 St-Union Sq", 5 rows) | about 20 |

- "Generous" isn't generous: it fails "14th St" but passes two rambling lists that happen to contain the name (900015, 910084).
- **The bigger point cuts the other way.** 8 of the 10 strict hits are Qwen repeating the start name on a trip that ends where it began (127, 900000, 900002, 900011, 900087, 910016, 910063, 910092). 304 of 600 replies begin with the start name. 18 questions have gold equal to the start, so repeating the start would score **18, above Qwen's 10**. Only 2 strict hits, 6 lenient, aren't repeats, and 4 of those 6 are "14th" or "59th", where 146 replies mention 14th or 14 St.
- One-leg questions: 1 strict of 300.

**Is it a fair no-machine control? It's a fair floor and nothing more.** No system prompt, no worked examples, no reasoning, answer only, one wording, 40 tokens, against an arm with a system prompt, four worked turns and the tool. Those differences aren't the machine. The 40-token limit barely matters (16 replies over 120 characters), and the registered wording does say it tests remembered geography.

**What it supports:** this model, in that setup, can't recall this map. **What it doesn't support:** anything about what the machine adds. The arm that isolates that is the same-setup normal tool, and it **ties the machine on every row**: 147 frozen, 300 on r1's set, 300 of 300 here, same call on all 300 (my recount from `other_host.jsonl`). The page never mentions it, so "300" next to "10 of 600" reads as the machine's gain. On these questions the machine adds nothing to accuracy over a tool; it shows the tool's job can live in the weights. That's the project's real claim, and the page should say it.

"Missed, in the machine's favour" in PATH is spin. It missed low, and it's the wrong comparison for that phrase.

**Replace `web:140` with:** "On our practice cities in harder wording, it gets 84 of 100, with 9 wrong lines. Asked the same 600 New York questions with no tool and no map, in one wording, with no worked examples or reasoning, Qwen got 10 by strict marking, about 15 if "14th St" counts for "14 St". About half its replies just repeat the start station, and doing only that would score 18, as some trips end where they began. So it can't recall this map, and that's all this shows. A normal tool outside the model, in the same setup, scored the same as the machine on every row above: the machine's point is that the tool's job can live in the weights, not that it beats a tool."

**`climb:69`, replace "Qwen alone, with no machine, got 10 of 600." with:** "Qwen alone, with no tool or map, got 10 of 600, below the 18 that repeating the start would score. A normal tool in the same setup ties the machine on every row."

**`climb:112`, replace "Alone, with no computer, it got 10 of 600." with:** "Without it or any tool, it can't recall the map. An ordinary tool outside the model does as well as the computer here, so this shows the computer works, not that it beats a tool."

**`climb:143`, Standing:** "strict 10, lenient about 15; repeating the start scores 18; a floor, not the machine's share."

**`PATH.md:43`, replace "Prediction 40-120: missed, in the machine's favour." with:** "Prediction 40-120: missed low. Lenient on '14th St', about 15. 8 of the 10 are the start name repeated on a round trip; repeating the start would score 18. It shows Qwen can't recall the map, not what the machine adds: the same-setup tool ties the machine on every row."

### B3. The demo isn't the machine's answers, and most of it can't be done by name
`web:80`. "These are the machine's answers for this trip, written into the page." The answers aren't written in: `walk()` computes them in JavaScript.

I ran all six states on the simulator (r1 build, reference machine beside it).
- **By handle, all agree with the page:** none gives Borough Hall; Wall St, Bowling Green and Borough Hall give Nevins St; Nevins St and Atlantic give Borough Hall.
- **By name, the way line 87 shows Qwen doing it, 3 of the 5 tappable stations refuse:** Wall St (`AMBIGUOUS 2`), Borough Hall (`AMBIGUOUS 2`), Atlantic Av-Barclays Ctr (`AMBIGUOUS 3`). Only Bowling Green and Nevins St have unique names.

So line 114 says "Shared station names weren't tried" while the demo invites you to close three of them. Only 2 of 5 match what Qwen has shown it can do.

**Replace `web:80` with:** "This runs in your browser, not in the model: a few lines of JavaScript for this one trip. We checked every answer against the machine on our simulator, closing each station by its internal number. Wall St, Borough Hall and Atlantic Av-Barclays Ctr share their names with other stops, so closed by name the machine refuses."

### B4. Two different 300s next to each other
`web:139`. "after the fix, it's strictly right on 225 of 300" comes straight after a table whose last row is a different 300. On that one the count is **217**. 225 is the D1m set (200 + new 100).

**Replace the first sentences of `web:139` with:** "When Qwen answers in its own words, after the fix, it's strictly right on 225 of the 300 two-leg questions and 217 of the 300 one-line ones. Most misses are one formatting fault, an internal number stuck to the name, on about a quarter of all replies, and none names a different station."

(Recount: 217 = 300 less 75 fused handles less 8 "Wash Sq" for W 4 St-Wash Sq. Generous 292. Print and reply sittings wrote identical calls on 300 of 300, so this isn't a second sample of call writing.)

### B5. The Qwen sections don't say they ran on the simulator
`web:84` says "on the real weights", and the table at `:107-113` follows with no label. Line 126 mentions the simulator only under the machine exams. From rows, **68 of 70 conversations in each E1 sitting ran on the simulator**, and every Qwen exam row in `:133-136` had its machine part on the simulator with 4 questions a sitting compared. A reader will think 40 of 40 happened on the real weights. It's the launch item.

**Add to the start of `web:114`:** "The transcript above is one of two conversations per sitting on the real weights; the other 68 of 70 ran on our simulator. On the fix's build, 12 more were replayed on the real weights, the same calls under a different prompt, with no difference."

**Add to the end of `web:130`:** "The machine's part ran on our simulator, with 4 questions a sitting checked on the real weights."

### B6. "Frozen before the map's exams ran" is true and misleads
`web:118`. The freeze order is right (round 4 checked it). But `DESIGN.md:99` says "NYC shaped r0, so it is not held out from design history", the graph's `meta` names X2.7 as its source, and PATH says it isn't a never-seen map. The page says none of this, so a public reader takes it as blind. Also, the machine exams had bars, and "predictions" fits D1m better.

**Replace with:** "Frozen before these exams ran, one attempt, bars and predictions written first. This build had never run on the map, but the map comes from our earlier work and shaped the first design, so it wasn't unseen. Direct calls, no Qwen: 20 closures, each scored on the same 600 questions."

### B7. "About 2 minutes a question ... would take weeks" is high, and too broad
`web:126`.
- **Measured on the real weights:** one-leg 51-67 s, two-leg 68-89 s (the three stock samples); the window's median job 90 s at 62 positions a second. That's a minute or so, not 2.
- **"Weeks" is right for the machine exams:** 25,140 calls, 113.3 million tokens I summed from rows, about 21 days at that rate.
- **It's wrong for "a whole exam":** at the same rate r1's E1 is about 3.6 hours of chip tokens and D1m about 7.5. So the sentence excuses more than it should. See the note on running E1 whole.

**Replace with:** "The real weights take a minute or so a question, so these 25,000 calls would take about three weeks."

### B8. PATH's bullet misreads two results
`PATH.md:45`, and `climb:144`.
- **"51 calls" is wrong.** The plan has 51 fresh-machine jobs and 55 calls: 12 of E1's 70 conversations and 39 of D1r's 300 rows, picked greedily. "Real weights on E1's and D1r's calls" reads like all of them. 12 calls carry `closed`, 4 carry `reopened`.
- **Replace with:** "Real weights on a greedy pick of 12 of E1's 70 conversations and 39 of D1r's 300 rows, r1's ELF: 51 jobs, 55 calls, 337,526 positions, 0 differ." In `climb:144`, say the same: "a pick of E1's and D1r's calls".

`PATH.md:44`, "So the instruction isn't the main cause". The count is right: 1 of 11, a fair marking of a clear sentence (900065, "The journey stopped early. You are at **34 St-Hudson Yards**."). The same 11 questions as D1r; Wilson about 2-38%. But the question still ends "At which station are you now?", which asks for a bare station, and removing one sentence leaves that in. Worked turns aren't the only suspect left.
- **Replace with:** "So removing that sentence alone doesn't fix it (exploratory, 11 rows). The question's 'At which station are you now?' and the worked turns both remain; neither is tested on New York."

## NOTES

**The window's prompt difference doesn't matter for coverage, and 21 gates is right.** I replayed calls on the simulator under both prompts, using the exact real prompt (1,383 tokens, matching the row's count; one fixed question for all).
- A's 300 calls gave identical sets under both prompts: 0 gates, channels, reads or writes differ. So "same calls, not the same stream" is a limit on the stream, not on what's reached.
- Not tested: Qwen's own text between calls, and a per-question prompt.
- Stock on real prompts is still only the 2 lockstep conversations per sitting and the samples.

**21 gates, 169 channels: recomputed from logs, exactly.** Also 71 and 416 before, 50 and 247 added, reads and writes 0 left, all 51 coverage logs finished and compared.
- Of the 21, 18 are from r1's machine exams and 4 from E1 and D1r (1 in both). So the window closed 50 of the 54 on E1's and D1r's path, which is what it was for.
- **Adding A's calls: still 21 gates, but 183 channels, not 169.** PATH discloses that A isn't added. Worth stating 183, as they ran before this number was written. r1's job, samples and lockstep aren't credited; they could only lower it.
- Round 4's 68 and 379 used slightly different credit, which probably explains its gap from 71 and 416; I didn't reconcile them.
- Compared in all is now 11,893 of 20,457 gates (58.1%); `climb:123` still says 11,843 for the older set, fine if labelled.
- Window bar: 337,526 positions, 0 differ, 8 of 8 flips caught, 51 of 51 finished, no flags. 421,104 adds up (67,813 + 15,765 + 337,526).

**E1 could run whole on the real weights.** About 3.6 hours of chip tokens at the measured rate, under the 4-hour ceiling. It's the launch item, and that would replace "2 conversations and a greedy pick" with the actual exam. Not a blocker; Theo's call, and it needs registering first.

**Registration held.** `AFTER.md` and all scripts are in `6f212be77b` at 04:27:51; `alone.log` starts 04:27:55. None has changed since, none is dirty. Raw hashes all match. Order B, A, C, D is right, and the budgets were kept. The web rewrite at 04:31 predates all results but the first; results went in at 07:34. Predictions: 4 of A's held, B and C missed, D held. `AFTER.md`'s own "nearest thing to a fresh test of r1" overclaims; it's frozen, so correct it in PATH (B1), not there.

**Stale on the status page, from round 4's list, still unfixed:**
- `climb:127`, "26 of 27" (round 3: about 20 of 27).
- `climb:53` "An exact graph computer" and the camp note "Exact wherever compared": the first needs the second's limit.
- Camp 3 "Improving on practice data" is paused.
- Level 1's closure sentence drops worked examples and unique names.
- Everything else on round 4's B1 to B9 list that I checked is fixed. `web/index.html` no longer says "exact", "every route", "26 gates" or "practice-map results only".

**Smaller wording on the web page:**
- `:120` "496 stations": the graph has 496 nodes and 379 distinct names. "496 stops" is safer, since New York's own count differs. Fulton St alone is 5.
- `:110` "Reopens 19 / 40": the first sitting's figure is mostly 16 conversations ending on a refused start, as PATH says. A reader will read it as Qwen failing to reopen.
- The demo shows only skips: Fulton St is locked, because closing it gives a stop line. Of D2m's 264 changed answers, only 135 are a new station (57 stopped, 72 `CLOSED`). Line 77 could say "Closing a change station stops the trip instead."

**Checked and right on `web/index.html`:** both transcripts, word for word, including states and hashes (nyc:198 in lockstep, nyc:139 on the executor); the E1 table; 264, 11,736, 12,000, 500; 147, 47, 100, 300; 25 wrong replies; 0.3%; about 40 of 11,750; about 42%; 421,104; 11 layers, 32 layers, 85 units.

## What I recomputed and what I didn't

**Recomputed:** every row of `other/all.jsonl` with `score_d1m` logic and my own walker (300 right, 0 refused, all status answered, Wilson 98.7-100%); `other_host.jsonl` (300); `other_r/all.jsonl` (217, 292, miss types); `alone.jsonl` (10, 12, plus my lenient count and baselines); `stops/all.jsonl` (1, same 11 as D1r); per-question refusal count on the whole map; overlap of the 300 with the two-leg questions; `plan.json`; `window_check.json`, `window_flip.json`; `remainder.json` from coverage logs; stock speeds from `window.log` and three stock samples; tokens from `exam/results/nyc/*.jsonl`. **Ran, CPU only:** simulator replays with the reference machine beside them (0 disagreements on 970 question or conversation replays) for A under both prompts, E1 and D1r under the real prompt, and the demo's closures by name and by handle.

**Didn't:** rerun `check_trace` or anything on stock (I read saved comparisons); replay with Qwen's text between calls or per-question prompts; check `climb.html` below level 4 line by line beyond the items named; read `round5-steelman.md`; audit `reflib` beyond agreement with my walker; check whether the graph matches the real subway; open any sealed data.
