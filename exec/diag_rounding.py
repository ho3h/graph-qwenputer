"""Do the bf16 rounding points ever change a value? A patched copy of engine.c counts it; the normal engine is untouched. The no-rounding build passes the trace check, so this says whether that is because rounding never acts on these streams.

    python diag_rounding.py --out results/diag_rounding.json
"""
import argparse
import ctypes as ct
import glob
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
src = open(os.path.join(HERE, "engine.c")).read()
old = "    uint32_t u; memcpy(&u, &f, 4);\n    u += 0x7FFF + ((u >> 16) & 1);\n    u &= 0xFFFF0000u;\n    memcpy(&f, &u, 4);\n    return f;\n"
assert old in src
new = "    uint32_t u, v; memcpy(&u, &f, 4); v = u;\n    u += 0x7FFF + ((u >> 16) & 1);\n    u &= 0xFFFF0000u;\n    chip_round_calls++; if (u != v) { chip_round_changed++; if (chip_round_first == 0.f) chip_round_first = f; }\n    memcpy(&f, &u, 4);\n    return f;\n"
patched = src.replace(old, new).replace("static inline float bf16r(float f) {", "uint64_t chip_round_calls, chip_round_changed; float chip_round_first;\nstatic inline float bf16r(float f) {", 1)
os.makedirs(os.path.join(HERE, "build"), exist_ok=True)
path = os.path.join(HERE, "build", "engine_diag.c")
open(path, "w").write(patched)
os.environ["CHIP_SRC"] = path

import common as C  # noqa: E402
import box as X  # noqa: E402
import decode as D  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core  # noqa: E402
from cexec import CExec  # noqa: E402
from speed import free_run  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--budget", type=int, default=800_000)
ap.add_argument("--max-call", type=int, default=200_000)
ap.add_argument("--seed", type=int, default=5)
ap.add_argument("--out", required=True)
a = ap.parse_args()
L = C.Lite(tokenizer=False)
T = L.T
items = []
for qf in sorted(glob.glob(os.path.join(C.X210, "data", "dev", "*", "*.questions.json"))):
    assert "heldout" not in qf
    items += [(qf, x) for x in json.load(open(qf))["questions"]]
random.Random(a.seed).shuffle(items)
calls = [(j["graph"], j.get("setup"), f, ar) for j in json.load(open(os.path.join(HERE, "plan_accept.json"))) if j["name"] in ("lim-bounds", "lim-lines") for f, ar in j["calls"]]
ex, chip, wrong, ncalls = None, 0, 0, 0
for qf, x in items:
    if chip + sum(0 for _ in ()) > a.budget and not calls:
        break
    if calls:
        g, setup, fn, ar = calls.pop(0)
    else:
        g, setup, fn, ar = json.load(open(qf.replace(".questions.json", ".graph.json"))), x.get("setup"), x["call"]["fn"], x["call"]["args"]
    try:
        m = D.parked_machine(g, T, setup)
    except Exception as e:
        if type(e).__name__ == "BootLimit":
            continue
        raise
    import copy
    snap = copy.deepcopy(m)
    ses = BR.Session(T, m)
    try:
        ses.qwen([T.TCO] + T.encode(X.template_text(fn, ar)) + [T.TCC], max_records=a.max_call)
    except RuntimeError:
        continue
    core.snapshot(L.c, snap)
    if ex is None:
        ex = CExec(L.c, L.T)
    ex.clear()
    ex.load_init()
    s, nc, n, w = free_run(ex, ses.toks)
    chip += nc
    wrong += w
    ncalls += 1
calls_n = ct.c_uint64.in_dll(ex.lib, "chip_round_calls").value
changed = ct.c_uint64.in_dll(ex.lib, "chip_round_changed").value
first = ct.c_float.in_dll(ex.lib, "chip_round_first").value
r = {"calls": ncalls, "chip_tokens": chip, "wrong": wrong, "rounding_applied": calls_n, "rounding_changed_a_value": changed, "first_value_changed": first, "flags": ex.flags()}
print(json.dumps(r), flush=True)
json.dump(r, open(a.out, "w"), indent=1)
