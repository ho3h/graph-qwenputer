"""S12(a): wexec's negative control. One nonzero weight doubled at a time; the check must see it wherever a stream reads it.

    CHIP_FIRMWARE=../fw/build/fw.elf python wneg.py --n 30 --positions 12000 --out results/s12_negative.json
"""
import argparse, json, os, random, sys, time, types
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(X210, "exec"))
sys.path.insert(0, HERE)
import common as C
_src = open(os.path.join(X210, "exec", "check_trace.py")).read().rstrip()
assert _src.endswith("\nmain()")
CT = types.ModuleType("check_trace")
CT.__file__ = os.path.join(X210, "exec", "check_trace.py")
exec(compile(_src[: -len("main()")], "check_trace.py", "exec"), CT.__dict__)
import numpy as np
from chipformer.rv import core
from wexec import WExec
ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=30)
ap.add_argument("--positions", type=int, default=12000)
ap.add_argument("--seed", type=int, default=20261102)
ap.add_argument("--out", required=True)
a = ap.parse_args()
L = C.Lite()
keep_cols = L.meta["code_dims"] + [L.meta["tau_dim"], L.meta["mu_dim"]]
rows = CT.Rows(L.meta["chip_dims_offset"])
plan = {j["name"]: j for j in json.load(open(os.path.join(X210, "exec", "plan_fw.json")))}
name = "tiny-ten"
tr = CT._limit(dict(np.load(os.path.join(X210, "exec", "results", "trace_fw", name + ".npz"))), a.positions)
prompt, m0, stream, own, ses = CT.job_stream(L, plan[name])
core.snapshot(L.c, m0)
ex = WExec(L.c, L.T, L.meta)
rng = random.Random(a.seed)
ARR = ("q_w", "z_w", "a_w", "b_w", "g_w", "u_w", "d_w", "o_w")
sizes = [(l, k, len(ex.tables[l][k])) for l in range(len(ex.tables)) for k in ARR if len(ex.tables[l][k])]
tot = sum(s for _, _, s in sizes)
base = CT.compare(L, ex, rows, tr, prompt, stream, own, keep_cols)
res = {"engine": ex.lib_hash, "stream": name, "positions": a.positions, "baseline_differing": base["positions_differing"], "cases": [], "weights_total": tot}
print("baseline", base["positions_differing"], flush=True)
for i in range(a.n):
    u = rng.randrange(tot)
    for l, k, s in sizes:
        if u < s:
            break
        u -= s
    arr = ex.tables[l][k]
    old = float(arr[u])
    arr[u] = old * 2.0
    r = CT.compare(L, ex, rows, tr, prompt, stream, own, keep_cols, limit_first=1)
    arr[u] = old
    res["cases"].append({"layer": l, "array": k, "index": u, "old": old, "caught": r["positions_differing"] > 0, "first": r["first"][0]["i"] if r["first"] else None, "flags": r["flags"]})
    print(json.dumps(res["cases"][-1]), flush=True)
    json.dump(res, open(a.out, "w"), indent=1)
res["caught"] = sum(c["caught"] for c in res["cases"])
res["tried"] = a.n
again = CT.compare(L, ex, rows, tr, prompt, stream, own, keep_cols)
res["after_restore_differing"] = again["positions_differing"]
json.dump(res, open(a.out, "w"), indent=1)
print("caught", res["caught"], "of", a.n, "after restore", again["positions_differing"])
