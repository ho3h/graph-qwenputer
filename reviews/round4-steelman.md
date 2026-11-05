# X2.10 round 4: steel-man review (D161)

Claude (steel-man subagent), 3 Nov 2026. Covers New York's frozen exams and revision r1. Written without reading this round's critic. No model was run.

## Verdict

**The machine half is stronger than the page will need it to be, and I reproduced it from outside the project. The best thing about the Qwen half is how it failed when New York surprised it.** Two wordings need correcting in the work's disfavour, one "silent" count and "never used in design". Both are below.

## What I checked

**Recomputed from saved rows:**
- **An independent walker.** I wrote about 50 lines from `SPEC.md` alone, importing nothing from the project, and ran it on New York's graph. It matched the machine's saved line on all 24,600 answers, frozen and r1, at the first run: 600 base, 12,000 closed, 12,000 restored. 264 affected changed, 11,736 unaffected stayed. Script: `<scratchpad>`.
- **Routes.** My own BFS agrees on all 454 hop counts, the printed paths use real edges, and the 46 `NOPATH` are truly unreachable. Reference digests are equal on all 25,140 calls per build (24,640 + 500).
- **Replies, traps and reopens.** I classified every r1 D1r reply and every E1 false close and reopen miss from `all.jsonl`.
- **Sums.** Real-weight positions and chip tokens, as given below. I traced the `nyc:198` walk by hand.

**Read, not recomputed:** the score files themselves, the window's coverage JSON, the whole-table check, Qwen's 424 tensors, the 11 layers. I saw the first jobs of the stock checks and their totals.

**Not opened:** the `nyc-cf` and `nyc-relabelled` data (I read only their rules in `data/README.md`), and all other held-out data.

## 1. The strongest true claims

**Technical reader:**
> A RISC-V machine compiled into 11 added layers of Qwen 3.5, with no training and Qwen's own 424 tensors bit-identical, sat a frozen exam on New York's subway, which its development had never run, with no error: 500 of 500 routes, and across 20 closures of 600 questions each, 264 of 264 affected answers changed, 11,736 of 11,736 others stayed byte-identical, and 12,000 of 12,000 were restored on reopening. Those are direct calls on an executor, with a reference machine's digest equal on every call. The executor matched the real weights at all 335,703 positions of a 42-call window on New York's own calls, leaving 26 of the 11,535 gates those calls reached uncompared. Driving it through a tool call, Qwen scored 147 of 200 at its one blind sitting, with 53 loud refusals and no wrong line. All 53 came from station names New York reuses. One disclosed rule, chosen after seeing that, gave 300 of 300, on the same calls for 200 of them. Qwen also wrote the close itself in 40 of 40 conversations, changing only that bit and the count, and the state returned word for word on all 33 that wrote both writes, read from the weights' own heads in the 2 run in lockstep. It also wrongly closes on 14 of 30 trap sentences, and a runner still offers the tool and ends the turn.

**General reader:**
> We built a small computer out of an AI model's own numbers, with no training, and loaded New York's subway map into it as data. On a test fixed in advance, it found 500 of 500 routes. We closed 20 stations one at a time and asked 600 questions each time: all 264 answers that should change did, all 11,736 others stayed identical, and reopening put all 12,000 back. That ran on a fast simulator, checked against the real model on a sample. Using the computer itself, the model got 147 of 200 at its one blind sitting and refused the other 53 rather than guess, because New York reuses station names. After one fix, made after seeing the problem, it got 300 of 300. Told about a closure in plain words, it made the closure itself every time, 40 of 40. It also closed a station on 14 of 30 sentences meant to trick it, such as a coffee cart shutting down outside, and that can make an answer wrong.

## 2. Most underrated: the frozen miss

