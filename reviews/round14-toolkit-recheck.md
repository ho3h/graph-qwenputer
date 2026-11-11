# Round 14 recheck

Fresh copy, empty `HOME` (still empty afterwards), memguard at 6 GiB (peak 0.78 GiB), no GPU, about 260 firmware calls. Below, `gq` is `gq.py` under those settings, `G` a graph and `M` the three small files. `ask` ran only to the pre-model checks: `gq ask` stops at `run.py`'s weights check, and I ran `ask_run.py` with `edit.py`'s module body but not `main()`.

My `nq = ec.chat.v0` was wrong, as you say.

## My report, item by item

1. **`try` and `sim`: fixed.** `gq try nyc chase "14 St" "FX southbound 1"` and the `sim` form both print `@478 W 4 St-Wash Sq`. 113 more calls through both (shared names, closures, writes, handles, an unsorted three-field file) were identical. Other disagreements: new item 6.
2. **`TOOLONG`: partly.** `gq sim` at 79, 80 and 81 tokens: 81 is the first refusal, explained, and `check --firmware` predicts it exactly. State is unchanged afterwards. Open: `check` reports only `path`. A 72-token `path` passes while `link` on the same graph is 95 tokens and refused. `host/tools.py:38` and `SPEC.md:52` still say 16 legs; 12 `depends_on 1` legs fail.
3. **`build`: fixed.** `gq build --model M` gives `3d66be3572228cec`. `gq build` gives a plain message.
4. **`ask` home folder: fixed up to the model load; T1 decides.** `edit.py`'s body imports under empty `HOME`, and the patched source has no `X.MODEL`.
5. **`import`: partly.** Fixed: `From,Relation,To`, `,knows,B`, `#1 Dad…`, weights 5 and 7, `--both nosuch`, `--inverse nosuch=y`, `;` and tab files. John Smiths are documented. Open: `from,to,relation` and `source,target,relation` still import as edges, exit 0, with every column wrong.
6. **Tracebacks: partly.** Import and `check` cases are plain. Open: `gq try` on files `check` refuses: `format: x210-graph/2` (AssertionError), a list relation (TypeError), `change: 3` and `splice: ["nosuch"]` (KeyError). `prop: 70000` passes `check`, then "does not fit the firmware: 'H' format requires…".
7. **Requirements: fixed.** `/usr/bin/python3 gq.py sim G --model M path a b`: "older than Python 3.12". Python 3.15 without torch, `CHIP_CC=/nope`: plain messages. `CHIP_CC=/usr/bin/clang`: same answer. README:29-35 is unchanged.
8. **`--examples`, `--tools`: mostly.** Misspelt `fn`, wrong arg, wrong field, tool not offered, non-list and missing file are plain and before the load; `path, close` works; my course examples pass; the `legs` description now uses the graph's relations. Open: `"calls": 5` and `"args": 5` give TypeError (`calls.py:53,58`), `"result": 5` passes, `--tools ,` offers nothing. `run.py:53`: read only.
9. **Firmware guide: partly.** Neighbours edit worked and undo restored the hash. A one-space `f_path` edit now gets the plain hint. New item 2 is wrong advice.
10. **`sim` extra arguments: fixed.** `gq sim G --model M path a b c`: "path takes…".
11. **Modularity: fixed.** Folders listed, train wording documented, New York prompt gone with token counts unchanged. List below.
12. **Default weights: fixed.** TOOLKIT states both.
13. **`web/check_figures.py`: fixed.** 3266 checks, 0 failed.
14. **Tests: fixed, but see new item 1.** 54 checks on Python 3.9, 61 with `--model`. They now cover the blockers. No BOM, CRLF or quoted-comma test, though those behave.

**Small:** token count and `zlib` fixed. `.gitignore` partly: `t8/fw/build/` and `tok/build/` show as untracked after the first `sim`. `find | A|B` still prints `NORELATION B`. **Licence:** partly: the model licence is stated, and the MTA's terms are neither named nor linked.

## New

