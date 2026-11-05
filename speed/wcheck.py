"""The chip layers from the checkpoint's tensors (wexec) against the saved stock traces, by exec/check_trace.py's own compare: bf16 bits over all 3,968 dims at every position.

    CHIP_FIRMWARE=../fw/build/fw.elf python wcheck.py --trace ../exec/results/trace_fw --plan ../exec/plan_fw.json --out results/s2_fw.json [--job c024-chase] [--max-positions N]
"""
import argparse, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(X210, "exec"))
sys.path.insert(0, HERE)
import common as C
import types
_src = open(os.path.join(X210, "exec", "check_trace.py")).read().rstrip()
assert _src.endswith("\nmain()")                       # the file runs main() on import; its functions are taken without that last line, unedited
CT = types.ModuleType("check_trace")
CT.__file__ = os.path.join(X210, "exec", "check_trace.py")
exec(compile(_src[: -len("main()")], "check_trace.py", "exec"), CT.__dict__)
import numpy as np
from chipformer.rv import core
from wexec import WExec

ap = argparse.ArgumentParser()
ap.add_argument("--trace", required=True)
ap.add_argument("--plan", required=True)
ap.add_argument("--job", default=None)
ap.add_argument("--max-positions", type=int, default=None)
ap.add_argument("--mutate", default=None, help="seed:N: one checkpoint weight changed per run, on the first job")
ap.add_argument("--out", required=True)
a = ap.parse_args()
L = C.Lite()
keep_cols = L.meta["code_dims"] + [L.meta["tau_dim"], L.meta["mu_dim"]]
rows = CT.Rows(L.meta["chip_dims_offset"])
plan = {j["name"]: j for j in json.load(open(a.plan))}
names = a.job.split(",") if a.job else [n for n in plan if os.path.exists(os.path.join(a.trace, n + ".npz"))]
t0 = time.time()
ex = WExec(L.c, L.T, L.meta)
res = {"engine": ex.lib_hash, "weights_from": "merged safetensors, no IR tables", "build_s": round(ex.build_s, 1), "stats": ex.stats, "elf": C.X.build_elf(), "jobs": []}
print(json.dumps({k: res[k] for k in ("engine", "build_s", "stats")}), flush=True)
for name in names:
    tr = dict(np.load(os.path.join(a.trace, name + ".npz")))
    if a.max_positions:
        tr = CT._limit(tr, a.max_positions)
    prompt, m0, stream, own, ses = CT.job_stream(L, plan[name])
    core.snapshot(L.c, m0)
    ex.p.residue = 0; ex.p.flags = 0; ex.p.not_saturated = 0; ex.p.steps = 0; ex.p.heads_run = 0
    t1 = time.time()
    r = CT.compare(L, ex, rows, tr, prompt, stream, own, keep_cols)
    r.update(positions_with_chip_residue=ex.p.residue, not_saturated=ex.p.not_saturated, tokens_per_s=round(r["positions"] / r["run_seconds"], 1), heads_run_per_token=round(ex.p.heads_run / max(1, ex.p.steps), 1), wall_s=round(time.time() - t1, 1))
    res["jobs"].append(r)
    print(json.dumps({k: v for k, v in r.items() if k != "first"}), json.dumps(r["first"][:3])[:800], flush=True)
    json.dump(res, open(a.out, "w"), indent=1)
try:
    pr = (__import__("ctypes").c_uint64 * 16).in_dll(ex.lib, "w_prof")
    stn = (__import__("ctypes").c_int64 * 8).in_dll(ex.lib, "w_stat")
    res["prof_ticks"] = list(pr)
    res["stat"] = list(stn)
    print("prof", list(pr), list(stn), flush=True)
except ValueError:
    pass
res["totals"] = {k: sum(j[k] for j in res["jobs"]) for k in ("positions", "owned", "positions_all_bits_equal", "positions_differing", "dims_differing", "low_differing", "kept_fp32_not_exactly_bf16", "positions_with_chip_residue")}
res["seconds"] = round(time.time() - t0, 1)
json.dump(res, open(a.out, "w"), indent=1)
print(json.dumps(res["totals"]), res["seconds"])
