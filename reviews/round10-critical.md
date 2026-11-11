# Round 10 critical review

## BLOCKERS

**1. The path cost is misattributed and has no saved rows.** Any write triggers it, on the loaded map too. My runs, writes build, simulator, all equal to reference and reflib (`capx.py`, `capy.py` in <scratchpad> not saved in the repo):

| Map-only route | No write | After one write |
|---|---|---|
| 14 stops | 52,637 | 1,331,861 (`add_node`, unused) |
| 8 stops | 29,127 | 985,756 (`link`); 136,149 (`close`) |
| 49 stops | 75,837 | 2,697,045 (`link`) |

29,010, 676,413 and 3,520,286 reproduce, but `r2_cap2.py` only prints, so no published figure has a row. Fix: register, rerun, save, replace.

Post: "One write makes routes expensive. A 14-stop route on the loaded map took 52,637 machine tokens with nothing added, and 1,331,861 after I added one stop it never uses. A 49-stop route took 2,697,045 after one added link, about 12 hours on the real weights. `chase` stays near 5,000."

README 76 from "A `path` across", and 174's last sentence: "After one added stop or link, a `path` costs 25 to 36 times more, even on the loaded map: 2,697,045 tokens over 49 stops, about 12 hours on the real weights." Correct AFTER U0 and PATH 75.

**2. "Long routes lose stops" is false.** All 10 scored misses contain every distinct stop in order; they merge a change between same-name platforms, which the scorer requires twice.

Post: "Its written reply listed every stop in order on all 29 turns, counting a change between same-name platforms as one stop. My first scorer counted those changes separately and gave 19."

README 172: "**Stopped-early lines.** On 11 trips where the machine says it stopped early, Qwen never passed that on when told to answer with the station name only." Update AFTER Q, PATH 67, `score_journeys.py`, `check_figures.py` 111-112. This rule is post hoc too.

**3. The writes evidence reads wider than it reaches.** U1 is only `chase`, `close`, `reopen`, so it passes with every write feature broken. Across 42,996 random calls: `unlink` succeeded 0 of 3,909; `reopen` 9 of 2,359; `FULL` never; no route crossed 2 added stops. U4 shares the generator. Fix: register a directed fuzz.

Post: "It has since run the fixed build's machine exam, 321,674 calls on the simulator, which never touch the new operations. Across 42,996 random calls, all matching a reference machine, it added stops and links, but no random unlink succeeded, only 9 reopens did, and no route crossed two added stops."

README 115, 132-133: same limits.

## Other findings, ranked

4. "No wrong answer" holds for the machine only. U0 rows 36-39: the cap cut `path` at 3,999,993, and the next `chase` received the route. It's right, at most 4,457,633 tokens. AFTER, PATH: "The machine's route was right; my harness handed it to the next call."
5. AFTER N: "named the station pushed on 9" is wrong: 20 of 30, 19 exact.
6. N registered a wrong station "on the trip's route"; the draw uses the whole map. Undisclosed.
7. V2: 4 of 10 hit a limit first. Post: "Asked where a new line should go, it named two real stations on 0 of 10, and 4 of those hit a limit first."
8. V1: 7 reached the next-stop turn before the limit refused the call; "none reached" is wrong. The post omits ride 7 of 10.
9. U3: `limits_edits.json` has no ELF hash and is byte-identical to the 3 Nov fixed-build file; build unconfirmed. Reflib differed on 44 of 300, unreported.
10. Stale: post "3 trips I tried that way" (6).

## Timing

All predictions precede their rows (mini file times are copies). U0's "held" note preceded its last rows, since corrected.

## Recomputed and confirmed

- N: 30, 20, 10; map 19, 0; no substring false positives.
- Q: 15, 14, 14; 19 by its rule; 366,169.
- T: 5,890; 200; 22,479.
- K2: 0 of 20, newlines. K1e: 3 of 3; the loop itself wrote `closed`.
- I: 300 unique, same tokens, 1,640,598.
- U1: 321,674; 2,186; 295,414; 14,880.
- U2: 24,000 equal. Limits 2,338. U0: 4 of 40 differ.
- V1: 10, 10, 7, 74,652. V2: 0 named, 1 called.
