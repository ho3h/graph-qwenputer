# X2.10 fw/ development log: CPU groundwork for the next rungs

Development; no gate, no model weights, no MPS, no merged checkpoint. Written as work proceeds; every number names its file.
All paths are under `xseries/X2.10/`. Every process ran under `tools/memguard.py --limit-gib 12 --log fw/mem.log`.

## Item 1: token histogram by C function (done 2 Nov, 00:25 ET)
**Method.** `fw/fwbox.py` `ProfMachine` subclasses `ref.Machine` and counts tokens per (calling context, pc), through `bridge.Session`,
with no effect on any record. `fw/hist.py` runs the same call sets in the same order as `rvc/test_m1.py` `task_real` and `task_dev`.
`fw/hist_report.py` attributes each pc by symbol table and DWARF inlining (`fw/attrib.py`).
- **The symbol table alone is not enough.** -O2 folds gather, the parser and almost every f_* into `main`: a real chase has 4,467 of
  5,546 tokens in `main` by symbol (`results/hist_rvc.json`, `symtab_tokens_mean`). So the attribution adds `llvm-symbolizer --inlining`
  on a `-g` build. That build's text, rodata and data equal `rvc/build/graphlib-bridge.elf` (`attrib.same_code`, asserted at run).
- **Check on the counter.** Calls and mean tokens equal M1's on all 19 function groups to the printed decimal (`results/hist_rvc.json`
  against `rvc/results/m1_full.summary.json`), and stage tokens sum to chip tokens on every group (`counted_equals_chip`). The call
  stack returned to root at every HALT (`ctx_not_root_at_halt` is 0 everywhere).
- **Run.** `results/hist_raw_rvc.json.gz`, `results/hist_rvc.log`: 1,041 s, 4 workers, peak 1.45 GiB. r097 does not fit (known).

**Stages** (`hist_report.py`): capture = `gather`. parse_call = `call` and its tag scanners. parse_args = chase's legs, `steps`, `direction`.
resolve = relation and node lookup. work = the walk or search. print = `put*`. `frame` and `go` are under 0.5% and left out below.

| Function | Calls | Mean tokens | Capture | Parse call | Parse args | Resolve | Work | Print |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **real** find | 487 | 3,033 | 26.6% | 47.3% | 0 | 16.1% | 0.4% | 9.1% |
| real follow | 190 | 6,342 | 25.1% | 52.3% | 1.6% | 10.7% | 4.8% | 5.2% |
| **real chase** | 21 | 5,546 | **23.8%** | **45.8%** | **11.9%** | 8.3% | **5.4%** | **4.4%** |
| real neighbours | 505 | 6,058 | 26.6% | 55.9% | 0.4% | 11.4% | 1.8% | 3.6% |
| real path | 71 | 7,409 | 15.2% | 29.5% | 0 | 9.7% | 29.6% | 15.8% |
| **real cheapest** | 48 | 46,713 | 2.7% | 5.2% | 0 | 1.9% | **86.2%** | 3.9% |
| real close | 12 | 2,702 | 26.5% | 49.1% | 0 | 10.6% | 0.9% | 12.5% |
| real link | 6 | 8,763 | 23.3% | 50.5% | 1.1% | 15.6% | 2.0% | 7.2% |
| real unlink | 18 | 7,191 | 22.5% | 47.4% | 0 | 21.5% | 0.9% | 7.4% |
| **dev** find | 10,337 | 3,315 | 23.4% | 40.9% | 0 | 21.4% | 0.4% | 13.5% |
| dev follow | 1,259 | 6,200 | 24.4% | 50.6% | 1.7% | 8.4% | 8.7% | 5.9% |
| dev chase | 11,877 | 6,093 | 20.8% | 40.1% | 11.7% | 10.8% | 9.7% | 6.7% |
| dev neighbours | 495 | 4,728 | 26.7% | 53.9% | 0.3% | 9.3% | 2.8% | 6.6% |
| dev path | 689 | 16,225 | 6.6% | 12.6% | 0 | 2.8% | 72.3% | 5.6% |
| dev cheapest | 1,876 | 133,087 | 0.8% | 1.6% | 0 | 0.3% | 95.6% | 1.6% |
| dev close | 1,566 | 2,624 | 27.0% | 49.7% | 0 | 8.3% | 0.9% | 13.6% |
| dev reopen | 493 | 3,012 | 24.4% | 45.3% | 0 | 11.6% | 5.3% | 13.0% |
| dev link | 297 | 6,997 | 25.1% | 53.5% | 1.1% | 9.2% | 2.0% | 8.8% |
| dev unlink | 297 | 6,150 | 24.7% | 51.5% | 0 | 10.5% | 3.0% | 10.0% |

