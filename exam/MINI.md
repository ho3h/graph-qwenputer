# On the mini: every station, and three treats (3 Nov, Theo: "Great. Do this. Maybe design a few other fun treats to keep the mini engaged")

Machine only, no Qwen: direct calls on r1's executor (`t8/fw/build_r1/writes.elf` ad1abcc6), reference machine beside it on every call, CPU, New York's opened map, the mini's 10 cores. Items are built on the Mac (`exam/items_all.py`, seed 20261105) and answers come from reflib; closures are also checked against `edits2/oracle.py`. Runner `exam/run_all.py`, score `exam/score_all.py`. No sealed data goes to the mini. Registered before running.

## 1. Every station
Each of the 496 stops closed once, on a fresh machine, in seeded order, so a partial run is an unbiased sample: `close`, all 600 questions, `reopen`, 30 seeded questions. **Bar, as D2m's: 100% of affected answers change to the re-solved answer, 100% of unaffected are byte-identical, the 30 restored; same tokens as the reference machine on every call.** A miss is reported, not revised. **Budget:** the Mac's 517 s per D2m unit, about 272 s for this shorter unit, × 496 × 1.5 / 8 workers = 25,300 s, so two runs of at most 13,000 s each, gated at a unit's start. Whatever isn't finished stays UNRUN and is reported as a count. The budget isn't raised if the mini is slower. **Predictions:** all pass, 90%. Some stops are start or end stops, so closed-start refusals are expected.

## 2. Treat: blackout
One machine with no reset. Close all 496 stops in seeded order, 30 seeded questions after every 31st close, then reopen all in reverse with the same checks, then all 600 questions. **Bar: every line equal to reflib's and the oracle's; the final 600 equal the opening 600.** **Predictions:** passes, 80%; the risk is state that only breaks under many closures, as the most tried so far is 12. Budget 3,000 s.

## 3. Treat: the longest trips in New York
All-pairs hop counts on the Mac, then the 50 longest ordered pairs on the machine with `path`. The longest trip in the graph, by this graph's edges. **Bar: line equal to reflib's and to BFS.** **Predictions:** longest 70-110 hops; costs 100,000-250,000 chip tokens at most; no failure below `MAX_CALL`. Budget 1,800 s.

## 4. Treat: New York fuzz by name
5,000 `chase` calls by seed, by station name not handle: 2,000 one leg, 2,000 two legs, 500 three legs, and 500 awkward: an unknown line, a misspelt name, a station on no such line, zero or large stop counts. Those past the capture window are dropped and counted. **Bar: same tokens as the reference machine on every call.** Reflib's line beside it; a difference from reflib is counted against the 80 known fuzz classes and any new one is reported. **Predictions:** 0 machine-reference differences; reflib differences under 1%, all in known classes. Budget 3,600 s.

## Also
Clean-room check, done before this was written: the bundle copied to `<mini>` and `check/walk.py` run with the mini's system Python 3.9: 24,600 answers and 500 routes on both builds, 0 differ (`exam/results/mini/cleanroom_walk.txt`). The mini's base rows are compared with the Mac's digests: same firmware and tables should give the same tokens on another machine.

Deployment notes, 3 Nov, once started and before any score: `<mini>`, 8 workers, memguard 3 GiB each. The mini's copy of `tok/cexec.py` and `exec/cexec.py` uses the system compiler, `/usr/bin/clang`, and its engine is built there, as the Mac's build uses instructions the M4 lacks. So the base rows' digests also test a different compiler. The items were built after registration, and they put the longest trip at 49 hops, so the 70-110 prediction above missed before any machine call.
