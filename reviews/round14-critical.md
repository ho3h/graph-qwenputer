# Round 14 critical review

## Blockers

**1. "The repo has the steps, and the 18.8 GB model is on Hugging Face."**
Logged out at 14:49 EST, `github.com/ho3h/graph-qwenputer` returns 404 and `huggingface.co/hopski/graph-qwenputer` returns 401. `gh`: private, last push 3 Nov, no `run.py`.
Fix: push the bundle and open both. Until then: "The repo and the model are not public yet."

**2. "I took a fingerprint of everything the graph-qwenputer stores about the graph, before the flood and after the repair. The two fingerprints match exactly."**
Unmeasured on this rule: `r6_walk_sim.json` has no fingerprint, `r6_walk_a1` stops after `close`, and the stage prints "(run in progress)". "Everything" is false: `t8/fw/edit.py:59` hashes only the edit record, and the start value `b4b3c9dba00b20ea` is identical on nyc, nyc-b and another city (`c024_edit`). The README repeats the error.
Replacement: "The fingerprint covers the graph-qwenputer's record of edits: closures, added connections and removed connections. On an earlier build, the fingerprint returned to the start value after a reopen. On this conversation, the result is in progress."

**3. "Qwen writes a reopen call, the square goes dark, and the old route returns."** Also the footer: "This page replays saved runs."
No r6 row has Qwen writing a reopen: `r6_journeys` has no reopen turn, and `exam/r6_walk_sim.py:20` supplies all six calls. Fixed build: 33 of 40.
Replacement: "In the simulator run I supply the reopen call. Qwen's own reopen call is in progress on the real model. The square goes dark, and the old route returns."

**4. "The whole conversation is running on the real model as this page goes up, so the printed answers here come from the simulator..."**
The sentence contradicts step 10's "The answer came out of the model's own layers", and omits a stopped attempt. `r6_walk_a1`: real weights, `chase` 6,279, `path` 39,584, both replies right, `close` written, 75,659 positions, 0 differ, walltime at 3,600 s.
Replacement: "The real model has printed the first answer and the 10-step route, with all 75,659 tokens matching the simulator. That run stopped on a time limit I set too low, during the route around the closure. A second run is in progress, so the reroute and the reopen here come from the simulator."

**5. "Qwen answered straight away and showed no doubt."**
`exam/alone_walk.py:21` sets `enable_thinking=False`, with a 40-token cap, and the question ends "Answer with the station name only." The page and README never say so.
Replacement: "For this test I turned off Qwen's reasoning and asked for the station name only. Qwen said Union Station." Chart label: "Qwen alone, no map, reasoning off".

## Others

6. "On 4 of the 10 tries, Qwen ran out of calls first." `recommend/all.jsonl`: 3 `budget` (0 calls), 1 `cap` (6 calls). Replacement: "On 4 of the 10 tries, Qwen hit a limit first: 3 token limits and 1 call limit."

7. "The driver also decides whether Qwen or the computer produces the next token." `vendor/.../rv/chat.py:6-9`: the circuit's output code sets the owner. Replacement: "The 11 layers signal when the computer owns the next token. The driver reads the signal and keeps the computer's tokens out of Qwen's layers."

8. "The README has every test, every build, the limits..." "Four builds" and the results omit r6. The cost bullet is stale: r6's reroute took 58,901 tokens. Replacement: "The README has the tests, the limits and how to run the graph-qwenputer." Add an r6 row. Label README's 5,890 as the fixed build.

9. "Can I run the graph-qwenputer?" "Yes." `run.py` runs the 11 layers on the simulator. Replacement: "Yes. The run script keeps Qwen on the real weights and runs the 11 layers on the simulator."

10. "Most of the graph-qwenputer is in the model." The model file holds only the computer. Replacement: "The computer is in the model file. The map and the program live in the model's running state."

11. "qwenFS says the qwenFS chat loop only decodes tokens and stops". qwenFS's README has no "only", and adds a runtime that "loads that file's bytes". Replacement: "The qwenFS chat loop decodes tokens and stops, and a qwenFS runtime pages files in."

12. "I asked Qwen 600 subway route questions of the same type." `alone.jsonl`: 300 one-train, 300 two-train. Replacement: "I asked Qwen 600 questions of this kind, half with one train and half with two."

13. "The tokens are the steps of the program..." The 6,279 tokens are CPU instructions and results. Replacement: "The tokens are CPU instructions and CPU results."

14. "about two minutes", "about 11 minutes". `build.py` assumes 58 tokens a second, and `r6_walk_a1` measured 21 beside the exam. Add "with nothing else running".

15. "Now close any stop you like." The cut implies Qwen can close any stop. Tapped closures use handles, with no Qwen. By name, 125 St prints AMBIGUOUS. Replacement: "The stops you tap close by number, with no Qwen involved. In a sentence, a shared name like 125 St gets a refusal."

## Recomputed and confirmed

Routes and reroute against `nyc_b.graph.json`. 10 of 600; 1, 54/36, 47/53/0, 100; tool ties; 2,186; 295,414; 2,552. r6 journeys 15/15, Bay Ridge `NOPATH`. T line 3 of 3, 148,381, 43 minutes. Choice 30, 0 of 60, 20. No-routing 6 of 6; zeroed 0 of 20; wrong map 0 of 600; 52,519. Pushback 10 of 10. October and "in front" match Agrawal. r6a and r6e are running: labels hold. Moved README numbers I spot-checked match saved rows, `PATH.md` or earlier reviews.
