# X2.10 round 4: critical review (frozen New York and revision r1)

Reviewer: critic subagent, 3 Nov. CPU only, no GPU. Scripts and outputs stayed in the scratchpad; the only repo file written is this one.

## Verdict: what can be said publicly

**The counts hold, the freeze held, and the machine result is strong. The public wording isn't ready.** I recounted every Qwen and machine number from raw rows, and all but a few side details match. Nothing leaked, and nothing needs rerunning. The problems are in what the pages make of the numbers: `status/climb.html` overstates in five places, and `web/index.html` is wrong throughout.

Safe to say today, with these limits attached:

> On the real New York map, on a fast simulator of the compiled weights with a second reference machine checking every call, the machine got all 500 sampled route queries and all 20 sampled closures right (24,600 answers), by scripted calls with no Qwen. The simulator matched the real weights on all 335,703 positions compared on New York's own calls.
>
> Qwen, writing one call in one question template, scored 147 of 200 at its one frozen sitting: 0 wrong and 53 refusals, because New York reuses station names. On the file's own questions that was 47 of 100. A fix chosen after seeing this scored 100 of 100 on new questions that were built so they couldn't be refused. That confirms the fix; it isn't a blind test.
>
> Told in ordinary words, with worked examples in the prompt, Qwen closed the right uniquely named station 40 of 40 times, and also closed a station on 14 of 30 sentences that shouldn't close anything. Six of those moved the answer, and Qwen's reply gave no warning.

Not safe to say: "every route", "every closure", "perfectly exact", "about three quarters", "300 of 300" as a headline, "the computer in the weights passed", "26 gates left", or "5 silent" as r1's cost.

## BLOCKERS (fix before anything public)

### B1. `web/index.html` is false now: don't deploy it
Every line that is wrong or unsupported:

| Line | Text | Problem |
|---|---|---|
| 63 | "Practice-map results only. No New York exam has run." | False since 2 Nov. |
| 96-97 | "The real map has never been opened. It stays sealed..." | False on both counts. The exams opened it. Even before them, `DESIGN.md:99` says "NYC shaped r0", and the graph and chases come from X2.7 (`data/README.md:161`). |
| 97 | "one frozen attempt, with one documented revision if it misses, and we'll publish the result either way" | Stale. The revision was spent with no bar missed (B6). Publishing the result is still owed. |
| 91-92 | "98 right ... 77, with 7 wrong" | `clean.elf`, not the standard build. Not the New York result. |
| 88 | "591,209 positions ... roughly 60%" | Old firmwares. Now 11,843 of 20,457 gates (58%) on this build's tables. |
| 62, 77-78 | "exact computer", "so it is exact and instantly reversible" | Needs limits: 80 known fuzz differences, 250 reserved ids handled by a gate rule, 58% of gates compared. |
| 78 | "nudging its weights and hoping nothing else moves" | Unmeasured. The weight-editing comparison isn't registered. |
| 87 | "The same machine runs any graph" | Round 3 found r096 and r097 don't fit. Say "any graph that fits". |
| 92 | "Qwen drives it" | Omits the worked turns, single tool and runner. A runner picks the tool, ends the turn and scores (`REGISTRATION.md:13`). |
| 93 | "That's the part we're finishing" | Round 3 and New York both show otherwise: stop lines strict 0 of 11. Nothing is finishing it. |
| 69-75 | The "Close a station" demo | JavaScript that picks `open[4]` and prints something shaped like a machine call. It isn't the machine, and the page doesn't say so. Round 3 asked for a label; still none. |
| 100 | "All results here are development data on practice maps" | True of a page that now omits the main results. |

**Fix:** rewrite from the verdict text above. Until then, don't deploy.

### B2. Climb headline: "The computer in the weights passed New York exactly"
`status/climb.html`, "If we stopped today". D4m and D2m ran on the C simulator, by scripted calls. On stock: 335,703 of about 113 million machine tokens, 0.3%. PATH says "The executor carries these results on a sample". The headline doesn't.

**Replace with:** "The compiled computer passed its New York exams on a simulator checked against the real weights on a sample."

### B3. Climb level 1 overclaims, and contradicts PATH (`climb.html:112`)
- **"got every route and every closure right."** It's 500 of 245,520 ordered pairs (46 of the 500 are correct `NOPATH` answers), and 20 of 496 stations, by handle and without Qwen.
- **"about three quarters of questions on the first try."** That's 147 of 200, and 100 of those 147 are my generated easy half, which couldn't fail this way. PATH line 27 itself says "47 of 100 is the honest number".
- **"perfectly exact".**
- **"sometimes closes one it shouldn't".** It's 14 of 30 traps. Four of the ten wordings fire 3 of 3.

