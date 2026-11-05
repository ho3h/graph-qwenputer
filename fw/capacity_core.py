"""Item 2, computed part: what more DROM or RAM key heads cost, from the vendored circuit compiler (IR build only).

    python capacity_core.py --drom-log2 17 --ram-log2 15 [--store] --out results/capacity_core_<tag>.json

The vendored core.py is read as text and only its address decode is patched in memory, so the same compiler builds the
circuit with a larger DROM or RAM (DROM base = its size, the text buffer at the RAM's size). The vendored files are not
written. No weights: this is graph building and slot allocation. Nothing here is executed on the circuit; a bigger table's
programs were not run, so the result is the build's size, not a tested machine.
"""

import argparse
import json
import os
import sys
import time
import types
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
VENDOR = os.path.join(X210, "vendor", "qwenputer-riscv")
sys.path.insert(0, VENDOR)
sys.path.insert(0, os.path.join(X210, "rvc"))

from chipformer.rv import spec as S  # noqa: E402
from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.q35.ir import FFN, Head, Target  # noqa: E402
from chipformer.q35.emit import allocate  # noqa: E402
from chipformer.q35.merge import pick_hidden  # noqa: E402

CORE = os.path.join(VENDOR, "chipformer", "rv", "core.py")
MODEL = ("<drive>/Models/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/"
         "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")


def patched_core(drom_log2: int, ram_log2: int):
    src = open(CORE).read()
    S.DROM_WORDS = 1 << (drom_log2 - 2)
    S.RAM_WORDS = 1 << (ram_log2 - 2)

    def sub(old, new):
        nonlocal src
        assert src.count(old) == 1, old
        src = src.replace(old, new)

    sub("hl = lits_of(EA[13:17], h)", f"hl = lits_of(EA[13:{drom_log2}], h)")
    # the bits of the table's base must sit above both tables and the text buffer
    base = max(drom_log2, ram_log2 + 1)
    sub('in_drom = c.and_([1 - b for b in EA[18:32]] + [EA[17]], "in_drom")',
        f'in_drom = c.and_([1 - b for b in EA[{base + 1}:32]] + [EA[{base}]] + [1 - b for b in EA[{drom_log2}:{base}]], "in_drom")')
    if ram_log2 != 15:
        sub("tsel = [EA[15]] + [1 - EA[b] for b in range(11, 15)]",
            f"tsel = [EA[{ram_log2}]] + [1 - EA[b] for b in range(11, {ram_log2})]")
        sub('in_ram = c.and_([1 - b for b in EA[15:32]], "in_ram")',
            f'in_ram = c.and_([1 - b for b in EA[{ram_log2}:32]], "in_ram")')
        sub('in_text = (c.and_(tsel + [1 - b for b in EA[16:32]], "in_text") if text else None)',
            f'in_text = (c.and_(tsel + [1 - b for b in EA[{ram_log2 + 1}:32]], "in_text") if text else None)')
    mod = types.ModuleType("core_patched")
    mod.__file__ = CORE
    sys.modules["core_patched"] = mod
    exec(compile(src, CORE, "exec"), mod.__dict__)
    return mod


def gb_estimate(hidden, chip_layers, vocab):
    """bf16 bytes / 1e9, calibrated on one measurement and checked on another (see DEVLOG):
    params = hidden * (vocab + 37,400 per chip layer (1.63B dense chip weights / 11 / 3968) + 1,473,000 for 32 Qwen layers)."""
    return round(2 * hidden * (vocab + 37_400 * chip_layers + 1_473_000) / 1e9, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drom-log2", type=int, default=17)
    ap.add_argument("--ram-log2", type=int, default=15)
    ap.add_argument("--store", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    core = patched_core(a.drom_log2, a.ram_log2)
    cfg = json.load(open(os.path.join(MODEL, "config.json")))
    tc = cfg["text_config"]
    T = BR.Text(os.path.join(MODEL, "tokenizer.json"))
    store = None
    if a.store:
        from chipformer.rv import store as ST
        store = ST.Config()
    target = Target(tc["linear_num_key_heads"], tc["linear_num_value_heads"], tc["intermediate_size"])
    c = core.build(target, T, store) if store else core.build(target, T)
    keep = set(c.keep)
    alloc = allocate(c, None, keep, tc["intermediate_size"])
    hidden, m = pick_hidden(tc["hidden_size"], 1 + alloc.n_slots)
    heads, units = Counter(), Counter()
    for n in c.nodes:
        if isinstance(n, Head):
            heads[n.level] += 1
        elif isinstance(n, FFN):
            units[n.level] += len(n.terms)
    names = Counter()
    for n in c.nodes:
        if isinstance(n, Head):
            names[n.name.rstrip("0123456789").rstrip(".")] += 1
    v0 = tc["vocab_size"]
    vocab = -(-(v0 + S.VOCAB) // 64) * 64
    res = {"drom_bytes": 1 << a.drom_log2, "ram_bytes": 1 << a.ram_log2, "store": a.store, "stats": c.stats(),
           "key_heads": sum(heads.values()), "heads_by_table": dict(names), "heads_by_sublayer": dict(sorted(heads.items())),
           "units_by_sublayer": dict(sorted(units.items())), "slots": alloc.n_slots, "hidden": hidden, "ballast_m": m,
           "chip_layers": c.n_layers(), "vocab": vocab, "base_hidden": tc["hidden_size"], "gb_estimate": gb_estimate(hidden, c.n_layers(), vocab),
           "seconds": round(time.time() - t0, 1)}
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("drom_bytes", "ram_bytes", "store", "chip_layers", "key_heads", "slots", "hidden", "gb_estimate", "seconds")}))


if __name__ == "__main__":
    main()