**The first sitting failed in the best available way.** New York had a property development never met: 76 names shared by 193 of 496 nodes. Qwen scored 147 against a predicted 176-198, and all 53 failures were `AMBIGUOUS` lines naming the candidates. None was a wrong line. Qwen's call was right on all 53. An LLM system that meets a surprise on a blind test and says "which one?" every time, instead of guessing, is unusual, and the page gives it a caveat's tone. It's also the best evidence the seal was real: had New York leaked into development, shared names would have been handled.

The limit is firm: this holds in print mode. In reply mode the same refusals became 25 wrong answers.

**The others, ranked:**
- **Closures exact, with state read from the weights: rated about right, but its best evidence isn't on the page.** Across both sittings Qwen wrote 80 of 80 right closes (Wilson from 95.4%) on 64 different stations, and 56 of 56 on the 7 wordings with no form of "close" ("No trains are calling at X"). 52 of 52 states returned word for word. Weight editing can't offer that reversal, but no comparison is registered, so don't say "beats".
- **24,600 machine answers: strong, and easy to overstate.** It's 600 questions under 41 machine states. 168 questions are affected by some closure; 4 of the 20 closures affect none. The fair form is "264 of 264, 11,736 of 11,736". Its real force: the size prediction was the named risk, 496 nodes against checks that stopped at 270, and it passed untouched. Tokens were missed: `path` reached 58,798 against a predicted 25,000.
- **Zero clean wrong lines: true only on questions with no edit.** 0 of 300 distinct questions (Wilson to 1.3%), one wording family. E1's traps print 5 clean wrong lines. Practice hard wording had 3 silent in 100.
- **Qwen writing the edit: slightly overrated as a reading result.** It's the launch item and it works, but the traps show it responds to the words.

**A finding nobody has stated: on a right line, Qwen almost never names a wrong station.** Of r1's 75 strict misses:

| Reply | Count |
|---|---|
| Handle fused to the name ("27 14 St" for `@27 14 St`) | 61 |
| Stop lines, naming the station where it stopped | 11 |
| Name shortened ("Wash Sq" for "W 4 St-Wash Sq") | 3 |
| A different station | 0 |

So "225 of 300" reads like 1 in 4 misread, and it isn't. The fused handle is a real blemish, and strict was right to count it, but it's one formatting fault.

## 3. Caveats

**Stricter than the evidence, or missing context:**
- **"It still never says the trip stopped."** All 300 questions end "Answer with the station name only", and Qwen obeys. On `lines/` wording without that sentence, 60 of 60 said it stopped, on random graphs. Round 3 raised this. Add the clause until it's tested.
- **"False closes 14 of 30" reads like a rate.** It's a hand-built adversarial panel, and it's concentrated: in r1, five wordings ("The pharmacy at X...", "One entrance at X...") took all 14, the other five 0 of 15. Next to it belongs a number that isn't on the page: unasked `closed` on plain questions, **0 of 500 rows across both sittings**.
- **"Silently" hides that the record is complete.** All 27 false closes across both sittings appear on the machine's own line, as `closed @344 Hoyt St`, and in state. Silent in the reply, never in the log.
- **"58% of gates".** The right denominator for these results is what they reached: 99.8% of gates and 93.6% of channels. Keep the remainder in numbers. The other 8,588 gates carry none of these answers, though D1r's and E1's reach isn't counted.
- **"Roughly 60%" on the page** is stale and weaker than the truth.
- **"Reopens 33 of 40"**: 6 of the 7 misses are one wording, "Trains are stopping at X once more", 2 of 8. The rest: 31 of 32.
- **Stale text, against the work:** PATH rung 4 "Python still ... applies closes" and "has not written a write"; rung 5 "Not frozen"; climb's "awaits round 3's reviews"; the page's "No New York exam has run" and "98 ... 77, with 7 wrong".

**Right to keep, all of them:**
- The executor carries the results on a sample. 110,279,985 frozen machine tokens would take about 71 days on stock at 18 a second, so that's the honest reason.
- Real-weight positions on New York so far: 449,761 across both builds, 0 differing. Say "sampled".
- r1 isn't blind; the 53 are close to re-scoring; the new 100 confirm rather than test; D1m's bar tests little.
- D2m's closures are direct calls, not written by Qwen. **This is the easiest confusion on the page.**
- A runner outside the model; worked turns in the prompt; one question wording; hard wording about 84 on practice; refusals becoming invented answers in reply mode.
- Controls, rerouted and relabelled cities unrun; no weight-editing comparison.