`reopen` was never called by Qwen in `host/out`, so it has no real row.

**The chase, settled (real calls, n = 21, 45.6 captured tokens, 119.5 captured bytes; all from `results/hist_rvc.json`):**
- **The report's "about 52% parsing" does not hold: it is low.** Capture plus tag parsing is **69.7%** (3,864 of 5,546). With the legs, **81.6%**.
  With name and relation lookup, **89.9%**. The walk itself is 5.4% and the printing 4.4%. Its interpolation came from unknown-function
  calls, which stop at `NOFUNCTION` before the parameter loops, so it misses most of what a real call pays.
- **Tokens by C function:** `find_lit` 1,503, `gather` 1,323, `f_chase` 441, `at` 376, `call` 203, `ghash` 186, `eq_lit` 179, `trim` 169, `ws_at` 169,
  `named_at` 163, `rv_ecall2` 145, `next_param` 118, `walk` 66, `cur_first` 61.
- **What a byte costs:** 11.1 tokens to gather and 21.3 more to scan, so 32.3 tokens per captured byte, or 84.7 per captured token. The report's slope
  was about 56 per token. Most of those bytes are template text the machine already knows: `<parameter=`, `</parameter>`, `</function>`.
- **Mean tokens per instruction:** capture 1.44 (SB is 4 tokens), parse_call 1.03. The cost is instruction count, not value width.
- `dev` chases agree on the order: 60.9% capture and tag parsing, 72.6% with legs, 83.4% with lookup, 9.7% work, 6.7% print. They walk longer and print longer names.

**`cheapest` (`results/hist_rvc.json`):**
- Real mean 46,713, median 82,992, max 84,726: 86.2% search. Dev mean 133,087, median 91,662, max 1,717,803: 95.6% search.
- **Search by C function, real:** the shared-cursor walk over edges (`cur_next` 6,704, `rit_next` 3,965, `cur_other` 2,063, `cur_w` 1,472, `rit_init` 892, `is_closed` 437, `has_slow` 433) is
  15,965 tokens, 40% of the search. The queue (`hpop` 5,774, `hq_pop` 2,563, `hpush` 1,060, `hq_push` 323) is 9,720, 24%. `relax` plus its best-cost helpers about 7,000, 17%. `f_cheapest`'s own lines 7,519.
- **It never stops early:** it finalises every reachable node, because `f_cheapest` runs the queue dry. The answer is known once the target is finalised.
- This is the same case as `path_tight` (`cop/DEVLOG.md`): the general cursor code runs while nothing is closed or edited.

**So item 3 is supported on both counts.** 69.7% of a chase is the machine reading its own template, and `cheapest` searches past its answer through a general cursor.

Not run in this item: `limits`, `framing`, `random`, `medium` parts of M1 (the brief asks for real and dev only), and anything on weights.

## Item 2: the capacity law (done 2 Nov, 00:45 ET)
Files: `fw/capacity_core.py` (the vendored compiler with its address decode patched in memory, `results/capacity_core_*.json`), `fw/capacity_law.py`
(`results/capacity_law.json`), `fw/overlay_cost.py` (`results/overlay_cost.json`). Marked below: **computed** from code, **checked** computed and then run,
**estimated** on paper for circuits that do not exist.

### What one key head holds (computed: `core.py`, `q35/ir.py`)
A chip layer has one attention sublayer with 16 key heads. A key head has 2 value heads × 128 rows × 128 columns, of which 126 carry data.

| Table | Key heads now | Bytes per key head | Layout |
|---|---:|---:|---|
| ROM | 32 | 8,192 | 2-hot rows, byte columns |
| DROM | 16 | 8,192 | 128 rows × 2 × 32 bytes, read-only, 32 of 126 columns per row used |
| RAM | 32 | 1,024 | 128 rows × 2 × 1 word, 64 of 126 columns (the SW and SB write sources) |
| Text buffer | 1 | 80 rows × 16 bytes | |

