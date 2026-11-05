# X2.10 cop/ development log (Phase A reference; development, no gate)

Status: A1 dev clean against reflib 2a406e3e (graphlib.c 461abe99). The dev cost evidence does not support either A4
prediction. No gate was run. Inputs were checked unchanged after the run: reflib, COPROCESSOR.md, graphlib.c, data/dev.

## Files
- `cop_ref.py`: the coprocessor on Python state, and `CopMachine` (vendored `ref.Machine` plus custom-2).
- `boot.py`: `x210-graph/1` to coprocessor state and DROM blob; holds the Python side of the hash.
- `graphlib.c`: the C library; `-DNO_GRAPH_OPS` gives the software baseline.
- `run_call.py`: builds, boots, runs calls. `test_a1_dev.py`, `cost_dev.py`: the tests. `results/`: saved outputs.

## Run rules (from the lead, after the 13:10 ET panic)
All runs go through `tools/memguard.py --limit-gib 12`. Every reflib or machine call has a 60 s alarm, and a hit counts
as a mismatch. The test log is flushed per job. The panic came from the old reflib's `cheapest` looping on zero
weights (reproduced by the lead), not from this code.

## Decisions
- **Token format.** `GOP` family, 16 ids from `spec.VOCAB`, appended the way spec.py appends the store families. A graph
  op's record is `GOP(op)` then rd's value record (`NT` when rd = x0). Op ids are the order of `cop_ref.OPS`.
- **Encoding.** Opcode 0x5B; (f7, f3): GADD 0,0; GDEL 0,1; GFIRST 0,2; GNEXT 0,3; GEDGE 0,4; GNODE 0,5; GSETN 0,6;
  GLBYTE 0,7; GLFIRST 1,0; GLNEXT 1,1; SOP 1,2; EXPAND 1,3. SOP sub-ops 0..8 in the COPROCESSOR.md order.
- **Program shape.** Parked firmware like the qwenputer calc bridge: init, then exit ecall; each GO reads one call and
  parks. RAM and coprocessor state persist, so close / link sequences work as in the circuit. Tokens count GO to HALT.
- **Call buffer.** Flat bytes at the text buffer (0x8000, 2,048 bytes): `fn NUL (key NUL value NUL)* NUL`. The result
  text is printed without the §6 wrapper.
- **Boot blob.** At DROM 0x21000 (program rodata stays under 4 KB). Graph data is read at run time, never compiled in.
- **Hash.** FNV-1a-32 over UTF-8, folded to 12 bits, in `boot.ghash` and `graphlib.c ghash`. The check that they agree is
  that find resolves labels through their buckets (all labels up to 200 per graph, else a sample of 64, plus forced
  collisions).
- **Effective edges have no result buffer.** A list without a closed splice target is walked directly. Otherwise
  `eff_slow` runs Dijkstra over the closed nodes and leaves targets in a bitmap. So degree has no library limit.
- **Queues cannot lose an answer.** A key that does not fit is dropped and remembered; when a dropped key could be next,
  the smallest live keys are rebuilt from bitmaps and `best_get`. Capacity costs time on extreme graphs, not exactness.
- **Saturating costs.** Costs and eff weights saturate at 65,536. Anything above 65,535 is `OVERFLOW`, and such nodes
  cannot lie on a cheaper path, so answers are exact. Costs use the scratch column plus an overflow bitmap.
- **path by EXPAND.** S0/S2 frontier, S1 visited (closed nodes included from the start), S3 the persistent closed set.
  With four sets the levels cannot be kept, so each rebuild step recomputes L(k−1): O(D²) records. On `DEGREE`, or with a
  node closed and a splice relation present, path restarts as the cursor search.
- **Software baseline.** Per-node arrays in DROM, tagged by relation and sorted; a RAM overlay (256 added edges,
  tombstones) answers link / unlink. Image limit: N ≤ 1,024 and the 128 KB DROM.
