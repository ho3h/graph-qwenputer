# Round 17 critical review of the revised post

**Verdict: READY AFTER FIXES.** Two changed sentences are wrong or unsupported. The replacement for "bit-identical" holds.

## Blockers

**1. "qwenFS is another project built on Qwenputer, and qwenFS puts a file system in the model. The qwenFS chat loop only decodes tokens and stops, …"**
qwenFS's repo (github.com/vixhal-baraiya/qwenFS, README and `qfs/`, read 9 Nov) never names Qwenputer. The repo is not a fork, uses Qwen3.5-2B, and says "its layers are built directly in Qwen3.5's own layer types". No saved record supports "built on Qwenputer". "Only" restores a word that `reviews/round14-critical.md:37` removed.
Replace: "qwenFS is another project that compiles a part into Qwen 3.5's weights, and qwenFS puts a file system in the model. The qwenFS chat loop decodes tokens and stops, a qwenFS runtime loads a file into memory when Qwen reads the file, and qwenFS already has Qwen writing files and links."

**2. "The question file for that map has 47 questions that start at a shared name, and the graph-qwenputer printed the right answer on all 47."**
`data/heldout/nyc-relabelled/nyc-relabelled.questions.json` has 400 questions, and 218 start at a shared name (my count). 47 is the count among the file's 100 two-train questions, the only ones the test took from the file (`exam/AFTER.md:371`).
Replace: "Of the 100 two-train questions in that map's question file, 47 start at a shared name, and the graph-qwenputer printed the right answer on all 47."

## Should fix

**3. "…and adds columns that silence Qwen's layers on the computer's tokens."** Also `release/README.md:5` and the model card. This is Qwenputer's design claim (`mute.py:1-16`), unmeasured here, and the page's driver section says Qwen's replies were "garbage, probably because the computer's tokens had gone through Qwen's layers". Replace: "…and adds columns that are designed to keep Qwen's layers quiet on the computer's tokens."

**4. The saved script does not produce two claims.** No saved code writes `norm_rescale_check` or `outside_block_by_kind` in `tok/results/r17_stock_tensors.json` (`tok/mem.log:278`, an unsaved `python -` run), yet `web/check_figures.py:299` reads them. `bits()` (`tok/check_stock_tensors.py:20`) compares the 48 float32 tensors by value. Add both checks and an int32 view.

**5. Chart label "Qwen given the map, listing each stop"**, beside "Qwen alone, no map, reasoning off" (`web/index.html:241`). The contrast implies reasoning on (`exam/mapped.py:55`). Replace: "Qwen given the map, listing each stop, reasoning off".

**6. "With the map pasted in and each stop listed before the answer, Qwen got 54 of 100, with 36 wrong."** The passive hides who listed the stops, and 10 questions go missing. Replace: "With the map pasted in, I asked Qwen to list each stop before answering, and Qwen got 54 of 100 right, got 36 wrong and did not finish 10."

**7. "A harder set of wordings, on the invented cities that I used for practice, scored 84 of 100, with 9 wrong."** The other 7 are unexplained. `PATH.md:137`: "84 right, 7 loud, 6 limit on a wrong query, 3 silent". End: "…with 9 wrong and 7 refused."

**8. "The fixed version's 100 questions ran whole on the real model, inside an exam of 300 questions, and all 1,640,598 tokens matched the simulator."** True, but 1,640,598 reads as the 100's count. Replace: "The fixed version answered these 100 questions whole on the real model, as part of an exam of 300 questions, and all 1,640,598 tokens of that exam matched the simulator."

**9. `release/launch-posts.md:42`: "Nothing is trained, and Qwen's layers keep Qwen's released weights."** A diff shows 64 changed gains and 88 tensors with an added column. Replace: "Nothing is trained. Qwen's layers keep Qwen's released weights, apart from normalization gains that Qwenputer rescales and columns that Qwenputer adds."

## Minor

- "did not finish the other 10": all 10 hit my limit of 1,024 new tokens (`M1.jsonl`).
- "Nothing was trained." Passive. Write "I trained nothing."
- "If a sentence named the stop instead, a name that several stops share, such as 125 St, would get a refusal." Write "If you named the stop in a sentence instead, and several stops share the name, as 125 St does, the graph-qwenputer would refuse."
- "the rescaled normalization": write "normalization gains". "another city's map": the city was invented (`exam/AFTER.md:49`).
- Terms: "a simulator" and "a reference machine" recur after the page defines both; no sentence ties "firmware" to "my program".
- "Add --whole to the gq.py ask command": the page has named only "the run script", which takes `--whole` too (`run.py:25`).
- `PATH.md:179` and `exam/REGISTRATION.md:15`, both bundled, still say "Qwen's 424 tensors bit-identical" with no object.

## Holds

- My independent CPU rerun, with integer views of every tensor: 360 of 424 equal bit for bit, the other 64 are the two gains of each layer, 65 of 65 norms equal Qwenputer's rescale in bf16, and 88 tensors carry one added column. The local files' SHA-256 equal Hugging Face's.
- Reasoning off (`exam/mapped.py:55`); 54, 36 and 10 recount.
- The 100 two-train questions are in the 300 (`nyc_r1_d1m_score.json`), and 1,640,598 is the whole exam (`exam/AFTER.md:143`).
- Only the 3 stops at Saratoga Av. The draft, 2,100 to 2,300 and 2,395 (`exam/AFTER.md:249-287`); 244 and 56 (`exam/AFTER.md:392`).
- 643,348 inside 995,198 (`web/check_figures.py:273`); the walker (`check/walk.py:4`); the newsstand sentence, on which Qwen closed (E6); 0 of 600 (`control_map.json`); `--whole` (`gq.py:280`); Prospect Park and Tottenville.
- `check_figures.py`: 316,774 checks, 0 failed; toolkit tests, 69 of 69. No new sentence has an em dash, "not X but Y" or "X, not Y".
