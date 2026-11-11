# EXEC: a Mac executor for the machine's layers (Theo, 2026-11-01)

**Why.** Stock layers ran at about 48 machine tokens a second on a shared Mac, and the largest planned check is 66.5M tokens, about 387 hours. Theo: use an executor for proof of concept and testing, compare with the real weights periodically, and treat anything above 4 hours as unrealistic.

**The ceiling.** No single planned run above 4 hours. The 66.5M-token check would need about 4,600 machine tokens a second (66.5M ÷ 14,400 s). If the executor can't reach that, the check is reduced or moved to the reference machine, and that is stated before it runs. The ceiling is not a reason to loosen a bar.

**Acceptance, before the executor counts for anything.** All on dev graphs.
1. **Exact.** Every machine-owned position: the residual leaving the executor equals the residual leaving the stock chip layers, dim by dim, on real streams covering all ten functions, including limits and at least 100,000 owned positions. Any mismatch, tolerance or rounding difference is reported as found, never rounded away. If exact equality can't hold across number formats, this comes back to Theo and the lead with the measured difference.
2. **Can fail.** A saved negative control shows the check catches a wrong executor.
3. **Same tokens.** Decoding with the executor gives the same tokens as stock on the same streams.
4. **Speed.** Measured chip tokens per second, with what else was on the machine stated. No clean figure is claimed from a shared run.

**The periodic comparison with stock weights, once accepted.**
- Repeat the check after any change to firmware, circuit or executor, before using results from the new build.
- At each gate, a sample through stock weights, chosen before the run by a seed, at least 10,000 owned positions and at most 1 hour.
- Spot checks during long runs, at least one sample per run.
- Any mismatch stops the run, and its results don't count until explained.

**What it does not change.** Every result says whether it ran on the executor or stock. "Nothing outside the model, stock `transformers`" is claimed only for what ran on stock. A public demo runs on stock.

Under D161 the executor's acceptance is reviewed before it carries a gate.

## Whole-table check and coverage difference (2 Nov, round 2 critical review, finding 4, conditions 1 and 2)

**Why.** The executor is bit-equal to stock on what its streams exercise, about 60% of units. On the other 40% there is no evidence, and corrupted-table controls caught 10 of 24 and 2 of 6 for that reason. Written before any of the tools below has run on the real tables. Budgets are CPU estimates. CPU only, no MPS, no model forward pass, under `../tools/memguard.py --limit-gib 12`; a memory kill is a finding and the limit is not raised. `engine.c`, `cexec.py` and firmware are not changed. If a check finds a real difference, it stops and goes to the lead first.

**A. Tables against the IR (`tablecheck.py`).** Reads the compiled tables the executor loads and rebuilds, by its own reading of `engine.c`, every FFN unit (coefficient, `a` form, `b` form, output dim), every head channel with its lag taps, decay, write gate, output gate and output weight, as exact rationals, then compares them with forms taken directly from the IR nodes. It does not import `compile_ir.py`.
- **Passes if:** 0 differences across all 42,114 units, 20,388 gates and all heads; every number in every table is read by the check, with any that is not listed and explained; both firmwares load byte-identical tables, or each is checked separately; for each firmware the ROM rows in the heads equal the words in its ELF, read by a separate small ELF reader. Any unit it cannot check is reported with the reason.
- **Test of the check:** the 30 earlier corrupted-table cases (24 in `results/negative_tables_tinyten.json`, 6 in `../edits/results/negative_machine.json`) and 1,000 new single-number corruptions, seed 20261102: 10 in each table array, the rest uniform across all numbers in all arrays. **All must be caught.** Every miss is listed and counts as a miss in the rate, even if I can argue it changes nothing.
- **Guess:** 0 differences; 100% caught.