The merged build: 103 key heads, 11 chip layers, hidden 3,968 (`results/capacity_core_base.json`, equal to `docs/rv-store.md`'s core column).

### The law of the C build (checked)
- **DROM = 12,504 + (12 + mean label bytes) N + 12 E + (5 + mean relation-name bytes) R bytes.** Within 4-6 bytes of padding on 5 real boots, including N = 1,024, E = 7,486 (`checked.drom_law_vs_boot`).
- **RAM .bss = 256 + 1,280 + E_tomb/4 + 4,096 + 4N + max(2N, 8,192) + 7N/8 + 1,792 + 124,** plus 560 bytes of stack (M1's lowest SP). Within 4 bytes of the linked `_end` at MAXN 1,024 to 2,816 (`checked.recompile_vs_reflib`).
- **Rows per head:** 682 edges per key head of DROM (12 bytes: out and in entries, both weights), 146 added edges per key head of RAM (7 bytes).
- **Format limits, not head limits (computed):** N ≤ 4,096 (12-bit handle in the edge entry and the Dijkstra key). E ≤ 32,767 (cursor `i | e << 16`, `OV` in bit 31). E ≤ 10,752 tombstones as compiled, E/4 bytes of RAM. R ≤ 64. Labels ≤ 64 bytes. 256 added edges as compiled.
- **`N ≤ 1,024` is a compile-time constant, not a capacity limit (checked).** Recompiled with `MAXN` 2,048, 2,560 and 2,816, the same 128 KB and 32 KB ran 12 calls each equal to reflib, at N = 2,032, 2,544, 2,800 near the DROM edge. `MAXN` 3,072 does not link (`.bss` over by 640 bytes). So today's image reaches about N = 2,800 with no new head, with E shrinking along the DROM law (E = 3,332 there).

### What more heads cost (computed: IR builds; none of these machines has run a program)
| Build | Added key heads | Chip layers | Slots | Hidden | GB (estimate) | Edges added at 12 bytes |
|---|---:|---:|---:|---:|---:|---:|
| Today: 128 KB DROM, 32 KB RAM | 0 | 11 | 1,265 | 3,968 | 18.8 | |
| 256 KB DROM | 16 | 12 | 1,265 | 3,968 | 19.10 | +10,922 |
| 512 KB DROM | 48 | 14 | 1,265 | 3,968 | 19.69 | +32,768 |
| 1 MB DROM | 112 | 18 | 1,265 | 3,968 | 20.88 | +76,458 |
| 2 MB DROM | 240 | 26 | 1,265 | 3,968 | 23.25 | +163,840 |
| 64 KB RAM | 32 | 13 | 1,296 | 3,968 | 19.40 | |
| 128 KB RAM | 96 | 17 | 1,296 | 3,968 | 20.58 | |
| 512 KB DROM, 64 KB RAM | 80 | 16 | 1,296 | 3,968 | 20.29 | +32,768 |
| 1 MB DROM, 64 KB RAM | 144 | 20 | 1,296 | 3,968 | 21.47 | +76,458 |

- **DROM: 16 key heads, one layer, about 0.30 GB per 128 KB, and hidden does not move.** RAM: two layers and about 0.60 GB per 32 KB.
- **The GB formula is an estimate,** calibrated on two figures: 2 × hidden × (vocabulary + 37,400 per chip layer + 1,473,000), from 18.8 GB and 1.63B dense chip weights (`rvc/DEVLOG.md`). Checked on one figure it did not see: `--store` builds to 12 layers, 164 heads, 1,806 slots, hidden 4,608, as `docs/rv-store.md` says, and the formula gives 22.18 GB against that doc's 22.3.
- **Speed is not costed.** Each chip layer also runs on every text token. No build here has a measured rate.
- **What a bigger DROM needs besides heads (not done):** `spec.py`'s map, `cop/boot.py`'s size, a moved DROM base, and the cursor and tombstone formats above E = 10,752 and 32,767.

### What each option can and can't hold (computed, `computed.table`; 16-byte labels, except 18 for the NYC estimate; R = 20, or 50 for the NYC estimate, or 4)
NYC was not read. Its row uses DESIGN's estimate (496, 1,761) and a guessed 50 relations.

| Graph | N | E | DROM needed | RAM needed | Today | Recompiled, no new heads | Smallest that holds |
|---|---:|---:|---:|---:|---|---|---|
| NYC estimate | 496 | 1,761 | 49 KB | 24.0 KB | holds | holds | today |
| Frontier of today's image | 1,024 | 7,486 | 131.0 KB | 24.0 KB | holds | holds | today |
| Near the recompile limit | 2,800 | 3,332 | 131 KB | 32 KB | no: N | holds (12 calls run) | recompile |
| Sparse, E = 4N | 2,048 | 8,192 | 168 KB | 29.0 KB | no: N, DROM | no: DROM | +16 KH |
| r097 (dev) | 928 | 12,503 | 182 KB (real boot) | 24.4 KB | no: DROM | no: DROM | +16 KH |
| **Dense** (1,024, deg 16) | 1,024 | 16,384 | 238 KB | 25.4 KB | no: DROM | no: DROM | +16 KH |
| **Dense** 25% | 256 | 16,384 | 217 KB | 25.4 KB | no: DROM | no: DROM | +16 KH |
| **Dense** complete | 128 | 16,256 | 211 KB | 25.4 KB | no: DROM | no: DROM | +16 KH |
| **Dense** 12% | 512 | 32,000 | 411 KB | 29.3 KB | no: DROM | no: DROM | +48 KH |
| **Large** sparse | 4,096 | 16,000 | 319 KB | 40.3 KB | no: all | no: DROM, RAM | +80 KH |
| **Large** sparse | 4,096 | 30,000 | 487 KB | 43.8 KB | no: all | no: DROM, RAM | +80 KH |
| Past every format | 4,096 | 65,536 | 914 KB | 52.7 KB | no | no | none without a wider cursor |
| **Edits:** NYC estimate + 1,000 live added edges | 496 | 1,761 | 49 KB | 29.2 KB | no: overlay 256 | holds, by recompiling the overlay | recompile, but see cost below |
| **Edits:** NYC estimate + 4,000 live added edges | 496 | 1,761 | 49 KB | 50.2 KB | no | no: RAM | +32 KH (64 KB RAM) |

### Graph circuits and `EXPAND` on paper (estimated, `estimated` in the JSON)
The ranges come from a choice the design has not made: whether one row holds a whole edge and is rewritten whole (75 bits, fits one value head), or whether `{from, rel, to, w}`, next-out, next-in and alive are written apart (four value heads per row, since a head write replaces the whole row).

| Key heads | Envelope (4,096, 16,384, R 64) | (1,024, 16,384, R 20) | (256, 16,384, R 20) | NYC estimate (496, 1,761, R 50) |
|---:|---:|---:|---:|---:|
| Node rows | 32 | 8 | 2 | 4 |
| Label bytes, boot-only byte table, 64 bytes each | 32 | 8 | 2 | 4 |
| Label directory, boot-only | 2 | 2 | 2 | 2 |
| Edge rows | 64-256 | 64-256 | 64-256 | 7-28 |
| List heads: one per node | 32 | 8 | 2 | 4 |
| List heads: hashed (node, rel), load 1/2, both ways | 256 | 256 | 256 | 28 |
| List heads: dense N × R, both ways, as COPROCESSOR.md's table reads | **2,048** | 160 | 40 | 194 |
| **Total, least to most** | **162-2,370** | 90-434 | 72-302 | 21-232 |
| **Added layers** | **11-149** | 6-28 | 5-19 | 2-15 |

- **DESIGN's law omits the list heads.** `first-out[(node, rel)]` dense is N × R, a second quadratic-looking term, and the largest line in the envelope. COPROCESSOR.md's proposal 6 (one list per node) avoids it. The review should pick one.
- **`EXPAND`:** key heads per (slot, direction) = ⌈N/128⌉ × ⌈N/252⌉. DESIGN's 8, 33 and 520 are one direction, unrounded; the instruction set has both.

| N | Per slot and direction | One slot, in and out | Four sets | Residual dims added, at least | Hidden | Layers added | GB |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 256 | 4 | 8 | 8 | 512 | 4,608 | 1 | 22.18 |
| 496 | 8 | 16 | 8 | 992 | 4,864 | 2 | 23.78 |
| 1,024 | 40 | 80 | 20 | 2,048 | 6,144 | 7 | 32.33 |
| 1,024, 4 slots (DESIGN's envelope) | 40 | 320 | 20 | 2,048 | 6,144 | 22 | 39.22 |
| 2,048 | 144 | 288 | 36 | 4,096 | 8,192 | 21 | 51.68 |
| 4,096 | 544 | 1,088 | 68 | 8,192 | 12,288 | 73 | 125.32 |

- **Hidden size is the main cost of sets, and the heads are not.** A set read crosses the residual as N dims and a set op reads two. So the 2N is a floor, and it moves hidden through `pick_hidden`'s steps. Even N = 256 goes from 3,968 to 4,608, +3.4 GB, more than a 1 MB DROM costs. DESIGN's law counts heads only.
- **`EXPAND`'s read has a known risk.** `docs/rv32.md` records that an 8-hot read left 2e-8 residues on the fla kernels, because 1/√k is not exact, and the core went back to one-hot and 2-hot reads. A frontier is k-hot for any k. Thresholding at > 0 may absorb the residue. A3 has not been run, so this is unknown.
- **Unused density (estimated, not built):** the DROM uses 32 of 126 columns per row. If all 126 work with its 2-hot read and gates, a key head holds about 32 KB rather than 8 KB. Nobody has tried this.

### The critic's point: "the same heads would buy several times more read-only DROM"
**It holds for read-only graphs:** 682 edges per key head of DROM against 64-256 of graph rows, so **2.7× to 10.7×** (geometry computed, the row layout estimated). At E = 16,384 the rows alone take 64-256 key heads; 64 key heads of DROM is 512 KB, and +16 already holds that graph. At every row of the table with E ≤ 16,384 and N ≤ 2,800 the software build needs at most 1 more layer.

**It does not hold for writes.** Each added edge needs writable state whichever way it's built: 146 per key head of RAM against 64-256 of rows, the same order. So capacity alone gives no several-fold case either way for writes. The difference there is cost per call (`results/overlay_cost.json`, c024, the rvc firmware, every answer equal to reflib):

| Live added edges | Chase mean (8 calls) | Neighbours | Cheapest (1 call) |
|---:|---:|---:|---:|
| 0 | 5,367 | 4,614 | 82,297 |
| 16 | 5,598 | 4,973 | 647,219 |
| 64 | 6,042 | 5,363 | 1,772,790 |
| 128 | 6,505 | 5,873 | 3,269,721 |
| 256 | 7,542 | 6,919 | 6,263,925 |

The overlay is scanned per list per relation. A chase pays about 8.5 tokens per added edge, and `cheapest` goes up 7.9× at the first 16 and 76× at 256. `close` adds nothing to this overlay: it sets a bit. What a closed node costs later searches was not measured here.

**What this means for condition 2.** "A graph the software build cannot hold" depends on what the software build is. Against today's frozen image, anything past the table's first rows qualifies. If that build may grow by one layer, nearly nothing with E ≤ 16,384 qualifies except heavy edits. **That definition needs fixing before the graph is registered.** On capacity alone, a hardware case rests on run-time edits. `EXPAND`'s case is token savings, and condition 1 says tokens are not the reason.

### Candidate shapes for "a registered graph the software build cannot hold" (Theo picks; nothing is registered)
| Shape | Example | Today's build | Software with more heads | Graph hardware (estimated) | What it would show |
|---|---|---|---|---|---|
| **Large and sparse** | N = 4,096, E ≈ 16,000, city or grid-like, from a registered seed | No: N, DROM and RAM | +80 KH, 5 layers, 20.29 GB | 162-2,370 KH before `EXPAND`, outside its envelope (N ≤ 1,024) | Capacity by size. Hardware's head bill may exceed software's unless it uses per-node lists and whole-row edges |
| **Dense** | N = 256, E = 16,384, 25% density, diameter about 2. Or N = 128, complete | No: DROM, by 86 KB | +16 KH, 1 layer, 19.10 GB | 72-302 KH, plus `EXPAND` 16 KH and hidden 4,608 | Set-at-a-time reads where they are strongest, but that is a token result: one layer of DROM holds it |
| **Edit-heavy** | NYC-scale base plus ≥ 4,000 live added edges, or a graph built entirely by `link` | No: `FULL` at 256 | +32 KH of RAM holds it, and every call scans the overlay (over 6M tokens per `cheapest` at 256) | 16-63 KH of rows for those edges, no scan | The one class DROM can't buy, and it fits the headline, exact edits. Needs its own cost bar, since holding isn't the difference |

### Proposed, not applied
- DESIGN "Capacity law": replace with the above; add list heads, hidden growth from sets, and both `EXPAND` directions.
- PATH / condition 2: define "the software build" (frozen today's image, or the C build at the same head budget).
- COPROCESSOR.md: decide row layout and list heads, since they move the total by more than 10×.

## Item 3: a firmware parse and `cheapest` pass (done 2 Nov, 01:55 ET)
Item 1 supports it (69.7% of a chase is reading its own template; `cheapest` searches past its answer). `fw/graphlib.c` is a copy of `rvc/graphlib.c` 7efccc0e, with general changes only. The diff is `fw/graphlib.diff`, the build `fw/build/fw.elf` e908647b. No new instruction. Each change can be switched off with `-DFW_NO_x`.

**The changes, all kept:**
- **PARSE.** A call in the template's exact token shape is walked row by row. Template rows are compared in place as words, and only names and values are copied. Anything else, including a full row or row 80 in use, returns with nothing printed and the old `gather` and parser decide. All but one of Qwen's 1,358 saved calls take this path (`results/fast_path_real.json`). A name or value containing `<`, or a name containing `>` or a newline, is refused, so the regex in `host/tools.py` can't find anything the walk doesn't. Function and key names go by length and bytes rather than a loop over tables.
- **LEGS.** Chase parses its legs in one pass, remembering the first bad leg, because a wrong leg count outranks it. `trim` returns at once when both ends are plain bytes.
- **PUT.** Putchar sets only a0 and a7. A label prints through a pointer.
- **CHEAPEST.** It stops when the target is finalised, since a finalised node is never touched again. While nothing is closed or edited, a tight loop over each node's whole list runs, in the same entry order; if its queue would spill, the general search starts over.

**Bar: zero mismatches. Result: zero** (`results/m1_fw/m1_full.summary.json`, `results/m1_fw.log`, 553 s, 4 workers, peak 2.58 GiB). `fw/test_m1_fw.py` imports `rvc/test_m1.py` unchanged and only redirects the ELF and the output folder.

| Part | Checks | Match | TOOLONG, as predicted | Mismatches |
|---|---:|---:|---:|---:|
| dev | 29,186 | 29,186 | 0 | 0 |
| real | 1,358 | 1,358 | 0 | 0 |
| random | 24,000 | 22,788 | 1,212 | 0 |
| medium | 512 | 497 | 15 | 0 |
| limits | 332 | 330 | 2 | 0 |
| framing | 33 | 31 | 2 | 0 |

Same counts as M1's. The ELF that passed and the one with item 4's `#ifdef FW_ONELINE` in the source have the same code (`attrib.same_code`, run).

**Tokens per call, before and after** (`results/before_after.json`; before is `rvc/results/m1_full.summary.json`):

| Function | Real: before | After | × | Dev: before | After | × | Dev max: before | After |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| find | 3,033 | 1,303 | 2.33 | 3,315 | 1,595 | 2.08 | 8,283 | 5,670 |
| follow | 6,342 | 2,568 | 2.47 | 6,200 | 2,589 | 2.40 | 36,175 | 32,612 |
| **chase** | **5,546** | **2,485** | **2.23** | 6,093 | 2,912 | 2.09 | 11,322 | 7,523 |
| neighbours | 6,058 | 2,372 | 2.55 | 4,728 | 1,831 | 2.58 | 6,983 | 2,812 |
| path | 7,409 | 4,324 | 1.71 | 16,225 | 12,755 | 1.27 | 616,496 | 591,566 |
| **cheapest** | **46,713** | **12,577** | **3.71** | 133,087 | 37,995 | 3.50 | 1,717,803 | 1,253,431 |
| close | 2,702 | 1,060 | 2.55 | 2,624 | 995 | 2.64 | 3,722 | 1,714 |
| reopen | not called | | | 3,012 | 1,343 | 2.24 | 5,277 | 3,220 |
| link | 8,763 | 3,697 | 2.37 | 6,997 | 2,633 | 2.66 | 7,931 | 3,145 |
| unlink | 7,191 | 3,257 | 2.21 | 6,150 | 2,434 | 2.53 | 6,710 | 2,855 |

- **Each change alone, real calls** (`results/per_change_real.json`, real, limits and framing with 0 mismatches for each): chase 5,589 with all off, 3,010 PARSE only, 5,134 LEGS only, 5,513 PUT only; cheapest 45,660 all off, 15,750 CHEAPEST only, 43,144 PARSE only. PARSE is nearly all of it outside `cheapest`.
- **What a chase is now** (`results/hist_fw.json`, real, n = 21): capture walk 1,041 (41.9%), legs 391, lookup 317, call parsing 283, walk 275, print 164. So reading its own call is still 69% of a smaller number, with legs. `cheapest` is now 9,229 tokens in `cheapest_tight` of 12,577.
- **The forecast.** Replaying Qwen's 358 calls from the byte-token control (`results/forecast_from_control_calls.json`, every result equal to the transcript): **3,626,632 tokens before, equal to the report's 3.63M, 1,036,463 after, 3.5×.** Cheapest questions go 301,662 → 66,454 each, chase questions 39,133 → 16,197. `cheapest` is still 51% of the forecast. This is that transcript's flow; it says nothing about accuracy.
- **What got worse:** a call the walk refuses pays for the walk and then the old path. The largest real case: neighbours max 7,876 → 9,236, the one saved call outside the shape. `random` link max 13,899 → 14,757. Random calls gain least (chase 1.59×), since adversarial text is often refused.
- **`path` is barely helped at scale** (medium 1.05×). Its search is unchanged. On dev paths, `path_tight`'s mark test is the largest line, 2,184 of its 5,959 tokens (`results/hist_rvc.json`, `top_lines_mean`, line 787).
- **Fit:** ROM 34,380 bytes of 262,144, rodata 632 of 4,096, `.bss` ends at 24,448 (the byte map `cst` adds MAXN bytes), lowest SP 0x7D10 (752 bytes used, was 560). So 7,568 bytes stay free. **The price against item 2's law:** the byte map lowers the no-new-heads limit from about N = 2,800 to about 2,300: MAXN 2,304 links with 800 bytes left for a 752-byte stack, 2,432 leaves 48, 2,560 does not link (`results/capacity_fw_maxn.json`, links only, no calls run). The DROM law and the frontier are unchanged (same `max_E` per N in the summary's `fit`).

**Other tests.**
- **Aimed fuzz** (`fw/fuzz_fw.py`, `results/fuzz_fw.json`, `results/fuzz_rvc.json`): 28,489 calls (16,000 perturbed call shapes, including 400 vocabulary tokens per seed holding template characters; 6,000 odd legs; 6,480 `cheapest` with ties, zero weights, near-65,535 weights, closures and edits; 4 queue spills and 5 calls on a chain of 65,535 weights). **fw and rvc give the same answer on every one:** where either differs from the host, both do, with the same bytes (80 cases, `only fw` 0, `only rvc` 0, `same got` 80). `results/fuzz_fw_chain.json` is the spill and chain part alone, after item `saturation` below, 10 of 10 on the real build.
- **Those 80 are all old, and none is new.** 72 are non-ASCII digits (`rvc/DEVLOG.md` divergence 4). 6 have `<tool_call>` or `</tool_call>` inside the fuzzed text, where the bridge itself restarts or ends the capture, as it should: an artefact of this fuzz. 2 are calls over 80 tokens with no function tag: firmware `TOOLONG`, host `NOFUNCTION`, loud. `capture_rule` in `rvc/box.py` predicts this wrongly, because it looks for `</function>` anywhere while the firmware looks after `<function=`. Worth a line when SPEC gets `TOOLONG`.
- **Can it fail?** 11 deliberate bugs (`fw/mutants.py`, `results/mutants.json`, `results/fuzz_mutants.log`, against a baseline of known mismatches): 9 caught by the quick M1 or the fuzz. Two were not at first:
  - `saturation`: no test reached a wrapped key. I added a chain to @19 to `fuzz_fw.py`, and it now answers `cost 65522` where the host says `OVERFLOW` on that mutant, 10 of 10 right on the real build (`results/fuzz_fw_chain.json`). The mutant list's own record predates this.
  - `row_80`: still not caught. By argument it changes no answer: anything lost past row 79 lies after `</function>`, which the regex ignores too. The guard stays because the circuit has no query for a row above 80, so the firmware shouldn't read one.
  - `tie_rule`, `name_gt`, `gt_prefix` and `leg_count_precedence` were caught only by the aimed fuzz, not by quick M1 (full M1 was not run on mutants). `gt_prefix` needed the vocabulary tokens added after the first mutant run, which missed it.
- **On the circuit's IR, no weights** (`fw/ir_check_fw.py`, `results/ir_fw.json`, 1,107 s, peak 3.62 GiB): c024 and r001, all functions, `cheapest` included, plus word loads from the text buffer, which the old firmware didn't use: **0 wrong predictions and 0 owner mismatches on 113,688 owned positions.**

**Not run:** the merged weights. M2's teacher stream on this firmware is the check still owed, needs MPS, and is the next step before adopting it. The firmware is snapshot state (`core.snapshot`), so adopting it needs no re-merge.

**Arithmetic, not measurement:** at the shared 47.68 chip tokens/s, a real chase goes from about 116 s to about 52 s. D2m at 12,000 chases goes from 66.5M to about 29.8M tokens, about 174 hours: still far past the 4-hour ceiling without the executor or the reference.

**Proposed, not applied:** adopt `fw/graphlib.c` in `rvc/` after an M2 teacher stream; try a byte map in `path_tight` as in `cheapest_tight`; closures keep the general search (`cheapest` after a `close` gains only the early stop), so D2 runs should be costed on closed-state calls, which this log has not separated.

## Item 4: the one-tool flow check (done 2 Nov, 02:05 ET)
`fw/oneline.py`, `results/oneline.json`. Machine only: no Qwen, no weights. `-DFW_ONELINE` makes `main` print the result and nothing around it, so HALT's echo ends the line. It changes the response, so it is a measurement build and not part of item 3's firmware.

**What a chase costs, on Qwen's own one-tool calls** (`rb/results/printout_one` and `printout_one_retry`: 40 calls, 34 questions, 47.1 captured tokens on average, 55 at most; re-encoded from saved text, every answer equal to the host tool):

| Build | Chip tokens, mean | Max | Echoed text tokens |
|---|---:|---:|---:|
| Today's firmware, wrapper (`rvc`) | 6,835 | 8,698 | 31.1 |
| Today's code, only the final line (`fw_off_line`) | 6,801 | 8,627 | 20.1 |
| This pass, wrapper (`fw`) | 3,393 | 4,722 | 31.1 |
| **This pass, only the final line (`fw_line`)** | **3,359** | 4,688 | 20.1 |

- **Dropping the response wrapper saves almost nothing: 34 chip tokens and 11 echoed tokens per call, about 1% of chip tokens.** A wrapper is a few putchars. The firmware pass saves 3,442. The one-tool flow's real saving is in the number of calls: a chase question in the byte-token loop took 39,133 chip tokens over 10.4 calls (`results/forecast_from_control_calls.json`, which uses that loop's calls and says nothing about accuracy), and with this firmware 16,197.
- **So one call on this firmware against that loop on today's: about 3,400 against 39,133,** 11.5× by arithmetic from these two files. The retry result (16/17) needs Qwen to read an error, so that branch needs some delivery Qwen can read.
- `fw_off` against `rvc` differs by about 25 tokens on the means, from moving the dispatch out of `call`. So that row stands in for today's code.

**By leg count, on chases that walk** (12 per leg count, c024, grown one leg at a time and checked by reflib, 1-3 steps a leg, 0 mismatches, 0 `TOOLONG`):

| Legs | Captured tokens, mean | Max | Chip: today | Chip: this pass | Chip: this pass, final line only |
|---:|---:|---:|---:|---:|---:|
| 1 | 41.3 | 42 | 5,482 | 2,479 | 2,445 |
| 2 | 47.6 | 48 | 7,537 | 3,896 | 3,862 |
| 3 | 53.9 | 56 | 9,394 | 5,230 | 5,196 |
| **4** | **60.2** | **63** | **11,404** | **6,608** | **6,574** |
| 5 | 65.7 | 67 | 13,393 | 7,992 | 7,958 |
| 6 | 72.2 | 76 | 15,151 | 9,193 | 9,159 |
| 7 | 78.0 | 80 | 17,274 | 11,018 | 10,984 |

Each added leg costs about 1,420 chip tokens on this firmware, about 1,965 today. So a leg is now the main cost of a long chase.

**The 80-token window** (`window` in the JSON; 28 dev cities, 40 samples per leg count per city, template text, start `@123`):
- **The template itself takes 31 tokens,** before any argument. `@123` takes 4 more, and each leg about 6-7.
- **4 legs always fit:** 1,120 of 1,120 at 60-63 tokens, leaving **17-20 tokens** of room. The longest label in these cities is 13 tokens, 9 more than `@123`, so a named start also fits at 4 legs, at 72 at most (arithmetic).
- **Legs:** 6 always fit (72-77). 7 sometimes (78-84). 8 never (84-91). One-letter relations reach 11 (80). This matches `rvc/DEVLOG.md`, so SPEC's 16 legs stay out of reach.
- **Relation names shaped like SPEC's example,** `A northbound` and `1 southbound` (strings from SPEC, no NYC data read): 7 legs at 78 and 6 legs at 77, so 4 legs at 60-63.
- **Qwen's own one-tool calls peaked at 55 tokens.** All 17 first-arm calls were 1 or 2 legs (8 and 9, `rb/results/printout_one`). So no saved Qwen call has reached 4 legs, and the 4-leg token counts above are template text.

**Not run:** Qwen on any of this. Whether a final-line-only response serves a retry, or what Qwen does next if it sees one, was not tested; the merged weights were not used, so these are reference tokens only. Time per call is left out, because there is no clean rate.
