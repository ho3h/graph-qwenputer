# Round 9: README, night before public

Line numbers are `README.md` unless named.

## BLOCKERS

1. **No licence (L209).** Add LICENSE (Theo's choice) and THIRD-PARTY.md. The ELFs link Qwenputer's MIT `crt0.S`, `rt.h`, `rom.ld` (`rvc/box.py:32-37`), so its notice must ship.
2. **L34 is false.** The reference accepted 300 links; firmware says `FULL` from 256 (`limits_edits.json`). SPEC L123 lists 80 more differences. Replace the last sentence: "The reference has no memory limits, so it accepts graphs and links the machine would refuse. Other known differences are in `SPEC.md`."
3. **Cited rows are missing (L118).** Add to `bundle.sh`: `mini/score.json`, `mini/limits_edits.json`, `mini/r2_fuzz/`, `mini/r2_more_score.json`, `after/w/` (the 97), `after/shared*` (the 38), `after/control_map.json`, `t8/fw/results/writes_fuzzfw.json`.
4. **Format sample broken (L50-57).** Its edge names node 1 with one node listed: `neighbours Ana reports_to in` gives a traceback. Edges using relation names answer `NOPATH` silently. Add a Ben node and write: "Each edge is `[from, relation, to, weight]`, where from, relation and to are positions in their lists."
5. **Labels (L139-140).** L118 defines real weights as 18.8 GB; these rows used stock Qwen, 9.3 GB (`exam/alone.py:26`, `exam/mapped.py:45`). Label them "Stock Qwen".
6. **Worked examples never mentioned** (PATH L36, L38; the post discloses them). Add after the table: "Qwen's machine rows had worked examples in the prompt, and the 300 questions copy one template. Without examples, Qwen wrote no close in 23 conversations. The closure rows use uniquely named stations."
7. **L7 opens HTML source on GitHub.** Use the post's public URL.
8. **L197 and L201 are false.** `web/build.py:259` and `reviews/round4-steelman.md:12` keep a scratchpad path with the username. Extend `sanitize.py`; write "unedited apart from local paths".
9. **MTA marks undecided.** The post draws route bullets in MTA colours; `round7-design.md:75` says check before launch. Theo decides.

## Other fixes, ranked

1. **L152 hides a timeout** (`AFTER.md:104`). Write "15 / 15; 14 / 14 reaching the closure, as one ran out of time".
2. **"Yet" (L9, L183) implies a release.** State the plan, or write "I haven't decided whether to release the model."
3. **L100-102.** Add: "Upstream also has file tools that Qwen calls in the same layers" (vendor README L32-36). Write Qwen3.5-4B. Say the C simulator isn't here.
4. **L193.** `fw/graphlib.c`, `tok/gen_fw.py`, `tools/rt_mini.c` and frozen source are absent, so builds can't be regenerated. Add them or say so.
5. **`try.py`.** `Usage: frobnicate takes . Calls:` is malformed; `BADARG path` omits the argument; bad files give tracebacks; errors exit 0; bare runs wait silently; nothing lists relations; 3,000 nodes load unwarned.
6. **`check/walk.py`.** L175 says look for matching pairs, but it prints `'n': 500, 'same': 454` (46 NOPATH rows skip the counter, line 82) and ends on a dangling label.
7. **L158.** 97 of 100 wasn't recomputed (`round6-critical.md:167`). List it as unreviewed.
8. **L154.** Write: "A normal tool outside the model scored the same as the machine on the 100 two-leg questions, before and after the fix."
9. **L106.** Add: "It ran through the layer modules, with a token cap set from the known stream."
10. **L133.** Disclose 250 reserved token ids that differ between simulator and weights; exams reject them (`REGISTRATION.md:16`).
11. **PATH.md.** Remove the private artifact link (L159). Add a note that it is a working log citing absent files.

## Cold read

Thirty seconds gives what it is and what you can't run. New versus Qwenputer waits until L100, so put a sentence in the intro. Happy-path outputs feel like a product; errors don't.

## Couldn't determine

- **MTA:** terms, read through a summarising fetch, bar modifying data and implying a licence. Whether derived graphs count needs a human. No feed date recorded.
- **NYC Open Data, Census:** terms not read.
- **Qwen:** Apache 2.0 per its card. No tokenizer files ship, but ELFs embed tables from `tok_lits.h`; notice undecided.
- **`ho3h/subway-in-the-weights`:** private, unchecked.

## Verified right

- README commands, table examples and my own graph behave as documented.
- 43 of 43 journey calls replay.
- `walk.py` and `check_figures.py` pass (3,234 checks).
- Machine, exam, edit and choice rows: score files, PATH.
- 5,890: `demo/all.jsonl`. 18.76 GB, 32 and 43 layers: checkpoint.
- Build hashes, Qwenputer facts and path-table files check out.
- Secret patterns: none. Sealed data: names and rules only, by name search. Largest file 11 MB.
