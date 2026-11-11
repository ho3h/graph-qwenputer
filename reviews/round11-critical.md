# Round 11 critical: r4 (f769d683) and r5 (06767ab3)

Rows: `exam/results/after/round11/`.

## BLOCKERS

**None in the firmware: I couldn't make r4 or r5 print a different line.** Three conditions on the claims:

1. **r5 can't be cited yet.** It has 14 routes on its registered bars; no `r5_directed` or `r5_all` rows are in the repo. Fix: state in AFTER.md that Z3 and Z2 on r5 don't count until they pass, and keep the post on r4's numbers until then.
2. **r5's bar misses its own new code.** Y never sets `dead_`, so r5's dead checks are never true in its registered tests. Fix: run `attack.py --aimed` on r5 with r2 beside it. r2 reached only 25 rows here.
3. **"Every rerun" is too wide for that coverage.** Copy:
   - README line 128: "On the writes build, adding a stop or a link made every later route expensive. This keeps the fast search at stops no write touched. It printed the same lines on my 400 write sequences and 14 routes, apart from one route the writes build couldn't finish. A route with a stop closed gets none of this. It hasn't had a frozen exam"
   - Post, replacing "On every test I rerun it prints the same lines as the writes build.": "It printed the same lines on the 400 write sequences and 14 routes I reran, apart from one route the writes build couldn't finish."
   - Post: "with real unlinks" becomes "with real unlinks of edges it had added".

## Other findings, ranked

1. **Y's coverage is thin.** 100 `path` calls, none after an unlink, all targeting a new stop. 2,145 unlinks, 0 of loaded edges. The exam sample's 25,880 calls have no `link` or `add_node`.
2. **AFTER.md wording.** "every line equal to r2's, including the 14-stop chain" is wrong: r2's executor row is `status max`. r4 equals r2's reference row.
3. **"No wrong answer" at the cap needs a limit.** After `status max`, the next call returned `ok` with the earlier route (`r5_capclosed`, `cap49closed` j=243: asked @298 to @325, printed 15 steps, reflib 4). It takes 240 links and a closure, beyond the 12-call limit. Fix: `max` ends the sequence.
4. **Closures get no fix.** r5's 14-stop chain: 60,492; with an unrelated stop closed, 817,464.
5. **The post is stale if r5 stands.** "fourth build"; 54,372 and 239,669 become 57,738 and 53,680.

## Tested and right

- r5: 4,088 rows, 1,130 routes, 0 reflib differences except 2 rows from finding 3. Reference engine equal on all 1,999 rows where it ran.
- r4: 2,077 rows, 0 differences except 2 `status max` near the full table; r5 clears both.
- r4 equals r5 on 1,492 shared aimed and fuzz rows; both equal r2 on the 117 r2 reached.
- Routes with a dead loaded edge: 327. `link` reviving one.
- Swap-remove orders; lower-handle predecessors added at the target; self-loops 109; start equal to target; new stop as target and start.
- `close`, writes, `reopen`, then the tight path: 160 aimed routes. Stations with transfers cut and restored.
- By reading: `touched_` only grows and covers both directions; `n_closed` balances; `cur_next` and `rit_init` are equivalent for untouched stops, so other callers are unaffected.

## Claims

**"About 11 minutes" holds for r4:** 648, 636, 637 s; the log gives 1,937 s for 3. It's 2-stop routes in lockstep, so it doesn't carry to longer lines or r5.

**Predictions preceded the runs.** r4: commit 08:08:00, build 08:08:01, rows 08:10:39, real weights 08:11:19. r5: commit 08:48:33, ELF 08:48:37. Z1, Z2 08:44:58; Z3 08:51:34, started 08:53.
