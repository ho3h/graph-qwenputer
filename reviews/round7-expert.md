# X2.10 round 7: expert review

T = `web/template.html`, P = `PATH.md`. Counts rechecked hold.

## 1. False or misleading, by harm

**Blockers**

1. **Asymmetric scoring (T152-183).** Qwen's rows mark its words; machine rows mark the printed line. On the file's 100 Qwen's words score 78 strict (my count, `nyc_r1_d1r_replies.md`; P37). Heading: "After the fix, the machine printed the right station on all 100 of the file's two-leg questions." Add: "Read back by Qwen, 78 of those replies were exactly the station. Across all 300, none of the misses named a different station."
2. **Abstention sold as an advantage (T241).** P28, P30. Replace: "At the frozen sitting the printed line gave 0 wrong and 53 refusals, where Qwen with the map gave 36 wrong. A normal tool refuses the same way. When Qwen read those refusals back, 25 of the 51 it didn't retry became wrong answers."
3. **"No outside program computes the answer" (T247).** `exec/REGISTRATION.md` limits that claim to stock runs. Replace: "On the real weights, no outside program computes the answer. Most exam rows used the simulator, an outside C program I trust because it matched the real weights on samples."
4. **Wrong build (T191).** 21 of 11,589 is r1, this exam's build (`after/remainder.json`). Replace: "on this build, 21 of the 11,589 circuit gates reached have never been compared."
5. **False chronology (T122).** The walkthrough is r1, as showcase T will be (AFTER:100). Heading: "That's one trip. The test came first." Open: "One good trip proves little, and this walkthrough came after the exam."
6. **Omitted shared-name closures (T191).** 193 of 496 stops share names (P29). Add: "Shared names went badly: in 38 conversations the machine refused every first call, 2 closure turns ended right, and 3 were silently wrong." (P61, `after/shared/score.json`.)
7. **Dek (T106).** Those closures were direct simulator calls. Replace: "I loaded New York's subway into that computer's running memory, tested closing every station, and got the model to add a line to it."

**Should fix**

8. Unlabelled machine, despite T117. T130: "Qwen ran for real here, and the simulator stood in for the 11 added layers." T192: "2 conversations ran on the real weights, 128 on the simulator."
9. T183 "every one of these rows": use "in both machine rows". T115: 10 of 600 is 1 in 60. T310: use "same stored graph as before".
10. T119 calls the map RAM, but its table is read-only (upstream README; AFTER:62). Replace the Agrawal sentence: "Qwen's layer type, Gated DeltaNet, keeps a running state and can overwrite one row of it exactly. Part of that state works as exact RAM and holds the closures, and the map sits in a read-only table beside it."

**The map**

- Track holds: rerunning `geometry.py` gives 0 straight fallbacks in 556 pairs. Straight hops come only from T279, transfers and closure skips; `d-close` shows a chord over the harbor. Add at T120: "The straight line is my drawing of the skip."
- T114 "each line in its own color" is false (`build.py:18`). Use "in MTA colors".
- Trip routes are Python walks checked at the endpoint (`build.py:112-143`), straining T111.
- Pins are fair matching with unfair wording: five of six "alone" pins are the start, and `build.py:148` pins the first node of a shared name (Times Sq has 4). T152: "Pick a trip. I draw the route from the map file, since the machine prints only the last station. Orange marks the station Qwen named without the machine, at the first stop with that name if several share it."
- The T start label sits under the deck (`d-build`); move "drawn by hand" (T329) to the body.

## 2. Attacked first

1. "Inside": the driver injects firmware and map, the plain loop covers 3 read trips, and zeroed-layer and write-loop controls are unrun (P66).
2. A rule fitted to the same 53,.
3. 295,414 unchanged: a machine ignoring closures scores all of it, and 69 stations move nothing.
4. Independence (T251, T254): one model family wrote, ran and reviewed this.
5. "One thing is new" (T241) resembles a saved state file.

## 3. Figures

**Wanted:** a claim ledger (number, build, machine, Qwen in the loop, prediction, file), the most valuable; a token-ownership strip, 50 against 5,392; closed bits from saved rows, since T289 paints a JavaScript set and phones hide the grid (T95); a browser of all 100 trips and every miss.

**Adds nothing:** "Hover or tap" (T182), as counts are printed; the counter tied to distance (T306); the FX figure, which duplicates `d-fix`.

## 4. Terms

- **Build:** "later" means r1 at T128 and r2 at T192. Name them frozen, fixed and writes.
- **Memory:** name Gated DeltaNet state once, or readers assume a KV cache.
- **Reference machine (T128), positions (T127), firmware (T192):** undefined at first use.
