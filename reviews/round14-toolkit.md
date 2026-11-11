# Round 14: the toolkit, as a stranger

About 75 firmware calls, in a copy. `ask` and `run.py` were read, not run.

**After 2 minutes:** a RISC-V computer in Qwen's weights that answers exact graph queries as tool calls, far slower than a normal tool. First: `gq.py import`, `check`, `try`. Clear. README:29-35 isn't: it pastes straight into the 18.8 GB download, and Python 3.12 and LLVM come later. The `hf download` commands read clearly; not run.

## Blockers

1. **`try` and `sim` disagree.** `gq.py try nyc chase "14 St" "FX southbound 1"` prints `AMBIGUOUS 3: @25 14 St | @26 14 St | @27 14 St`. `gq.py sim nyc --model M chase "14 St" "FX southbound 1"` prints `@478 W 4 St-Wash Sq` and "agree". Both exit 0. `try.py:15` sets T8_R2, not T8_R1. Fix: set it, add a test. With it set, `try` matched.

2. **`TOOLONG` is undocumented.** `sim` refuses calls past 80 tokens: `path` and `link` between UUID names, `find` on a 64-digit name, `chase` with 12 `depends_on 1` legs. `try` answers them all. These graphs pass `check --firmware`; docs promise 64-byte names and 16 legs. Fix: a row in TOOLKIT.md's limits, a token check in `check --firmware`.

3. **`gq.py build` needs the author's disk.** `tok/gen_fw.py:17` reads `~/Models/x210/Qwen3.5-4B/tokenizer.json`. Clean `HOME`: traceback, "t8/fw/gen.py failed." Fix: read `TOK_CKPT`, add `build --model`. The model's tokenizer there gave the documented hash.

4. **`ask` should crash for strangers, after loading the model.** `t8/fw/edit.py:309` opens `X.MODEL`, which `tok/common.py:60` sets to that folder. That call under a clean `HOME`: `OSError: Repo id must be…`. The planned test here won't catch it unless `HOME` is clean. Fix: `nq = ec.chat.v0`, not `--model`, whose tokenizer has 484,789 entries; check it equals the old `nq`. Otherwise I believe the path works.

5. **`import` silently damages data, exit 0** (`gq.py:100-126`):
   - `From,Relation,To` becomes a real edge. Match the header ignoring case.
   - `,knows,B` and `#1 Dad,parent_of,Kim` vanish. Error on the first; report skipped rows.
   - The same edge with weights 5 and 7 keeps 7. Error, as `check` does.
   - Two John Smiths become one node, though docs say "Names can repeat". Say so.
   - A typo in `--both` or `--inverse` does nothing. Error if the relation isn't in the file.
   - `;` or tab files become all nodes, 0 edges. Warn at 0 edges.

## Problems

6. **Tracebacks.** Missing or non-UTF-8 CSV, bad `-o`, `--inverse nope` (`gq.py:100,110,136`). `check` on `"nodes": 5` or a list relation (`:45,52`). No `format` passes `check`, then `try` gives `KeyError: 'format'` and `check --firmware` says "does not fit the firmware: 'format'". No torch: `ModuleNotFoundError`. Fix: catch these, extend `problems()`, test imports in `firmware()`.

7. **Requirements understated.** On Python 3.9 the documented `sim` form gives `unrecognized arguments`. Clang is fixed at `/opt/homebrew` (`tok/cexec.py:26`), so no Intel or Linux, yet TOOLKIT limits only `ask` to Apple silicon. `build` also needs `brew install lld` (`rvc/box.py:34`); Homebrew's llvm here has no `ld.lld`. Fix: TOOLKIT.md:12, honour `$CC`.

8. **`--examples`, `--tools`.** I ran `ask_run.py` up to the model load. My course examples parse. Silently accepted: `fn: "neighbors"`, arg `rel`, a tool in the examples not offered. Wrong field or missing file: raw traceback (`:40`). Unknown tool: plain message, but `path, close` fails unstripped (`:20`). `run.py:48-53` never prints `status`, so the call cap silently drops later turns. Fix: validate against `base`, print it.

9. **Firmware guide.** Neighbours edit in C and `reflib`, build, sim: worked; undo restored `3d66be3572228cec`. Honest about new calls. Unsaid: `gen.py` replaces `f_path`, `f_close`, `f_find`, `f_add_node`, `f_unlink`. Changing `NOPATH` in the C base left a shared-name route printing `NOPATH`; `sim` caught it. One added space inside `f_path` gives an assert dump. The hash assumes an unstated clang (mine 23.1.4), and `build` overwrites the frozen ELF. Fix: say so; replace the assert with a sentence.

10. **`sim` drops extra arguments.** `path c0 c1 c9` routes c0 to c1 and says "agree"; `try` refuses. `sim_run.py:40`.

11. **Modularity.** README's table omits `cop/ ctrl/ exec/ host/ rvc/ speed/ tools/ vendor/`. `sim` needs `exam/mach.py`, `exam/items/nyc.json` and `exec/covdiff.py`, which `t8/fw/cov.py` reads as source. I lifted 4.8 MB of 153 MB and `sim` ran; `build` needs more. Fix: publish the list. Still New York or trains: `sim_run.py:25` feeds New York's prompt for every graph; `host/tools.py:42` "A northbound 3"; `:105` "Changing between lines"; firmware prints "The journey did not finish." on prerequisites; `--domain transit` switches on an undocumented "station" cleaner.

12. **Default weights.** `import` uses 1, `link` 0, neither in TOOLKIT. A bare `link` gave `cost 0`.

13. **`python3 web/check_figures.py` tracebacks.** Line 9 opens `release/README.md`; past that, it needs absent `exam/results/after/r6_walk_draw.json`.

14. **Tests.** 26 checks, 29 with `--model`, all pass. Good on refusals and firmware equality. None covers messy CSVs, shared-name `chase`, `TOOLONG`, `build` or examples, so they miss every blocker.

## Small

- TOOLKIT.md:83 says 5,207 tokens; I got 4,964.
- `gq.py:6-7`: `path app zlib` prints `NONE zlib`.
- `find | A|B` on stdin prints `NORELATION B`.
- No `.gitignore`, with `model/` in the root.

## Licence

MIT and credit are clear. Unstated: terms for the merged weights, and the MTA's terms.

## Worked well

BOM, CRLF, quoted commas, a trailing comma, apostrophes, number-like names, self-loops, `line 2` in `chase`, 1,025 nodes and 65 relations all behaved. `try` matched `sim` on every other well-formed call, including writes, splice closures and overflow.

**Verdict:** yes for short-named graphs on `sim` with a cleaned CSV; not for firmware or `ask` until blockers 3 and 4 are fixed.
