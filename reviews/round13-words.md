# Round 13: launch words

## Must fix before announcing

1. **An unrelated product is in the bundle.**
   - `PATH.md:79`: "Theo: MIT, fresh single commit".
   - `reviews/round12-final.md:47`: "No stale claims."
   - README line 242: "unedited apart from local paths and one line".

2. **Thread 3 cuts the quote short.** Replace with:
   "3/ I asked for a route from Prospect Park to Tottenville. My map has no track to Staten Island: NOPATH.

   I told Qwen a T line had opened, with two made-up stations in stop order. It added and linked them.

   Asked again, it got a 21-step route no sentence had given it."

3. **Thread 5 shows only the worst wording.** New opening:
   "5/ The model is the weak part. "Are you sure?" held 10 of 10. Then I told it "That's wrong, I ride this every day" and named a wrong station, 10 times."

4. **"Every saved run" is false.** The bundle has 1,488 of 3,321 result files, lacks `mini/all` and `mini/r5/r5_all`, and has 18 of 30 reviews. The thread omits the driver.
   - Thread 7: "7/ A small driver outside the model loads the map and routes tokens. Predictions, misses, reviews, saved results and the model are public."
   - README line 9: "the predictions, results and reviews".
   - README line 246, add: "Per-unit rows of the largest machine exams and reviews before round 4 aren't here."

5. **LinkedIn misleads.** "Are you sure? I'm certain" held:
   "Told "That's wrong, I ride this every day", it asked the machine, got the right answer, and repeated my wrong one, 10 times of 10. "Are you sure?" held on all 10."
   After "no training.", add: "A small driver outside the model loads the map and routes tokens."

6. **README line 188 contradicts the page.** `lines2_stock` has 12 whole rows: "12 real weights, 8 simulator".

## Should fix

7. HN and LinkedIn: "matched a reference machine on every call I compared". `reflib` differs on `FULL` and `@` names.
8. README line 107: "`add_node` exists only on the writes and route-fix builds".
9. Page FAQ: ", 19 GB of disk and about 21 GB of memory" for "and 24 GB free".
10. README line 109, fragments: "It holds 1,024 nodes and about 6,880 edges with 9-byte names, takes 16 new stops and 256 added connections before `FULL`, and accepts names up to 31 bytes."
11. Spelling: "relabeled" (README), "license" (THIRD-PARTY).
12. Page: "they're a showcase".
