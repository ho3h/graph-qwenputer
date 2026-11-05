# X2.10 round 6: critical review (the post, `web/template.html`, and the runs behind it)

Reviewer: critic subagent, 3 Nov. CPU only. This is the only file I changed. I opened no sealed data. I didn't read `reviews/round6-steelman.md`. I saw the top of `round6-coldread.md` while looking for house rules and took no findings from it.

## Verdict

**The counts hold. The post isn't ready to publish until the blockers below are fixed.** Every exam count I recomputed from saved rows matches, and the firmware and reference logic hold up on the 18 one-station names. No run needs repeating. The problems are in what the words say about those counts:

- One sentence is false: "the machine's whole state" returns. The hash covers 10 named fields, and scratch memory differs.
- Three numbers are wrong for what they label: 6,338 tokens, "about a minute", "about seven times".
- Two showcase scenes are the kindest available choice, with nothing saying so. The T scene quotes the wording that copies a worked turn. The reopen scene comes from the frozen build, and on the later build Qwen missed the reopen on this same trip, with a different sentence.

## BLOCKERS

### B1. "The machine's whole state matches" is false (scene 8)
`t8/fw/edit.py:59` hashes only `n_closed, closed_bits, n_add, n_dead, n_edits, add_a, add_b, add_r, add_w, dead_`. `edits2/DEVLOG.md:31,55,63` says leftovers differ on all 159 units, with graph state identical; its taint and scrub runs found that scratch reached no answer. Registers and scratch differ after a reopen. On r2 the hash doesn't see new stops either: in `lines2` the sha stays `b4b3c9dba00b20ea` after `add_node`.

Replace the heading with: **"Reopen it, and the stored graph returns exactly."**

Replace the sentence with: "The square goes dark, and the graph state the machine keeps, every closure and edit, matches where it started, word for word: `b4b3c9dba00b20ea` before, and `b4b3c9dba00b20ea` after. Scratch memory differs, and in the calls I traced none of it reached an answer."

In "So why bother?", replace "read it, compare it and restore it word for word" with "read it, compare it and return its stored graph word for word".

### B2. The trip's token count is another call's (scenes 4, 5)
6,338 is the **reopen** call on the frozen build (`nyc_edit`, nyc:198). The open trip on the page is 5,392 on r1 (`nyc_r1_d1m` id 198, and the stock sample) and 4,898 on the frozen build. r1's two-leg mean is 5,391.

- Scene 4: replace "This trip takes about 6,000" with "This trip takes about 5,400".
- Code, in `run()` and `answer()`: `6338` and `"6,338"` become `5392` and `"5,392"`.
- "So why bother?" and the Rube Goldberg FAQ: "about 5,000 tokens" becomes "about 5,400 tokens". The old figure is the frozen build's and r1's is the one shown, so the page should use one build.

"About 50" holds: the mean is 50.8, and this call is 49.

### B3. "About a minute" and "about seven times" don't follow from the rows
Real-weights rates, all with lockstep running:

| Source | Rate | Per question |
|---|---|---|
| `nyc_r1_d1m` stock sample | 71.8 tokens/s | 75 s |
| `stock_partial` (shared GPU) | 59.6 tokens/s | 91-94 s |
| The whole edit exam | 57.6 tokens/s | |
| Plain `model()`, alone on the GPU | 12.6 tokens/s (5,221 in 414 s) | 412-494 s |

The ratio is 4.6 to 5.7. "Seven" appears to be 7 minutes divided by "a minute". I can't exclude that lockstep slows the driver figures, and no unlocked real-weights rate is saved.

- Scene 4: replace "on the real weights it takes about a minute" with "on the real weights it takes a minute or two".
- "So why bother?": replace "a lookup takes about a minute" with "a lookup takes over a minute".
- FAQ: replace "about seven times faster" with "about five times faster, measured with a checker running on the driver side".

### B4. Scenes 7 and 8 come from the frozen build, and the later build missed this reopen
nyc:198 ("Flooding...", "Repairs are done...") ran on `bcf1a1dc`. On r1 the same trip came with other sentences. "Trains are stopping at Bowling Green once more." got no `reopened`, the state stayed `4dd3494a9cc7f3dd`, and Qwen said Nevins St (`nyc_r1_edit_stock`). The page's "ran on the real weights" is true, and the sha values and lines match the rows. It reads as the current build, and a reader who opens the repo will find the miss.