1. **`test_toolkit.py --model` runs `build`** (`:166-167`; read, not run with another clang). It needs lld, which `sim` doesn't, and asserts clang 23.1.4's hash, though TOOLKIT says another clang differs. With another clang the setup test fails and leaves a non-frozen `writes.elf` that `sim` then uses. Fix: a separate `--build` flag, building in a temp copy.
2. **The guide's `f_path` advice is wrong.** I edited `NOPATH` in `gen.py` and `reflib` only: `gq sim courses path "Art History" Precalculus` printed `NOPATH`, DIFFER; only the shared-name route changed. Editing `fw/graphlib.c` too made all four calls agree. Fix: say both, since the helpers stay in the C base.
3. **`run.py --graph` on a three-field file should crash after the model load** (read): `edit.py:113` calls `reflib.Graph` after `ExecChat` at `:307`. That constructor alone gave `KeyError: 'format'`. `gq ask` fills the fields; `run.py` doesn't. Fix: `C.filled` in `run.py`.
4. **`nq` comment doesn't match the repo.** `tok/overlay.py:25` and the published tokenizer (`<|reserved_0|>` at id 248070) put Qwen's vocabulary at 248,070. I can't read Qwen's own tokenizer from the copy. If its `len()` is 248,077, the patch matches the frozen runs and lets Qwen pick `reserved_0` to `reserved_6`, as they could. Confirm in T1.
5. **`CHIP_CC` overstated, failure misnamed.** `tok/engine.c:6` includes `arm_neon.h`, so x86 can't compile it (read). A failing compiler prints "The graph does not fit the firmware: Command […]" (`sim_run.py:23`).
6. **More `try` and `sim` disagreements,** each marked `DIFFER` by `sim`. Non-ASCII digits: `follow | Oak | red | ٣`, `chase | Oak | red ٣`, `find | @３`, `link | Oak | red | Elm | ٣`; `try` accepts, `sim` refuses. A NUL in a relation passes `check`; `try` answers, `sim` prints `BADARG neighbours`. Fix: ASCII digits in `reflib`, refuse NUL in `problems()`.
7. **Small.** `--both` with a repeated row gives no note and `--inverse` says 2 rows (`gq.py:164`). A lone-surrogate label: `check` traceback. `ask` leaves a temp graph per attempt. `exam/AFTER.md:290` says "All fixed", which this doesn't support.

## What remains, ranked

Stops or seriously misleads a builder:

1. New 1: the documented setup test can fail and replace the firmware.
2. New 2: the guide sends firmware editors to the wrong place, though `sim` catches it.
3. New 3: a lost model load.
4. Item 5: reordered columns import silently.
5. Item 2: `check` passes, then `link` or a long `chase` refuses.

Doesn't stop anyone: new 4 (unless T1 says otherwise), new 5, 6 and 7, items 6 and 8, small items, licence.

## Files `sim` needs

My 4.8 MB lift carried spare files, and your fix dropped `exam/items/nyc.json`, so I retraced. An audit hook logged every file `sim` (all 11 calls) and `check --firmware` opened. I copied exactly these 39 files (480 KB) to an empty folder and ran from scratch under an empty `HOME`: 15 calls matched the full bundle's answers and token counts. Removing any one non-vendor file broke `check --firmware`. Vendor files weren't tested one by one.

```
gq.py
toolkit/calls.py
toolkit/sim_run.py
lib/reflib.py
host/tools.py
cop/boot.py
cop/cop_ref.py
exam/mach.py
exec/covdiff.py
rvc/box.py
rvc/decode.py
t8/fw/build_r6/writes.elf
t8/fw/cov.py
t8/fw/noun.py
t8/fw/overlay.py
t8/fw/tokrun.py
tok/boot_tok.py
tok/cexec.py
tok/common.py
tok/compile_ir.py
tok/core.py
tok/engine.c
tok/fragments.py
tok/overlay.py
vendor/qwenputer-riscv/chipformer/__init__.py
vendor/qwenputer-riscv/chipformer/dsl/__init__.py
vendor/qwenputer-riscv/chipformer/dsl/graph.py
vendor/qwenputer-riscv/chipformer/q35/__init__.py
vendor/qwenputer-riscv/chipformer/q35/emit.py
vendor/qwenputer-riscv/chipformer/q35/ir.py
vendor/qwenputer-riscv/chipformer/q35/prims.py
vendor/qwenputer-riscv/chipformer/q35/tiny.py
vendor/qwenputer-riscv/chipformer/rv/__init__.py
vendor/qwenputer-riscv/chipformer/rv/asm.py
vendor/qwenputer-riscv/chipformer/rv/bridge.py
vendor/qwenputer-riscv/chipformer/rv/elf.py
vendor/qwenputer-riscv/chipformer/rv/hf.py
vendor/qwenputer-riscv/chipformer/rv/ref.py
vendor/qwenputer-riscv/chipformer/rv/spec.py
```

The first run writes `tok/build/` and `t8/fw/build/`. To redistribute, also carry `LICENSE` and `licenses/qwenputer-LICENSE`.

Smaller sets, run on Python 3.9: `import` and `check` need `gq.py` and `toolkit/calls.py`. `try` adds `try.py`, `lib/reflib.py` and `t8/fw/noun.py`.
