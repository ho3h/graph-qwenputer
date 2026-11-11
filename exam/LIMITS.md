# Mapping the machine's limits (3 Nov, Theo: "Yes, map the limits")

Machine only, r1's executor, reference machine beside it on every call, on the mini's CPU, after every-station finishes. It replaces J in `exam/AFTER.md`, which is dropped unrun. Generated graphs only, by seed `20261107:limits`, so no sealed or downloaded data. Items `exam/items_limits.py`, runner `exam/run_limits.py`, score `exam/score_limits.py`. No bars and no build change: nothing here touches an earlier result. Registered before running.

**Fit.** At 1,024 nodes, search for the largest edge count that loads, on one relation and on 8. **Prediction: 4,300-4,900 edges at 8 relations.** The compile-time table already says 4,000 fits and 6,000 doesn't.

**Shapes, 1,024 nodes or the largest that fits:** a chain, a ring, a star, a binary tree, a 32 × 32 grid, a scale-free network, and a densest-that-fits random graph. Each gets 40 `path` calls by seed, the 5 longest pairs, 40 `chase` calls, and 5 closures, each scored on 20 chases. Answers from reflib, checked against `edits2/oracle.py` where it applies.

**Scale.** Scale-free graphs at 64, 128, 256, 512 and 1,024 nodes, same calls: tokens against size and hops. **Prediction: `path` costs grow about linearly with nodes visited; roughly 1,000-2,000 tokens per hop on a chain, so the 1,023-hop chain trip takes 1-2 million tokens, under the 4,000,000 call limit.**

**Edit table.** On a 256-node graph, add edges one at a time with `link`, up to 300, then remove them. **Prediction: the first refusal is `FULL` at 256 added edges, as the limits test says; every line equal to the reference machine.**

**Predictions overall:** same tokens as the reference machine on every call. Reflib differences only at the edit table's refusal, if at all. A call hitting the 4,000,000 limit is reported as the machine's limit.

**Budget:** today's rates, 3.5 s a `path` and 0.4 s a `chase`, plus the longest calls at about 8,000 tokens a second: about 20,000 s of worker time × 1.5 / 8 workers = 3,750 s; hard stop 13,000 s, gated at a unit's start.

Note before any machine call: building the items put the fit above my 4,300-4,900 prediction, which came from a table with 16-byte names; these use 9-byte names, and the search's upper bound was raised to 30,000 once its first run sat on 6,000. The prediction stands as missed.

Results, 3 Nov, not reviewed (`exam/results/mini/limits_score.json`). All shapes: 0 differences from the reference machine and reflib on every call. Fit at 1,024 nodes with 9-byte names: 6,880-6,886 edges. **The 1,023-hop chain trip took 360,976 tokens: about 353 a hop, my 1-2 million prediction missed high.** Scale-free routes grow about linearly with nodes visited: at most 8,979 tokens at 64 nodes, 122,140 at 1,024. **The edit-table unit is void: my items called `link` with the wrong argument name, so all 300 returned `BADARG link`.** A corrected run replaces it, same 300 calls, `exam/limits_edits.py`.
