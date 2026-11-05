"""Dev test, no weights: the C engine against the vendored IR evaluator (ir.evaluate, exact float64), every IR dim at every position, on a real tiny stream.

    python test_ir.py --calls 3 [--out results/test_ir.json]
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import decode as D  # noqa: E402

import numpy as np  # noqa: E402

from chipformer.q35 import ir  # noqa: E402
from chipformer.rv import core  # noqa: E402
from cexec import CExec  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--calls", type=int, default=3)
ap.add_argument("--out")
a = ap.parse_args()
L = C.Lite()
plan = json.load(open(os.path.join(HERE, "plan_accept.json")))[0]
g = json.load(open(os.path.join(C.X210, "host", "test", "tiny.graph.json")))
calls = [tuple(x) for x in plan["calls"][:a.calls]]
prompt = D.prompt_for(L, g, "Answer with the graph tools.")
m0, stream, own, ses = D.session_for(L, g, prompt, calls, between=" ", tail="Done.")
print("stream", len(stream), "prompt", len(prompt), flush=True)
core.snapshot(L.c, m0)
t0 = time.time()
ex = CExec(L.c, L.T)
print(f"engine {ex.lib_hash} compile {ex.compile_s:.1f}s terms {len(ex.A['tix'])} (before sharing {ex.cse_stats}) exprs {len(ex.A['eptr'])} pairs {len(ex.A['p_t'])} buckets {len(ex.A['buckets'])} units {len(ex.A['ua'])} n_mem {ex.p.n_mem}", flush=True)
ptoks = [C.to_stream(L.v0, i) for i in prompt]
t0 = time.time()
ex.start(ptoks)
print(f"start {time.time() - t0:.3f}s flags {ex.flags()}", flush=True)
t0 = time.time()
carry, mats = {}, []
for b in range(0, len(ptoks) + len(stream), 2048):
    pass
# the IR: the prompt from zero states then the snapshot is the HF path; the windows matter only for lags. Evaluate the same way.
init = [(n, n.init) for n in L.c.nodes if isinstance(n, ir.Head)]
for n, _ in init:
    n.init = None
mp = ir.evaluate(L.c, ptoks, check=False, carry=(cy := {}))
for n, i in init:
    n.init = i
for k in [k for k in cy if len(k) == 3 and k[1] == "S"]:     # the states go back to the snapshot; conv windows stay
    del cy[k]
mats = []
for b in range(0, len(stream), 2048):
    mats.append(ir.evaluate(L.c, stream[b:b + 2048], carry=cy))
want = np.concatenate(mats)
print(f"IR {time.time() - t0:.1f}s", flush=True)
bad, first = 0, None
t_c = 0.0
for i, t in enumerate(stream):
    ts = time.perf_counter()
    ex.step(t)
    t_c += time.perf_counter() - ts
    got = ex.x().astype(np.float64)
    w = want[i]
    dif = np.nonzero(got != w)[0]
    if len(dif):
        big = dif[np.maximum(np.abs(got[dif]), np.abs(w[dif])) > 2.0**-60]
        if len(big) and first is None:
            first = {"i": i, "tok": int(t), "dims": [(int(d), L.c.dims[d].name, float(got[d]), float(w[d])) for d in big[:8]]}
            print("FIRST", first, flush=True)
        bad += len(dif)
        if first and i > first["i"] + 3:
            break
r = {"positions": i + 1, "stream": len(stream), "dims_differing": bad, "first_big": first, "flags": ex.flags(), "c_seconds": round(t_c, 3), "per_token_us": round(1e6 * t_c / (i + 1), 1),
     "units_on_per_token": ex.p.units_on / max(ex.p.steps, 1), "reads": ex.p.reads / max(ex.p.steps, 1), "writes": ex.p.writes / max(ex.p.steps, 1), "engine": ex.lib_hash}
print(json.dumps(r), flush=True)
if a.out:
    json.dump(r, open(a.out, "w"), indent=1)
