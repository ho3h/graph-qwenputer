# Round 16 critical review

## Blockers

**1. Band: "On the current build, all 995,198 machine exam calls matched a reference machine".** The sum holds (321,674 × 3 + 11,696 + 16,442 + 2,038), every row `same`. But none ran on the real model (`exam/mach.py`), the band omits that, and the FAQ promises "I say which". The reference runs the same firmware, and `check/walk.py` prints only two old builds. The page never says what this misses: README's Fixed rows show the replaced closure rule passing too. 94.6% of calls re-ask 600 questions per map. Fix: "On a simulator… a reference machine running the same firmware. That catches a faulty machine, not a wrong rule or map."

**2. README: "These are the ones that missed."** Left out: F1's install (`AFTER.md:347` says "missed"); U6's `FULL` at 256, void on 300 `BADARG` rows (`:383`), with README's U6 row silent; S2's replies, 98.6% against 60–95%, under "All predictions held" (`:371`). "Two runs" stopped on limits omits r6c (`:343`). Fix: add them.

**3. README: "It has since had a blind test on the two maps I kept sealed."** S1's 600 questions all use handles (`items/sealed/nyc-relabelled.json`), so S1 skips the fix. `nyc-cf`'s S2 is unfinished. `nyc-relabelled` is New York exactly: all 1,761 edges and the same-name groups match, so `AFTER.md:371`'s "a map it hadn't seen" is false. S2's 100 shared starts are filtered so a leg settles them (`d1m.py` `generate_shared`). Fix: say so; the file's 47 shared starts, all right, are the evidence.

## Should fix

4. **Thread 5: "296 of 300, with 0 wrong."** Omits the page's template caveat. On 2 of 4 refusals Qwen gave its misspelled start as the answer (`s2` rows 171, 900075). Fix: add both, on the page too.

5. **Thread 1, 3, 4** show no Qwen failure. Post 4 is one chosen conversation; E6: reopens 35/40, false closes 13/30. "It built the line" omits the empty T slot, worked examples and 0 of 10 planning. Fix: "I chose this one", plus those counts.

6. **Band: "all 15 new answers were right"**, beside the registered E6 on the same build: 33/40 lines, 7 `AMBIGUOUS`, Qwen named a station anyway on 6 (`e6/all.jsonl`). Fix: add to Questions.

7. **HN: "got 24 of 30 right".** `t2/RULES.md`: "I score calls, not replies." C2 turn 3 replied raw tool-call text. The page's "wrote the right calls" is fair and the CSV import is real (`t2/checks.txt`), but neither says agent, same-kind examples or 23 answered, the audit's fixes. Fix: copy them over.

8. **"predictions written before each run".** `publish.sh` deletes history. Privately the order holds (3499072fc2, then 8e33aaae93; manifest unchanged since 1 Nov), but the bundle lacks manifest, sealed questions and builder, so `sealed_open.py` breaks. Fix: publish those and the commit log.

9. **Thread 7: "saved results… public".** Rows for 967,060 of the 995,198 aren't bundled; three exams total 48 MB. Fix: add them.

10. **Unrun tests.** Nothing implies S3, S4, S5 or E6w ran, but README never marks them, against `AFTER.md:377`. "Running" will go stale. Fix: a "registered, not run" row.

11. **Round 15 fixes that didn't hold.** LinkedIn's "I added graph firmware" has no Claude Code; `TOOLKIT.md:13` "in Qwen's layers"; "Large language models get lost" (Theo's call).

## Minor

- README's "Reviewed:" stops at round 10.
- `publish.sh` commits under Theo's Gmail.

## Holds

No use of the sealed maps before 4 Nov: tools assert against `heldout`. Clean copy: first three commands right on Python 3.15 and 3.9, toolkit 69/69, figures 3,291/0, no secrets. Live page equals local. HN quote real (comment 50283402).

READY AFTER FIXES
