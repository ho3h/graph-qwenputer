# Round 17 expert review

Bare line numbers are `release/README.md`.

**Strongest hostile comment:** "A tool call at 55 tokens a second. Most numbers come from a C simulator, a script loads the data, and the author says an ordinary tool ties. What is this for?" The page stops at "The difference is where the work happens" (item 3).

## Blockers

**1. "No training happened, and Qwen's 32 layers are bit-identical."** Also the diagram and lines 5, 159. The saved check (`tok/results/t4_qwen_tensors.json`) compares 424 tensors between the author's two merged files. Against Qwen's release the shapes differ: `in_proj_a.weight` is [32, 3968] in `x210-tok` and [32, 2560] in Qwen3.5-4B, and `chipformer.json` says `"muted": true`. Anyone who diffs the Hugging Face file sees every layer tensor differ. Replace: "No. I trained nothing. In the model file, Qwen's 32 layers are 3,968 dimensions wide where Qwen's release is 2,560 wide, and added columns silence Qwen's layers on the computer's tokens." Whether Qwen's original values are unchanged needs the author's check: no comparison with Qwen's release is saved.

**2. "…and let Qwen reason step by step, Qwen got 54 right and 36 wrong".** `exam/mapped.py:55` sets `enable_thinking=False`, with a 1,024-token limit. The page says "turned off Qwen's reasoning" for the other arm, so this reads as reasoning turned on. No arm ran with reasoning on, and the text drops the 10 unfinished. Replace: "When I pasted the relevant lines of the map into Qwen's prompt and asked Qwen to list each stop before answering, with Qwen's reasoning still turned off and a limit of 1,024 new tokens, Qwen got 54 right, got 36 wrong and did not finish 10." Same fix: chart label, the memorize answer, line 227.

## Should fix

**3. "so accuracy is not a reason to build the graph-qwenputer."** The page concedes accuracy and speed and names no use. Add to the tool-call answer, from line 310: "I cannot name a production system that should use the graph-qwenputer today. The result shows that an exact part, with a memory that a sentence can rewrite, runs inside a model's own layers."

**4. "so the graph-qwenputer's tests ran on a simulator" and "all 335,703 tokens matched."** Those tokens are 42 calls on the first version (`PATH.md:33`). The fixed version's 300 questions, these 100 among them, ran whole on the real model (`AFTER.md:143`). Replace: "so most of the graph-qwenputer's tests ran on a simulator, a program that does what the 11 layers do, much faster. The fixed version's 100 questions also ran whole on the real model, inside a 300-question exam, and all 1,640,598 tokens matched the simulator."

**5. "Qwen with the graph-qwenputer printed 296 of 300 right."** The 11 layers ran on the simulator, a program outside the model, in a band that opens "Runs inside the model". The real-model run is "Registered, not run" (line 339). Replace: "With Qwen on the real model and the 11 layers on the simulator, the graph-qwenputer printed 296 of 300 right. No sealed-map test has run the 11 layers on the real model."

**6. "all 643,348 calls matched…" and "all 995,198 machine exam calls on the current version matched a reference machine".** The first total is inside the second (`check_figures.py:273`), the second drops "the same firmware", and "machine exam" is undefined. Replace: "A machine exam sends calls straight to the graph-qwenputer with no Qwen. All 995,198 machine exam calls on the current version, the 643,348 sealed-map calls included, matched a reference machine running the same firmware."

**7. "reproduces the graph-qwenputer's answers from the spec".** `check/walk.py` loads the earlier map and covers the first two versions (line 379). Replace: "rechecks 24,600 trip answers and 500 routes of the first two versions from the spec, under the earlier closure rule".

**8. "a closed stop cuts off any train that stops there"**, twice. This reads as the 3 no longer running, yet the new route rides the 3 for one stop. Round 16's prose pass flagged the shift (`AFTER.md:251`: "nothing passes it"). Replace: "Saratoga Av is on the 3, the line you were riding, and no train can pass a closed stop, so the 3 is cut in two at Saratoga Av."

**9. "since that rule does not help someone with a destination, I changed the rule".** `AFTER.md:249`: the change followed a reading of the post, with "the better demo is re-routing". The "Did you change the test" answer omits this change, which changed the expected answers. Add there: "I also changed the closure rule after I read a draft of this post, so that no train passes a closed stop. I predicted 2,100 to 2,300 changed answers under the new rule, and 2,395 changed."

**10. "Large language models get lost on the subway." "And models are catastrophically bad at reading the subway map without help."** Rounds 15 and 16 raised this. Every baseline row is Qwen 3.5 4B with reasoning off, and the 600 questions gave no map and 40 new tokens (`AFTER.md:10`). Replace: "Qwen gets lost on the subway." and "And Qwen, asked from memory with no map, got 10 of 600 trips right."

**11. "I changed the graph-qwenputer once for the exams", then "Later versions added writes, shared names, cheaper routes and blocking."** These contradict, "cheaper routes" reads as the `cheapest` call, and "blocking" is undefined. Replace: "I changed the graph-qwenputer once in response to an exam result" and "Later versions added writes, names shared by connected platforms, routes that cost fewer tokens, and the rule that no train passes a closed stop."

**12. "all 244 questions that ran on the rerouted map".** Add, from `AFTER.md:392`: "I stopped that run at 244 of 300, and the 56 unrun questions all start at a shared name."

## Minor

- "The run script … runs the 11 layers on the simulator." Add, from line 36: "The command `gq.py ask --whole` runs the 11 layers on the real model as well."
- The chart marks Qwen's reply for the baselines and the printed line for the graph-qwenputer. The reply score on these 100 needs the author's check.
- One name each: "second CPU"/"reference machine", "my program"/"firmware", "real model"/"real weights", "version"/"build", "query"/"call".

## Missing definitions

The band uses simulator, the 11 layers, reference machine and firmware before the body defines them. Never defined: exit units, practice cities, trick sentences, strict marking, qwenFS. For experts: "loads the map" means the driver writes the running state directly (README: "injects"), and the page never says which layers hold the state.

## README and TOOLKIT.md

- 191: the blocking build "hasn't had a frozen exam", against line 330, "a blind test of the current build". Round 16 flagged it.
- 149: "`add_node` exists only on the writes and route-fix builds". The blocking build has it.
- 310: "A lookup takes a minute or two". The page's route takes 12 minutes.
- TOOLKIT.md:163: "the firmware that the exams ran" holds for the current build only.

## Holds up

- No driver routing: 6 of 6, and 1 of 1 through plain `model()`.
- 995,198 and 643,348 add up from the README's rows.
- Round 15 and 16 fixes held, apart from items 6 and 10 and README line 191.