Replace "That conversation ran on the real weights." with: "That conversation ran on the real weights, on the frozen build. In the later whole exam the same trip came with a different sentence, "Trains are stopping at Bowling Green once more", and Qwen wrote no reopen: the stop stayed closed and it answered Nevins St. Reopens there: 33 of 40."

### B5. The T scene shows the wording that copies its worked turn
Worked turn (`exam/lines_run.py`): "A new W train starts today, with two brand-new stations, Reed Pk and Sage St. Northbound it runs Ash Rd, Reed Pk, Sage St, Oak Av."

The scene: "A new T train starts today, with two brand-new stations, Cinder Park and Larkmoor Sq..." "The T train has been cancelled." also copies the V turn. The later section says "one wording nearly copies an example" and doesn't say this is the one shown. nyc-t2:0 also ended on budget, with its last reply wandering into "if we assume the T train was reactivated... Cinder Park".

Every token in the scene matches the row: @496, @497, the three links, chase, "Larkmoor Sq", 5 writes. The choice of conversation is the problem.

**Fix: use nyc-t2:1.** It's on the real weights, in lockstep, 41,676 positions, 0 differ, status answered, and it uses a different announcement and cancellation wording. The links scored 15 of 15 on the three other wordings and 4 of 5 on the copied one, so the honest scene is also a stronger one.

Replace scene 11's second and third paragraphs with:

> A subway map is a graph, and what's in memory is a small graph store: stops, typed connections, reads and writes. It knows nothing about trains. So: "The T line has opened, and it adds two new stations: Foxglove St and Willow Gate."
>
> On a later build, with a map that already had an empty T relation and worked turns showing how, Qwen added the stops, linked them, rode the line and read it back, then removed the links when told "They've scrapped the T line", all on the real weights in this conversation. The two new stops stay until the conversation ends. Over 20 conversations, 2 on the real weights and 18 on the simulator, it added the stops on all 20 and linked the line on 19.

Code: in `buildT` use nodes 444 (Roosevelt Island) and 361 (Junius St), and the names Foxglove St and Willow Gate. Row text: `link Roosevelt Island > T northbound > Foxglove St`, `chase Roosevelt Island, T northbound 2 > @497 Willow Gate`, `Qwen: Willow Gate`. `D.tbeverly` in `build.py` needs the same change. The curve between the stops is invented; add to the button or caption "The new stops' positions are drawn by hand".

Rename the button "Replay the build".

### B6. "Nobody tells Qwen when to use it" overclaims, and "it didn't" over-call is half wrong
The system prompt opens: `You answer questions about the graph "nyc" with the graph tools.` All 6 worked turns call a tool, and none declines. That priming points toward calling, so the 0 of 60 is better evidence than the 30 of 30. Other-city routes called 20 of 20, above my predicted 8-18, which is over-calling, on a graph the prompt names "nyc". 8 of those 20 replies are the raw `NONE` line. The demo shows a graceful one. The section also never says which build.

Heading: **"Qwen decides when to call it"**.

First paragraph: "No code routes your question to the machine. The system prompt says "You answer questions about the graph "nyc" with the graph tools", and six worked turns all use one; nothing says when to skip them. So on the later build I asked it things it should and shouldn't use the map for. Pick one."

After the table: "I predicted it would over-call on subway trivia, and it didn't: 0 of 30. On other cities it did, calling on all 20, above my 8 to 18, on a graph the prompt names as New York, and 8 of those replies were just the raw refusal. These were clear cases I wrote myself; a murkier one like "is it quicker to walk from Union Sq?" hasn't been tried. Answers it gives by itself are unchecked, and some are wrong: the first line's route in the example above, what OMNY stands for, whether the subway has rats."

The chosen demo "When did the subway open?" shows "from 14th Street in Manhattan to 207th Street" with no warning. By my knowledge the first line ran City Hall to 145th St; I didn't look that up. Either the sentence above stays or the chip goes.

### B7. The map read-back says more than it shows (scene 6)
Of the 131,072 bytes, 52,519 are the map image and **78,553 are zero padding**: the code pads the image with zeros before comparing, and the saved `drom_from_weights.bin` is zero from byte 52,519 on. 37,457 bytes are nonzero. The strings "High St" and "Bowling Green" are in it, so it is the map.

- The table is compiled as read-only. In the code I read, `c.table` builds it and only load paths read it, so no instruction could change it. What the read tests is that the numbers stayed within rounding through the run.
- `read_drom` uses `round()`, so drift under 0.5 wouldn't show.
- The comparison is against the bytes the loader itself injected.
- No corruption control was run on this reader.
- "A real run" was teacher-forced on the reference's stream: 7,979 owned tokens predicted, 0 wrong, on r1, 8,042 stream tokens.