- **`path_tight`.** The software build's BFS in the common state is plain loops over each node's whole list. See the
  A4 section for why this matters.

## A1 dev results (`results/a1_dev.json`, 835 s, 4 workers, memguard peak 0.24 GiB, no alarm hit)
A check is one build answering one call, except in nx, where it is one reflib answer against networkx. Builds:
graph ops, graph ops with EXPAND unindexed (cursor search), software.

| Part | Jobs | Checks | Match | Mismatches |
|---|---:|---:|---:|---:|
| dev (all data/dev questions, setups, labels) | 128 | 87,836 | 87,836 | 0 |
| random (own graphs, one persistent state per graph) | 300 | 72,000 | 72,000 | 0 |
| medium (150–1,024 nodes, closures and edits) | 16 | 1,536 | 1,536 | 0 |
| limits | 1 | 289 | 289 | 0 |
| zero-weight tie cases | 1 | 171 | 171 | 0 |
| nx: reflib against networkx (open, closed, edited) | 229 | 1,479,824 | 1,479,824 | 0 |

- Builder answers in data/dev equal reflib's: 0 differences.
- r097 (928 nodes, 12,503 edges) needs a 181,620-byte DROM image, so it has no software run. Both graph-op routes match.
- **Limits covered:** `DEGREE` directly and through path's fallback; N = 1,500 and N = 4,096; refusals at N = 4,097, E =
  16,385, a 65-byte label and a non-NFC label; `FULL` directly and through link; `OVERFLOW`; 16 / 17 legs; 255 / 256
  steps; hash collisions; hubs of out-degree 1,000 and 3,000, including through a closed hub; every `@h label` outcome.
- `COLLIDE` and `PROBE` belong to E's tables and are not built here.
- The test does detect faults: run against a changed reflib, an older version of this code gave the lead 3,093
  mismatches of 72,000 in the random part. Nothing has been mutation-tested beyond that.

## A4 dev cost (`results/cost_dev.json`; 84 dev graphs of 64–1,024 nodes)
Ratio = graph-op tokens / software tokens, same core. These are not the gate: dev cities have 115–270 nodes and D ≤ 14,
while A4 is on NYC scale.

| Call | Calls | Ratio of totals | Median | Within prediction | Mean tokens (ops / software) |
|---|---:|---:|---:|---:|---:|
| path (predicted ≤ 0.10) | 1,008 | 0.200 | 0.295 | 108 | 2,343 / 11,718 |
| path, dev cities, reached pairs | 336 | 0.302 | | 0 | |
| chase (predicted ≤ 0.20) | 665 | 0.853 | 0.852 | 0 | 3,118 / 3,654 |
| find (for scale) | 252 | | | | 1,416 / 1,664 |

- **Path by N (ratio of totals):** 64–127 0.30, 128–255 0.30, 256–511 0.16, 512–1,024 0.087. Search alone, without the
  printing: 0.138 overall, 0.209 on cities.
- **The baseline decides this result.** With the software build's BFS going through the shared buffered `eff` code, the
  ratio was 0.040 (`results/cost_dev_sw_eff_baseline.json`, an earlier library version). That baseline was about five
  times too slow for a plain C BFS, so `path_tight` replaced it, and the ratio went to about 0.19–0.20. A4 should be
  measured against the tight one.
- **Chase is not tight on the software side.** A follow step costs 22.5 tokens with ops and 95.6 in software
  (`results/follow_micro.json`), 0.236 per step, on top of about 1,300 fixed tokens in both builds (parse, resolve,
  print). A tighter software loop would push the ratio nearer 1, so the 1/5 prediction fails either way.
- **Path against D, 22 × 22 grid (484 nodes, 1,848 edges):**

