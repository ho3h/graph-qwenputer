# Round 14 steel-man

Recomputed from saved rows and reflib. Partial r6a means 109 finished Mac units.

## 1. Strongest case

- r6c: 9,622 of 9,622 calls equal the reference machine and reflib (2,292 routes, 573 of 1,000 sets). No route contains a closed handle. All 573 reopened routes equal a fresh graph.
- Journeys: 30 of 30 machine answers right; Qwen closed and re-asked on 15 of 15. Replies list the stops on 29 of 29 route turns merging same-name neighbours, 20 strictly.
- Closing now costs almost nothing: same route closed against reopened, median ratio 0.997. Worst closed route 81,438 tokens, against `path_cursor`'s 345,039.

Limit: no r6 row saves Step 13's matching fingerprints; that match is T's, on the earlier rule.

## 2. Best unused result

Shared names set the price, more than route length. Times Sq, Grand Central and Atlantic Av start 3 journeys. Their 6 routes cost 151,169 to 226,375 tokens; the other 24 at most 84,919. Grand Central to Flushing, 10 steps: 151,169. Far Rockaway to Wakefield, 49 steps: 83,763.

`f_path` sends multi-node names to `path_multi`, which walks `rit_next`; the fast path and r6's patch touch only `path_tight`. r6c's `uniq` filter excludes shared names, so "under 100,000" covers unique names only. At 58 tokens a second, a Times Sq route takes about an hour.

- r6c's 1,719 closed-phase routes: 215 `NOPATH` with nothing closed, 42 closed endpoints. Of the other 1,462: 1,222 unchanged, 137 longer (mean +3.5, max +18), 16 rerouted at equal length, 87 `NOPATH`.
- Qwen's one `NOPATH` reply adds "because Bay Ridge Av is closed". The machine gives no reason, and 215 of r6c's 302 `NOPATH`s have no such cause.

## 3. The rule

Right for this post: deletion is the standard semantics, it serves a rider with a destination, and `splice` keeps the old rule per map.

Lost: "station shut, trains still run". Under the wall, 153 of 496 closures strand someone; 149 St-Hostos strands 9.6% of reachable node pairs.

"Nothing can pass a closed stop":

- Transfers: true. All 35 transfer groups are cliques, so a closure blocks only that platform.
- Express trains: false. With 74 St-Broadway closed, `7 northbound 1` from 61 St-Woodside stops early while `7X northbound 1` reaches Junction Blvd. `nyc-b:13`'s new route rides that edge. At least 112 stops have a direct edge over them.
- Shared names: 171 of 1,375 routes print a closed stop's name through another node. 58 names (151 nodes) return `AMBIGUOUS` to `close`. No journey or r6c row closes by shared name.

Wording: "A train that stops at a closed stop is cut off there. An express that skips it still runs."

## 4. The post's shape

Mostly fair: the ordinary-tool tie stays in the story. The gap: Step 15 gives Qwen's closing as 15 of 15 while the same act's failure sits in a Question. Smallest addition, after "asked again in all 15 conversations": "On trick sentences, Qwen also closed stops it shouldn't have, 14 times out of 30."

## 5. Next

Keep new load off the Mac until r6e returns: it has one attempt left.

Record now: r6a looks headed for a miss. On 109 units, 541 answers changed against the old rule's 493, which scales to about 2,400 against the predicted 2,100 to 2,300 (units aren't random). 111 of 541 are `CLOSED` lines, so "nearly all" stop-early is weak too.

1. r6b, registered, no saved rows, mini. 3,000 s. 0 differences.
2. r6c without `uniq`, closures by name, 120 sets, mini. 4,900 s (4 routes × 190,000 at 27,700 a second × 1.5). 0 differences; shared-name routes 100,000 to 300,000 tokens.
3. Qwen on failure lines, simulator: 10 `AMBIGUOUS`, 10 unrelated `NOPATH`, 10 `NONE`. 6,100 s (135 s × 30 × 1.5). Routes through the unclosed station on 5+; blames the closure on 7+; says closed on 5+.
4. Multi-source `path_tight`, if Theo wants Times Sq on the real model. 2,100 s (480 routes × 80,000 × 1.5). Run 2's lines identical, each under 100,000.
5. Sealed rerouted map, machine only, 100 closures, Theo's call. 3,900 s (2.3 units a minute × 1.5). 0 differences; the only row that can retire "no blind test".