**Two corrections the evidence forces:**
- **The r1 cost is understated.** PATH says "5 of those silent. That's the revision's cost: frozen had 3 silent." Those aren't the same measure. The frozen 3 are limit lines; `nyc_edit/score.json` has no silent key for traps. Like for like: clean wrong lines 0 frozen, 5 r1. Replies giving a wrong station with no warning: 3 frozen, 6 r1. All 6 of r1's moved answers are silent in the reply, including the limit line whose reply is "7 Av". Use 6 when describing replies.
- **"Never used in design" overclaims.** The graph comes from `xseries/X2.7`, the same author's earlier stream, and `data/README.md` records facts about it, such as 17 of 35 complexes mixing names. Say "never run in development" or "sealed from this build's development".

## 4. The landing page

**Headline:**
> **A subway map inside an AI model. Close a station, and exactly the right answers change.**

**The dek:** "New York's real map, 20 closures, 600 questions each, on a frozen build with one attempt: all 264 affected answers changed, all 11,736 others stayed byte-identical, and reopening restored all 12,000. No training."

**Must sit directly beside it:**
- "On our simulator, by direct calls. It matched the real weights at all 335,703 positions we compared."
- "With Qwen driving: 147 of 200 at the blind sitting, no wrong line, 53 refusals; 300 of 300 after one disclosed fix, which wasn't blind."
- "Qwen wrote the close itself 40 of 40 times. It also closed on 14 of 30 trick sentences, and 6 of those gave a wrong answer with no warning."

**Best transcript: `nyc:198` from the frozen run (`exam/results/nyc_edit/transcripts.md`).** Blind build, real weights in lockstep (14,052 positions, 0 differing), the answer moves, and Qwen is right both times in its own words. A New Yorker can check it on a map: the 5 from Fulton St goes Wall St, Bowling Green, Borough Hall; with Bowling Green skipped, it lands one on at Nevins St. My walker gives both answers.

> **User:** Flooding has closed Bowling Green. Start at High St station. Ride the A train 1 stop northbound, then change to the 5 and ride the 5 train 3 stops southbound. One stop means the next station. At which station are you now? Answer with the station name only.
>
> **Qwen calls** `chase {"start": "High St", "legs": "A northbound 1; 5 southbound 3", "closed": "Bowling Green"}`
>
> **Machine:** `"closed @223 Bowling Green\n@401 Nevins St"`
>
> **Qwen:** Nevins St
>
> Right answer: `@401 Nevins St`
>
> **User:** Repairs are done and Bowling Green is back. Start at High St station. Ride the A train 1 stop northbound, then change to the 5 and ride the 5 train 3 stops southbound. One stop means the next station. At which station are you now? Answer with the station name only.
>
> **Qwen calls** `chase {"start": "High St", "legs": "A northbound 1; 5 southbound 3", "reopened": "Bowling Green"}`
>
> **Machine:** `"reopened @223 Bowling Green\n@220 Borough Hall"`
>
> **Qwen:** Borough Hall
>
> Right answer: `@220 Borough Hall`
>
> **State read from the heads:**
> - before: n_closed 0, closed [], sha b4b3c9dba00b20ea; stock heads sha b4b3c9dba00b20ea; changed []
> - after call 1: chase {"start": "High St", "legs": "A northbound 1; 5 southbound 3", "closed": "Bowling Green"}: n_closed 1, closed [223], sha 4dd3494a9cc7f3dd; stock heads sha 4dd3494a9cc7f3dd; changed ['n_closed', 'closed_bits']
> - after call 2: chase {"start": "High St", "legs": "A northbound 1; 5 southbound 3", "reopened": "Bowling Green"}: n_closed 0, closed [], sha b4b3c9dba00b20ea; stock heads sha b4b3c9dba00b20ea; changed ['n_closed', 'closed_bits']
>
> Returned word for word: True