**B. IR against the merged weights (`weightcheck.py`).** Reads `<drive>/Models/x210-rvc/` lazily with safetensors, tensor by tensor, no model object. Rebuilds what the 11 chip layers should hold from the IR by its own code, and compares order-free for FFN units and by position for heads. It does not import `emit_layers`. It shares `emit.allocate`, because the slot map is not saved in the checkpoint; the check tests that map's lifetimes separately.
- **Passes if:** every nonzero in `gate`, `up`, `down`, `in_proj_qkv`, `conv1d`, `in_proj_z`, `in_proj_a`, `in_proj_b` and `out_proj` of the 11 chip layers is accounted for and equal, every unit expected is present, the fixed tensors have their fixed values, and the chip dims of every embedding row equal the token features the engine uses.
- **Test of the check:** 60 seeded single-weight changes (seed 20261102), half on nonzeros and half on zeros. All must be caught.
- **Guess:** layers 0 differences; can run on CPU, peak under 3 GiB. Embedding rows: I expect any difference to be on `<|reserved_*|>` ids, because the merge read the source tokenizer and the executor reads the merged one. If so, that is a real difference and it stops there for the lead.

**C. Coverage difference (`covdiff.py`, with a patched copy of the engine source that `diag_coverage.py`'s method generates under `build/`).** A run's coverage log lists gates fired, head channels fired, value heads read and written, each with its first position. The baseline is the union across the saved stock traces of both firmwares, counting only positions compared on stock, so a prompt is not counted, and it is built while replaying each trace and comparing kept dims to the saved stock bits. A gate run treats any gate outside the baseline as a finding that needs a stock window; the tool lists it and exits nonzero.
- **Passes if:** each saved stream against the full baseline gives 0 new; leave-one-out on each saved stream equals the set arithmetic done separately; a gate removed from the baseline is listed exactly; a log from different tables is refused; a stream that should differ does: the vendored `calc-bridge.elf` on big-number calls, which writes the digit-file and quotient heads no firmware here writes.
- **Guess:** the replay gives 0 kept-dim differences; the baseline falls slightly below the reported 11,572 gates once prompts are excluded (under 50); calc-bridge gives over 100 new gates and new written heads `bn*` and `quo*`. The hub past position 130,000 is also run, unpredicted beyond at least 1 new gate.

**Budget, CPU estimates.**
| Step | Estimate | Times 1.5 |
|---|---|---|
| A, real tables | 3 s per pass (estimate from about 230,000 expanded terms); build 3 s measured | 1 minute with both firmwares |
| A, 1,030 corruptions | 3 s each, 4 processes: 13 minutes | 20 minutes |
| B, 11 layers | about 3.6 GB off the LaCie, about 20 s of Python per layer: 5 minutes | 8 minutes |
| B, embedding | 266M feature calls at 3.6M a second measured: 74 s, plus 1.4 GB off the LaCie | 4 minutes |
| B, 60 controls | 2 s each | 3 minutes |
| C, baseline | about 537,000 positions at 3,581 a second, the slowest figure in the DEVLOG: 150 s | 4 minutes |
| C, tests | hub stream from the reference, about 500,000 positions; calc-bridge; leave-one-out from saved logs | 15 minutes |

Total about 55 minutes of CPU at that factor; stop at 2 hours wall and report what finished. No budget is raised to pass.

**Revision to A, before its second run (one, documented).** First run on seed 20261102: 1,029 of 1,030 caught, so the "all must be caught" bar was missed by one (`results/tablecheck_corrupt_run1.json`, kept). The miss moved one `v_expr` pointer from expression 12172 to 12173. If the two expressions hold the same form the engine computes the same value, and the check did list expression 12172's `ec` as unread, but it only reported unread numbers and did not fail on them. The revision: any number no entry reaches now fails the check. It was already 0 on the real tables. Rerun: the same 1,030 cases, then seed 20261103 with 1,000 new cases and the same 30 earlier cases, chosen by that seed before the rerun. Bar unchanged. If either misses, that is the result and it is reported, with no second revision.
