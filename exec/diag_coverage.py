"""What the acceptance streams exercise: which FFN gates ever went positive and which value heads were ever read or written, on the plan's streams, using a patched copy of engine.c (the normal engine is untouched). A residual check says nothing about a gate that never fires.

    python diag_coverage.py --out results/diag_coverage.json
"""
import argparse
import collections
import ctypes as ct
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
src = open(os.path.join(HERE, "engine.c")).read()
a1 = "            int32_t g = g0 + i + k, u1 = gstart[g + 1];\n"
a2 = "                p->reads++;\n"
a3 = "                    p->writes++;\n"
assert a1 in src and a2 in src and a3 in src
patched = (src.replace(a1, a1 + "            chip_gate_on[g] = 1;\n").replace(a2, a2 + "                chip_read_on[vh] = 1;\n").replace(a3, a3 + "                    chip_write_on[vh] = 1;\n")
           .replace("static inline float bf16r(float f) {", "unsigned char chip_gate_on[65536], chip_read_on[1024], chip_write_on[1024];\nstatic inline float bf16r(float f) {", 1))
path = os.path.join(HERE, "build", "engine_cov.c")
os.makedirs(os.path.dirname(path), exist_ok=True)
open(path, "w").write(patched)
os.environ["CHIP_SRC"] = path

import common as C  # noqa: E402
import decode as D  # noqa: E402

import numpy as np  # noqa: E402

from chipformer.q35.ir import FFN  # noqa: E402
from chipformer.rv import core  # noqa: E402
from cexec import CExec  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--plan", default=os.path.join(HERE, "plan_accept.json"))
ap.add_argument("--trace", default=os.path.join(HERE, "results", "trace"))
ap.add_argument("--out", required=True)
a = ap.parse_args()
L = C.Lite()
plan = json.load(open(a.plan))
ex = None
done = []
for job in plan:
    if not os.path.exists(os.path.join(a.trace, job["name"] + ".npz")):
        continue
    n = json.loads(str(np.load(os.path.join(a.trace, job["name"] + ".npz"))["meta"]))["positions"]
    g = job["graph"] if isinstance(job["graph"], dict) else json.load(open(D.graph_path(job["graph"])[0]))
    prompt = D.prompt_for(L, g, "Answer with the graph tools.")
    m0, stream, own, ses = D.session_for(L, g, prompt, [tuple(x) for x in job["calls"]], job.get("setup"), between=" ", tail="Done.")
    core.snapshot(L.c, m0)
    if ex is None:
        ex = CExec(L.c, L.T)
    ex.start([C.to_stream(L.v0, i) for i in prompt])
    ex.run(stream[:n], keep=False)
    done.append({"job": job["name"], "positions": n})
A = ex.A
ng = len(A["gstart"]) - 1
on = np.ctypeslib.as_array((ct.c_ubyte * 65536).in_dll(ex.lib, "chip_gate_on"))[:ng].astype(bool)
units_per_group = np.diff(A["gstart"])
# per output dim: did any of its gates fire (names say what part of the core it is)
names = [d.name for d in L.c.dims]
dim_units, dim_on = collections.Counter(), collections.Counter()
for g_ in range(ng):
    for u in range(A["gstart"][g_], A["gstart"][g_ + 1]):
        d = int(A["uout"][u])
        pre = re.split(r"[.\[>=+]", names[d])[0]
        dim_units[pre] += 1
        dim_on[pre] += int(on[g_])
nv = len(A["vh_S"])
r_on = np.ctypeslib.as_array((ct.c_ubyte * 1024).in_dll(ex.lib, "chip_read_on"))[:nv].astype(bool)
w_on = np.ctypeslib.as_array((ct.c_ubyte * 1024).in_dll(ex.lib, "chip_write_on"))[:nv].astype(bool)
vh_names = [n.name for n in ex.heads for _ in n.vheads()]
res = {"streams": done, "gates_total": int(ng), "gates_ever_on": int(on.sum()), "units_total": int(units_per_group.sum()), "units_ever_on": int(units_per_group[on].sum()),
       "value_heads": nv, "ever_read": int(r_on.sum()), "ever_written": int(w_on.sum()), "heads_never_read": sorted({vh_names[i] for i in range(nv) if not r_on[i]}), "heads_never_written_that_have_keys": sorted({vh_names[i] for i in range(nv) if not w_on[i] and A["vh_v"][i + 1] > A["vh_v"][i]}),
       "by_part": {k: {"units": dim_units[k], "on": dim_on[k], "share_on": round(dim_on[k] / dim_units[k], 3)} for k in sorted(dim_units, key=lambda x: dim_on[x] / dim_units[x])}}
print(json.dumps(res)[:2500], flush=True)
json.dump(res, open(a.out, "w"), indent=1)