**Replace with:** "We've built a small exact computer out of the model's own numbers, with no training, so it can hold a subway map and look up the answer. On the real New York map it got all 500 routes and all 20 closures we tried. The model, using it, answered about half of New York's own questions at first, because New York repeats station names. After a fix chosen once we'd seen that, it answered all 100 new questions, but those were built to suit the fix. It can close a station itself when told in plain words, and on trick sentences it wrongly closes one about half the time."

### B4. "300 of 300 ... Wilson 98.7-100%" is the wrong number (`climb.html:125`, `:97`, headline, PATH:34)
I checked the raw rows.
- **The 200 repeats carry almost no new information.** Calls are identical on 200 of 200. Of those, 147 were already right and 53 are re-scoring.
- **The honest sample is the new 100,** Wilson 96.3-100%, and that's still for a sample that can't be refused.
- **Every one of the 300 calls is a literal copy of the question's text:** one template, with name and legs in order (my regex: 300 of 300). The worked turns demonstrate the same template. This measures transcription, not understanding. No hard wording ran on New York, and on practice hard wording gets 84.
- **"New York 300 of 300 on its wording" (`:97`):** "its wording" is one template. 200 of the 300 are mine.
- **Print mode isn't the default.** PATH:53 makes pass-to-Qwen the default. There the score is strict 225 of 300.

**Replace the headline with:** "Qwen got 147 of 200 at the frozen sitting (47 of the file's 100), then 100 of 100 on new questions after one disclosed fix. Every call copies one template, and those new questions can't be refused."

**Replace the Wilson line with:** "New 100: 100 right (Wilson 96.3-100%). The other 200 are the same calls re-scored."

### B5. "5 silent" compares two different things, and "used to hit a refusal" is mostly wrong
`PATH.md:36`, `climb.html` ("wrong closes that used to hit a refusal now move the answer silently, 5 of 30 traps"), `:117`, `:125`, and the table row.

From raw rows, false closes on the route:

| | Moved the answer | By the machine's line | Qwen's reply | Start name shared |
|---|---|---|---|---|
| Frozen | 3 (2 more refused) | 0 clean wrong, 3 limit lines | bare wrong station on all 3 | the 3 unique; the 2 refused shared |
| r1 | 6 | 5 clean wrong, 1 limit line | bare wrong station on all 6 | 3 unique, 3 shared |