It's a fair check, and a much smaller one than the sentence suggests.

Replace with: "After a whole trip on the real weights, 8,042 tokens with the tokens supplied and every machine token checked, I read the map table back out of the state: all 52,519 bytes of map, plus zero padding to 131,072, matched what was loaded. That table is read-only, so this shows the map stays exact while the machine runs. It came from the loader, and the weights alone don't hold it."

In the "Isn't this just a tool call?" FAQ, "the map reads back byte for byte" stays. The wrong-map control ("0 of 600") ran on the simulator, and 435 of those are `NORELATION`. Add "on the simulator".

### B8. "Try doing that by editing a model's weights." has no measurement behind it
PATH rung 6: "The weight-editing comparison is a draft (`edits/WEIGHT-EDIT-PLAN.md`), not registered." That makes it a taunt about an unrun test. **Cut the sentence.**

### B9. The plain-loop claim needs its scope (scene 5)
The code does what it says. `plainc` and `plaind` take argmax over the whole vocabulary through every layer, with no stop rule. `first_difference` is null through the full stream on all 3. `plaind`, through plain `model()`, has the same `gen_hash` as `plainc` on the shared question, `dcb3e07ded7fd430`. So "the answer came out of the model's own layers" is fair for the answer.

Three limits are missing from where the claim is made:

- Code outside injected the firmware and map after prefill.
- The trips were reads only, on r1, with no closure or write.
- It never stops, and printed junk HTML and repetition afterward; the junk is only disclosed two sections later.

Replace with: "The answer came out of the model's own layers. To check, I loaded the memory, then ran a loop that only takes the model's top pick. On 3 of 3 trips, with no closures, it printed the right answer, and then kept printing nonsense, because nothing told it to stop."

In the "Isn't this just a tool call?" FAQ, after "the model's own top pick printed it", add: "on the 3 trips I tried that way; the rest matched those layers token by token on samples".

### B10. Unlabelled simulator and replay on the page
- Scene 10 (blackout) doesn't say simulator. Add after "matched the first 600": "This ran on the simulator too."
- No sentence says the ride is a replay. Add to the intro, before "Scroll": "Everything below replays saved runs."
- Scene 3's caption prints `chase start: High St / legs: ...`, which is tidied. Qwen wrote `<function=chase><parameter=start>...`. Show the real text, or add "(tidied)".
- The later-build sentence in the "broke my first attempt" section is fine. The writes sentence is on r2 with far less proof: 2 real-weights conversations, and no frozen exam. "What's inside" says "built as a separate version; 18,996 random calls on it matched the reference". Add: "It hasn't had a frozen exam, and only 2 of its conversations ran whole on the real weights in the build test. Those random calls were 1,583 of the 2,000 sequences I planned before the time budget ended."

The chooser exam also had 2 lockstep conversations. Say "2 in each test" if both are meant.

### B11. External wording
- **"One asked if it was..."**: the commenter (rvz) asserted it: "So this is yet another rube goldberg machine", then ended "Why?". Replace with: `One called it "yet another rube goldberg machine", and asked why.`
- **704 and 146 are already out of date.** The API returned 705 and 147 when I fetched it. Replace with: "with over 700 points and nearly 150 comments".
- **"On October 29"** is UTC; the story was posted 00:25 UTC, the evening of the 28th in New York. Keep it, or say "In late October".
- **"monitors a model can't quietly edit"**: Agrawal's page, as paraphrased to me by a fetch tool, says monitors the model can't switch off. Replace with "monitors a model can't switch off".
- **"compiled into numbers by Divyansh Agrawal"**: this circuit is his plus 85 FFN units for normal-token printing (`tok/DEVLOG.md:95`), and the firmware is mine. The page never says so. Replace with: "compiled into numbers by Divyansh Agrawal's compiler, with one small change of mine so it can print ordinary tokens." Credit is otherwise adequate: named, linked twice, in the footer.

## NOTES