**Show this failure right beside it (`nyc:139`, r1, executor):**

> **User:** The coffee cart outside Hoyt St shut down last month. Start at President St-Medgar Evers College station. Ride the 5 train 3 stops northbound, then change to the 3 and ride the 3 train 1 stop northbound. One stop means the next station. At which station are you now? Answer with the station name only.
>
> **Qwen calls** `chase {"start": "President St-Medgar Evers College", "legs": "5 northbound 3; 3 northbound 1", "closed": "Hoyt St"}`
>
> **Machine:** `"closed @344 Hoyt St\n@219 Borough Hall"`
>
> **Qwen:** Borough Hall
>
> Right answer: `@344 Hoyt St`

**What would convince a sceptic, in order:**
1. **Let them check it without trusting us.** Publish the map, the 600 questions, the saved rows and SPEC. My 50-line walker reproduced all 24,600 at the first run, so a reader can too. This checks the answers, not that the weights produced them.
2. **The model itself.** Replay of `nyc:198` on the released weights. Releasing 18.8 GB is Theo's call, and without it that half rests on our word.
3. **A no-machine number beside the 300.** Currently the page can't say what Qwen does alone on this panel.
4. **Rebuild the interactive strip on this real walk**, Fulton St to Nevins St, in place of a practice city, marked as an illustration: it's JavaScript, not the model.
5. **Avoid these words:** "nothing outside the model", "first" (I checked no prior art), "beats weight editing", "understands".

## 5. Next experiments, in order, for Wed 4 Nov

Budgets use the registered rates × 1.5; each still needs registration and predictions first.

1. **No-machine control: Qwen alone on the same 300.** About 30 minutes at 4.0 s a question. It spends nothing sealed and answers the first question a sceptic asks. Add the zeroed-chip control on a handful if it's quick.
2. **The blind test r1 lacks, on `nyc-cf` first, then `nyc-relabelled`, if Theo agrees.** Frozen r1 build, D1m and host, with D4m and D2m on CPU alongside. About 80 minutes of GPU per city (200 × 9 × 1.5 + 200 × 7 × 1.5), and about 2 hours of CPU. This is the most valuable run available:
   - Relabelled keeps shared names, so r1's rule meets them blind, with invented names.
   - The counterfactual map removes W and M and reroutes N, R and Q, so remembered geography gives wrong answers.
   - It removes the page's largest asterisk, or shows a miss worth knowing.
   - **Theo's call:** it spends sealed data with no revision left, and a round of reviews must fit before publishing. If time allows one city, take `nyc-cf`.
3. **Stop lines without "Answer with the station name only".** The 11 D1r stop golds and the 10 in E1's closes, exploratory, a few minutes. It settles whether "never says it stopped" is Qwen or the question.
4. **Coverage on CPU, in parallel.** Add D1r's and E1's calls and r1's firmware to the remainder, so the page's number is whole. A window for what's left only if time remains.
5. **A new paraphrase panel on New York, 100 questions, about 25 minutes.** 300 of 300 is one wording family, so publish what happens on others. Practice suggests about 84. Check it doesn't spend a sealed pool.

**After launch:** registering the weight-editing comparison; stripping the handle from what Qwen reads (61 of 300 strict misses); the trap wordings, as the last worked-turn redraft failed its rule. **Not before Wednesday:** any change to the frozen or r1 builds.

## Where the best case still fails

- Almost all of the machine evidence is the executor, sampled. Whole-exam exactness on the real weights isn't shown.
- Qwen's part is one wording family with worked turns in the prompt, and r1 isn't blind.
- A false close in reply mode gives a wrong answer with no warning, 6 of 15 on-route traps.
- No control has run, so the page can't yet say what the machine adds over Qwen alone.
