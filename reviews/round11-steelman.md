# Round 11 steel-man

## What r4 adds
A route after an added stop costs what it did before: 14 stops, 1,331,861 tokens down to 54,372, against 54,328 unwritten. On the real weights, `path` crossed Qwen's own stops 3 of 3, 0 of 109,719 positions differing.

## Correct first
- **"First time" is false.** `journeys/all.jsonl` nyc-j:1 closed 6 Av, then routed, on the real weights (r2, 141,955 tokens). True: the first `path` across stops Qwen added.
- **Closures aren't fixed.** `graphlib.c` line 1000 sends them to `path_cursor`; 0 of r4's 100 aimed routes had a stop closed. The post's "one write" and the README's "any write" should say "an added stop or link".
- **The reply proves little.** My sentence lists those stops in order. The printed line is the evidence.

## T line scene: yes
Show `nyc-r3:0` alone; Foxglove is another build. Cortelyou Rd to Old Town is NOPATH before the line (reflib), so the arc reaches Staten Island. The route stops at Bracken Rd.

**Map:** nodes 269 and 415 replace 444 and 361. Draw three links; brighten the first two last.

**Final deck:** `path Cortelyou Rd to Bracken Rd` / `> 2 steps: @269 Cortelyou Rd > @496 Gannet Sq > @497 Bracken Rd` / `Qwen: Cortelyou Rd, Gannet Sq, Bracken Rd`. Big: "6", "calls by Qwen, on the real weights".

**Copy, after the 20-conversation paragraph:**

> On the route-fix build, I told Qwen the T line had two new stations, Gannet Sq and Bracken Rd. It added them and wrote the links. I asked for the shortest route from Cortelyou Rd to Bracken Rd, and the machine printed it from what Qwen had written. All 3 such conversations were right on the real weights, about 11 minutes each. The prompt had a worked example and my sentence gave the order, so the printed line is what counts. This build hasn't had a frozen exam.

## Main build?
Main claims stay on the frozen and fixed builds; move r4, labelled, into this scene. Z1 won't make it frozen.

## "The bug was mine"
Worth one sentence. Readers learn the 13-to-36 times cost can't count against compiled layers:

> That cost was my firmware. Changing the firmware removed it, with the layers untouched, and two of my cost predictions still missed.

## Smaller fix
Not before publishing. r4 was the one revision, so it's Theo's call, and a fifth build restarts Z1 and Z2. Design: scan once for a stop's relations; try only those. Prediction, five-row fit: 12-stop chain under 70,000, against 239,669; lines equal.

## Better next run
One conversation: Prospect Park to Tottenville, NOPATH, T opens, same question, 21 steps (reflib). No sentence contains that route.