- **PATH's "frozen had 3 silent" counts replies. Its "5 silent" counts lines.** On replies it's 3 against 6. On lines it's 0 against 5. Print mode is worse than stated, and reply mode is also worse than stated. The sixth (`nyc:118`) replies "7 Av" with the true answer Prospect Av, with nothing about stopping. Is "5 silent" right? Only on the line count.
- **Only 3 of r1's 6, and only 2 of the 5 silent ones (`nyc:185`, `nyc:133`), would have hit a refusal.** The others start on unique names (`nyc:138`, `:139`, `:128`) and would move under the frozen build too. So this is mostly a standing fault on both builds, and the rule adds about half of it. The draws also differ, so 3 and 6 aren't a clean before-and-after (the pre-run critic asked for this to be said; PATH doesn't).
- **The denominator misleads.** Only the 15 on-route traps can move the answer.

**Replace with:** "False closes on the question's route moved the answer on 6 of 15 traps after the revision, against 3 of 15 before (different draws). Every time, Qwen's reply named a wrong station with no warning. In the machine's own line, 5 of the 6 are clean wrong answers, against 0 before. About half of r1's wouldn't have got past a refusal under the frozen build; the rest happen on both builds."

### B6. "All predictions held" is false (`PATH.md:33`)
`R1.md:33` predicted "Chip tokens on a handle start: unchanged. On a name start: up by under 150."
- **Handle start:** every chase in D2m rose 97-119 tokens (24,600 rows; D2m's total 95,273,278 to 98,075,030).
- **Name start:** the 147 repeated unique-name rows rose 443-983.

Harmless to the answers, but both missed, and the pre-run critic warned about the first. Frozen also has an unreported token miss: `path` up to 25,000 predicted, 58,798 measured; chase 6,000-9,000 predicted, base mean 3,832.

**Replace with:** "Every accuracy and false-close prediction held; both token-cost predictions missed, and name starts cost 443-983 more."

Also tell Theo plainly, and record that he's been told, that the revision was used on a missed prediction with no bar missed. `R1.md:3` says "he is told so", and I found no record of that. See "Is the revision legitimate?".

### B7. "Leaving 26 gates unchecked" misleads, and the reader isn't told about r1 (`climb.html:117`, `:125`, the table's window row)
Recomputed from coverage logs: **26 of 11,535 and 344 of 5,417 are computed right** for what they say. But:
- **Level 2 reads as though only 26 gates remain.** In all, 8,614 of 20,457 gates have never been compared, though the exams didn't reach those.
- **D1r and E1 aren't counted.** I replayed their saved calls on the simulator with coverage (CPU; items prompt, so close but not identical). With them it's about 41 gates and 390 channels on frozen, and about 68 and 379 on r1 (section on the gap, below). Most of the added gates are on E1's path, the launch item.
- **The r1 number is smaller by construction, not because r1 is better compared.** 24 gates and 243 channels count r1's machine exams only. Those exams never start from a name, so they never run the rule. The like-for-like frozen figure is 21 gates and 230 channels. Comparing it with 26 and 344 isn't valid.
- **r1's own comparison with the real weights isn't stated on any page's top levels:** job 16,264 + sample 21,630 + lockstep 29,919 = **67,813 positions, on the r1 ELF**, about 0.06% of its machine tokens. The 335,703 is the frozen ELF.
- **In fairness:** the tables are the same (both hashes match, `ff9a...` and `02f4...`), the ELF is data on those tables (7,195 ROM words against 7,284), and gates carry across. That argument is sound, but it's an argument, and the reader should see it.

**Replace level 2's sentence with:** "They ran on our simulator, which matched the real weights on all 335,703 positions compared on New York's calls. It's a sample: about 40 of the 11,750 circuit gates these exams reached were never compared, and the exams didn't reach about 42% of the circuit. The fix runs a second firmware on the same circuit, compared on 67,813 positions, with about 70 gates reached and not compared."

### B8. E1's headline hides who it can close and how it's told (`climb.html:117`, PATH:29, :36)
- **"Closes 40 of 40" was drawn only from uniquely named stations** (`edit_draw.py`, `uniq`). 193 of New York's 496 nodes share a name, and the revision applies "in `chase` only", to the start. So "14 St is closed" has never been tried on New York, and by the rule's own text it stays `AMBIGUOUS`. No page says so.
- **The prompt has four worked turns and a field whose description lists "closed, shut, skipped, no service, out of service"**. Without them Qwen wrote no close in 23 conversations (PATH:63). Round 3 gave wording for this, and level 2's "Writing the edit works" omits it. The r1 wordings had also been seen (`R1.md:24`).
- **Replies aren't reported.** Of the 20 closes that moved the answer, 10 golds are stop lines (r1), and 10 of 10 replies give a bare station with no mention of stopping (frozen 8 of 8). The line is right; the sentence a user reads isn't. All wrong plain-station replies on r1 E1: 10 close-turn, 3 reopen-turn, 6 trap = 19 of 110 turns.
- **False closes leave the machine wrong even when this answer is right.** All 14 end with a station closed in state; 8 of them are off-route and score "right". A later question in that conversation would be wrong. The 7 missed reopens do the same.
- **The failures cluster.** "Trains are stopping at X once more" wrote the reopen on 2 of 8 (frozen 0 of 4); the other four reopen wordings got 31 of 32. Four trap wordings fire 3 of 3 (newsstand, coffee cart, one entrance, pharmacy), which gives 12 of the 14. So the unit is closer to 10 wordings than to 30 sentences.

**Replace level 2's sentence with:** "Told in ordinary words, with worked examples in the prompt, Qwen closed the right station on 40 of 40 and reopened it on 33 of 40, for stations with a unique name only; shared names weren't tried. It also wrongly closed on 14 of 30 trick sentences, always leaving a station closed in memory, and on 6 of them it moved the answer with no warning."

### B9. Climb is stale and contradicts itself further down
- **`:127`, "Rewording them made 60 of 60 replies say the trip stopped."** New York: **0 of 11**, on the worked-turn build. Level 2 of the same page says it never does. Round 3 asked for "not with the worked turns". **Replace with:** "Rewording worked 60 of 60 without worked turns. With them, on New York, 0 of 11."
- **`:127`, "26 of 27".** Round 3 says about 20 of 27.
- **Level 4, "Qwen's words 99 and 83".** Round 3 says strict 90 and 71-73.
- **Level 3 omits why strict is 225,** which from rows is: 61 replies with the internal handle fused to the name ("124 59 St"), 11 stop lines, 3 "Wash Sq" for W 4 St-Wash Sq. A fused handle looks like a real station name. Dev had 17 of 186. Add it.
- **Headline "no wrong answer printed".** True of D1m print only. Frozen pass-to-Qwen gave 25 wrong replies on refusals, 23 of them the start name repeated. E1 printed 5 clean wrong lines on r1. **Replace with:** "no wrong line on those questions".
- **"Everything since then awaits round 3's reviews", Reviews list, "Speedups to lock before the freeze", "Waiting on Theo" (85 units, 250 ids, proof's claim, all decided under delegation), "Strict name cleaner ... being built", "New York's token costs are extrapolated", "the bar for the exam".** All stale.
- **"about 13 GPU hours".** PATH:61 says about 20.0, and 12.9 without D3.
- **Camp 6 "Beats weight editing"** prejudges an unregistered comparison. Say "Compared with weight editing".

Before this goes out, also add round 4's status: levels 2-4 still say "not reviewed".

## Is the frozen run frozen? Yes
- `FREEZE.json` equals its copy at `ee803a1f18`. All 36 file entries hash right at that commit; the other two (checkpoint, manifest) are checked by `check_freeze.py`, whose log says `[] of 38` before D4m. `FROZEN` commit 21:11:44, items built 21:12:11, first results 21:14.
- Every D1m and D1r row carries firmware `bcf1a1dc`; every E1 and window hash agrees.
- `exam/results/nyc_d1m_ambig_posthoc.json` is 23:31, after E1 ended (23:28). r1 registered at 23:38.
- **No leak found.** Worked-turn names aren't New York's, and New York's 53 failures show nobody tuned for it.
- **One disclosure to add:** the shared-name hazard was in reach. `generate` and `edit_draw` deliberately take unique labels, and dev/random has shared labels on 100 of 100 graphs (5,231). "The practice maps never did" (climb) holds for the 28 cities, not for all practice graphs. Say "practice cities". The generated half was therefore padded in a way that hid the fault, which `R1.md` admits and which the top of the page should keep.
- **Limit:** I can't exclude uncommitted edits to frozen files between 21:12 and 23:28 other than through the row hashes. `check_freeze.py` ran once, at the start.
- **"First sitting" needs care:** New York's questions come from X2.7, and X2.7-2.9 ran on this map. It's first for this machine and prompt, not a never-seen map.

## Were the r1 harness repairs legitimate? Yes
- **The freeze changed in exactly three entries between `dd5f4e96d9` and now:** `t8/fw/r1_check.py`, `exam/stock_r1.py`, `exam/R1.md`. The frozen `R1.md` (6,501 bytes) is an exact prefix of today's. Nothing differs from `FREEZE_r1.json` now.
- **M1 check:** the saved parts show 0 in the mismatch column, and the old check could never pass. The repair also tightened the proofs' lines. It changed nothing tested.
- **Stock start:** the void plan (`void_r1_start1/plan_r1.json`) carries sentences as starts, so 0 differing would have passed without touching the rule. The fix makes the test harder, with the same ids 910000-2, chosen by rule before the run. Its folder is empty, and no comparison was made. "About two minutes" looks generous (log last written 02:15:53, fix committed 02:16:55): trivial.
- **Timing:** both repairs precede the first r1 Qwen row (D1m start 02:22:09). The CPU exams (names, D4m, D2m) ran before the repairs, but neither repair touches them.

## Is the revision legitimate? Disclosed, but it stretches the rule
- `REGISTRATION.md:40` allows a revision "after a miss" in a paragraph about bars. `AGENTS.md` says "Stop at the first failed gate". No gate failed. So by plain reading the revision wasn't triggered. `R1.md:3` says this is a reading under delegation, which is honest. It's Theo's call, and it should be put to him, not assumed.
- **Cost:** the one revision is gone on a non-failure. If a real bar misses on the same exam family, nothing's left. Climb says "the revision is spent", but doesn't say what that closes off.
- **The adoption reading is honest but weak.** It was set before the run, it's met, and the pre-run critic expected it to pass by construction: right 100 of 100 was the likely outcome. It reads only the new 100, so the place where r1 does harm (E1, clean wrong lines 0 to 5) can't affect adoption. "Adoption reading met" should be followed by that.
- **"Nothing is re-scored" (`REGISTRATION.md:40`).** It's kept for the frozen file, and the frozen results are given first. But a headline of 300 includes the 53 re-scored; see B4.

## Is 300 of 300 misleading? Yes as a headline. Is the rule sound? On New York, yes
- **Gold is independent of the code.** All 300 golds start from a handle; reflib's rule branch can't fire on them. My own walker, with no reflib, reproduced all 300 from the name Qwen wrote using my own copy of the rule, and all 100 file golds use the file's handle.
- **Gold isn't logically independent of the rule.** A question's start handle was chosen by walking the first leg's line, so it always has that line. If exactly one same-name node has it, it's that one. **The rule can't lose on any question built this way.** So 300 of 300 says the rule fits the generator, which was certain.
- **Could the rule be wrong and still match?** Only if Qwen writes the wrong line, and in this template it never does. Then a shared name resolves to the wrong platform, silently where it used to refuse. That's untested. On practice hard wording 16 of 100 aren't right, some on a wrong query, so the template exam can't see this cost.
- **In its favour:** of 720 pairs, 693 narrow and 27 stay refused (4 same-line: 36 St R, 7 Av B, each direction; 23 are `transfer`). My search found **0** cases where the rule picks one node while another same-name node sits on the same line in the other direction or as a terminal. So on this map, a right line always gives the right station. Machine, reference and reflib agree on all 720.
- **Sample:** generated 100 are all unique names, up to 4 stops, 5 stop-line golds. The new 100 are all shared names, 6 stop-line golds. The file's 100 have 0 stop lines, and 53 shared names. All two-leg, one template. The file's one-leg and split chases weren't asked of Qwen. `path` and `cheapest` were never offered to Qwen on New York; the 500 "routes" are scripted.

## The gap: D1r and E1 against the stock comparison
PATH says these aren't counted. I replayed their saved calls on the simulator with coverage, on CPU, and took off what baseline, window and each build's own stock runs (lockstep, r1's job and sample) compared. It uses the machine exams' prompt, so treat the numbers as close, not exact. The reference machine agreed on every replayed call. I stopped the r1 names part early, at about a quarter of its 720 one-leg calls, as it was adding almost nothing (0 gates, 5 channels); every other exam replayed whole.

| | Stated | Whole exam, my replay | Added by |
|---|---|---|---|
| Frozen, not compared | 26 gates, 344 channels | **about 41 gates, 390 channels**, of about 11,750 and 5,600 reached | E1 adds 16 gates and 54 channels; D1r adds 0 and 3 |
| r1, not compared | 24 gates, 243 channels | **about 68 gates, 379 channels**, of about 11,780 and 5,600 reached | E1 adds most: 44 of its 49 uncompared gates are beyond r1's machine exams |

**So how big is the gap? Small against the circuit, but about 1.6 times the stated gates on frozen and nearly 3 times on r1, and it sits on the launch item.** The window has no call using the `closed` field. E1's path is compared only by its 2 lockstep conversations (about 28,000 and 30,000 positions), and r1's second turns reach more than frozen's did, because all 40 got there. By the registered bar's own logic, E1's results are the least carried by stock. Reads and writes are all compared on both builds.

r1's own stock runs add only 3 gates and 38 channels beyond the frozen window. The rule's new branch itself is compared, through the three-call job.

**Replace PATH:31's sentence and PATH:37 with:** "Reviewer's replay, not a registered measure: with D1r and E1 counted, about 41 gates and 390 channels reached and never compared on the frozen build, and about 68 and 379 on r1, mostly on E1's write path." Better still, run a short stock window on E1's and r1's calls before publishing the edit claim, if the 4 hours can be found.

## Numbers recounted from raw rows

| Claim (PATH) | Recount |
|---|---|
| D4m 500 of 500 | 500. My own BFS agrees on length, validity and `NOPATH` (46). |
| D2m 264, 11,736, 12,000, 600 | All match, frozen and r1. Kinds 135 station, 57 stopped, 72 `CLOSED`. My own closed walker agrees on all 12,600 wants. Bodies identical frozen to r1 on 25,140 rows. |
| D1m 147, 0, 0, 53; Wilson 67-79; file 47, generated 100 | Match. Host 147, same call 200. Unasked `closed` 0. Reserved ids 0. Stock 18,149. |
| 76 names, 193 of 496; cities none | Match (28 cities). Random graphs differ; see above. |
| Post hoc 53 of 53 | Match, by my own walker. |
| D1r 149, 144, 120; stops 0 of 5 | Match. **"Of the 51 refusals, 2 rightly, 25 wrongly, 26 budget" adds to 53.** Correct: 53 refused; 2 Qwen fixed itself by calling again with a handle (ids 104, 136), which is why the line count is 149; of the other 51, 25 replied wrongly (23 repeating the start name) and 26 ran out. |
| E1 frozen: 40; 19; 24 reached; 3 both, 2 neither; 19 of 19; 13 (3, 7, 3); 28,096 | All match. The 3 "silently" are limit lines; see B5. |
| Window 42 calls, 335,703, 0; flips 8 of 8; 58% | Match. Plan: 24 `path`, 20 `chase`, 1 `close`, 1 `reopen`; **none uses the `closed` field Qwen uses**. |
| Remainder 26 of 11,535; 344 of 5,417 | Match. |
| r1 names 720, 693, 27 | Match, by pure count and from the file. |
| r1 D1m 300; 200 same; job 16,264; sample 21,630 | Match. Host 300. Three stock calls by name; sample of 4 holds one shared question (910021). |
| r1 D1r 300; 225; 286; stops 0 of 11 | Match. |
| r1 E1 40; 33; 40 reached; 33 of 33; 14; 6; 5 | Match on lines. r1 lockstep 29,919 positions, 0 differ (not in PATH). |
| r1 remainder 24, 243 | Match, machine exams only. |

## NOTES

- **D1m's second bar:** the transcript-agreement bar is UNRUN by registration. PATH doesn't repeat that.
- **Machine exams never test name lookup on New York's data:** all 600 chases and 500 paths start from handles. r1's name check covers one leg. Frozen D2m closed 12 shared-label stations of 20, by handle only.
- **D2m is narrow in places:** 264 of 12,000 affected (2.2%). Only 135 are a new station. Closures use the `close` tool, not the `closed` field.
- **`TOOLONG` on Qwen's calls:** writing `closed` and `reopened` together overflowed the capture or was refused, on 4 of 7 missed reopens (r1). Loud, but it's why reopen isn't higher. Frozen had 3 of 5 such.
- **E1 r1 and frozen use different draws,** so compare with care. Wordings identical, and seen.
- **Replies after a refusal still invent:** `nyc:163` replies with the closed station's name after `NONE`, a plain wrong answer.
- **Stale in PATH:** "Still open before the freeze" and the rung 5 row "Not frozen" predate the freeze. Rung 3 and 4 entries are fine as history.
- **Mountain:** "Qwen writes the query" is marked done with a missed bar. "Improving on practice data" is paused. Shares are stated as judgement, which is fine.
- **Budgets:** I didn't audit them; nothing suggests a breach.
- **The corruption control** hasn't been repeated on these tables, as PATH says. Level 3's "Every table number... match" should carry that and the 250 reserved ids.

## What I recomputed and what I didn't

**Recomputed:** all rows in `nyc`, `nyc_r1` (machine), `nyc_d1m`, `nyc_r1_d1m`, both host files, `nyc_d1r`, `nyc_r1_d1r`, `nyc_edit`, `nyc_r1_edit`; independent walker and BFS for gold; the rule's hazards on the whole graph; coverage set arithmetic from logs; a CPU replay of D1r's, E1's and r1's calls for coverage; freeze hashes against git at six commits; prefix check on `R1.md`; both void and real plans; reading of the r1 patch in `reflib.py` and `gen.py`.

**Not checked:** anything on stock (I read saved comparisons only, and didn't rerun `check_trace`); the firmware's rule by execution beyond the replay's agreement with the reference machine; `1.1 billion machine tokens` on climb; the fuzz classes; `t8/fw/results/r1/*` beyond logs; the dev window (27 calls); `ctrl/`, `lines/`, `tok/`, `speed/` claims on climb, other than noting round 3's corrections weren't applied; reply marking by eye beyond the samples quoted; whether New York's graph is faithful to the real subway; GPU block dates. My replay used the machine-exam prompt, not each flow's, so coverage is close, not exact.