- **"Never once" is 0 of 11.** Recounted from `nyc_r1_d1r`: 11 stop lines, 0 say it stopped. Write "on all 11 trips that stopped early, it never said so". Without that instruction it's 1 of 11, so the cause isn't only the instruction.
- **"16 new stops" is unmeasured.** Fuzz sequences are 12 calls, so none can reach it: `add_node` gave added 5,910, already 313, BADARG 248, FULL 0. Either run one direct call on the mini, or write "16 by design, not yet hit".
- **Corner difference by reading, not run:** firmware `parse_handle` is false for `@foo`, so it adds that stop, while reflib returns `BADARG name` for any `@` start. The fuzz only tried `@7`. No published row touches this. Fix or list it.
- **"The computer gets you a few things a tool outside the model doesn't"** will draw fire. A logged deterministic interpreter also has readable state and replay. Only "state lives in the model's own run" is unique. "No server and no sandbox" still means running a driver and an 18.8 GB model. Suggest: "Its state lives in the model's own run, so it travels with that run...".
- **The T relations were added to the map file** (`exam/items/nyc_t.graph.json`), so the "This is New York" map differs for that scene. B5's wording covers it.
- **The T ride-after-removal lines** are 17 of 19, and "says so in reply" isn't on the page. Fine as is, since the last-turn counts aren't claimed. The `after_reply_has_answer` 7 of 19 is a poor measure, and I wouldn't publish it.
- **`score_lines.py` is sound for what's claimed,** with one gap: `links` doesn't penalize extra links. My recount found extras only on nyc-t2:16, already a miss. `choice`'s "called" counts parsed calls; 0 replies in any arm contain call text left unparsed.
- **Taken out of the fix list:** "T color" is the MTA's #00ADD0 by my memory, unchecked. Harmless.
- **`build.py` hard-codes `"right": True`** on the blackout's last ops entry and the caption's "right on all 30" is fixed text. `mini/score.json` supports it (960 of 960), so no change to the page.

## What holds

| Claim | Recount |
|---|---|
| Plain loop 3 of 3, plain `model()` 1 of 1 | Rows; streams 4,921, 6,080, 5,054, no differences; hash equal |
| L2 20 and 19 | Own recount; 3-link check on rows; all scene tokens for t2:0 and t2:1 |
| Choice 30, 0, 0, 0/20, 20/20, 20/20 | Own recount, firmware `cce657b2` on all 130 rows |
| 475 of 496; 21 on Staten Island | Page data |
| Five Fulton St, four 125 St, three 14 St and its lines | Map file |
| 1 of 100 alone | Own recount; id 127 |
| 2,186 total on the map's node data | Page data; `mini/score.json` |
| Blackout 2,552 = 496 + 960 + 496 + 600; every station; fuzz; 500 + 12,640 etc. | `mini/score.json`, `r2_more_score.json` |
| sha sequence b4b3 > 4dd3 > b4b3; lines | nyc:198 frozen row; map_out's 4dd3 |
| 256 edit limit, 44 FULL | `limits_edits.json` |
| 18,996 calls, 6,471 `add_node`, all same and equal | Own recount |
| 225 of 300 strict | PATH and climb page cite it; row `correct` flags not used for this |
| HN quote | Algolia item 50282838 |

**One-station rule.** On all 76 shared names, I rebuilt the rule from the map file with my own code. Exactly 18 pass, and all 18 are complete cliques on transfer edges, so the rule's star check from the lowest handle is equivalent here, even after one platform closes. Widest is Grand Central, 311 m. By my knowledge all 18 are real free-transfer complexes. No other name has connected nodes, so none is wrongly refused by the star shortcut. Close pairs left separate (Rector St 54 m, Wall St 252 m, 34 St-Penn Station 286 m) are separate stations in life too. Firmware and reflib read the same on the rule.

**Could they agree wrongly?** Both came from one commit and one author, so yes in principle, and the "reviewer's short script" FAQ covers r1 only. I independently recomputed all 2,000 S3 by-name routes with my own BFS and name rule: 1,236 paths valid and minimal, 572 ambiguous as expected, 192 NOPATH as expected, 0 differences. Not independently recomputed: S2's closed-station answers by my own walker.

## Not recomputed or not checked

- The 335,703 positions, 8 flips, 0.3%, 40 of 11,750 gates, 795,589: round 5 checked them; PATH's newer window figures are separate.
- D1, frozen and practice-pool numbers, the E1 table, 23 conversations, 0 of 900, 97 of 100.
- `D.game`, and `D.ask` beyond two rows.
- qwenFS and qwenGPU's descriptions, the NTM citation, "some people were delighted".
- The page rendered. I read the template only.
- Journeys, gaslight, K2 and I, which the post doesn't cite.
- House rules: 0 em or en dashes in the visible text. No "not X but Y" construction found in my scan of negative sentences. "It's a toy store, and it's also real" and "Both, and I say which" are fine.