| D | Ops | Software | Ratio | Estimate without the D² term |
|---:|---:|---:|---:|---:|
| 2 | 1,341 | 1,681 | 0.80 | 0.78 |
| 5 | 1,947 | 3,089 | 0.63 | 0.56 |
| 10 | 3,565 | 8,621 | 0.41 | 0.31 |
| 20 | 8,007 | 27,344 | 0.29 | 0.16 |
| 30 | 14,409 | 50,076 | 0.29 | 0.13 |
| 42 | 24,429 | 62,761 | 0.39 | 0.14 |

  The fit is ops search tokens = 8.92 D² + 65.8 D + 890. The last column removes the D² term and is an estimate, not a
  measurement. It suggests a set file helps a lot at long D but does not by itself reach 1/10 on this graph: parsing and
  printing are shared costs.
- The cursor search with graph ops costs 1.61 × the software BFS, because it probes every relation per node.

## History of reflib changes handled
Self-loops; 16 legs; `cheapest` finalisation rule and zero weights; `reopen` by label; `link` / `unlink`; minimal weights
through closed nodes; `@h label` node arguments (SPEC §4, also in `reopen`).

Defects found in the first reflib by this test, since fixed by the lead:
1. `eff` weights depended on DFS order through adjacent closed nodes (cost 11 where the true minimum was 3).
2. A zero-weight edge into the source raised `TypeError`.
3. A zero-weight cycle made a predecessor cycle, so `cheapest` never returned (the cause of the panic).

## Bugs of mine, fixed
- `CLRB(seen, seen_list[--ns])` evaluated `--ns` twice (a clang warning caught it).
- `hub1399`: `\nLIMIT eff results` where reflib answers `MULTI 1399`. Fixed by removing the result buffer.
- First queue spill rule could rescan for every pop on adversarial weights (10 CPU-minutes in the limits job). The rebuild
  now keeps the smallest keys.
- Dev crash on r097: the graph does not fit the software image, and the harness let the boot refusal kill the whole
  file. The harness now records the refusal and runs both graph-op routes on that file.

## Known divergences (not exercised by the tests; decisions needed)
- **NFC.** The C library does not normalise. `run_call` refuses non-NFC arguments and `boot` refuses non-NFC labels.
- **Non-ASCII digits.** reflib's `\d` and `int()` accept them (`@٣`); the C library takes ASCII digits only.
- **`FULL`.** C answers `FULL` when GADD runs out of rows (16,384; tested through link) and at the software overlay's 256
  added edges. reflib has no such bound, though SPEC §3 says the reference raises each limit.
- **Label length.** `boot` refuses labels over 64 bytes (COPROCESSOR.md's table); DESIGN.md says 16 tokens.

## Proposed changes
COPROCESSOR.md:
1. **A set file, not four sets.** DESIGN.md's path "keeps each level's set"; v0 cannot, and the rebuild is the D² term.
   Suggested: enough sets for the longest level count wanted, with wider `s` and `t` fields.
2. **`SOP del`.** Removing one member takes three ops (clear, add, diff); reopen uses it.
3. **EXPAND's rel field is an index slot** (0..3), each slot a boot-declared set of relations, since NYC indexes the union
   of all moves. Rows count multiplicity.
4. **Drop GADD's dir-flags.** The reference reserves them (must be 0); nothing uses them.
5. **State the `DEGREE` rule.** The reference: a read's sum at any node above 256 answers −3 and leaves S_t unchanged. A3
   should pin the bound.
6. **Iterate a node's relations.** Cursor search pays one GFIRST per relation per node. A GRFIRST / GRNEXT pair would help.
7. **Reserve ROM uops** 70..81 for the graph ops when Phase B needs `rom_word`.

SPEC.md:
8. **Decide where NFC lives** (see above).
9. **§5 wording.** "Finalised in (cost, handle) order" holds only among nodes already reached: a zero-weight edge can reveal
   a lower handle after a higher one is finalised. reflib's queue order is the rule; my first nx check took the
   words literally and crashed on this.
10. **Add `FULL` to reflib's link**, and restrict digits to ASCII.

For Phase B: the bridge captures 80 tokens per call, and 16 legs may not fit. Not measured here.
