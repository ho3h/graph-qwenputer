"""Tokens per call through the executor, per plan job and per call, free-running with the reference lock on each burst; chip tokens per second with what else ran. Firmware from CHIP_FIRMWARE.

    python fw_calls.py --out results/fw_calls_fw.json
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import box as X  # noqa: E402
import decode as D  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402
from cexec import CExec  # noqa: E402
import speed as SP  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--plan", default=os.path.join(HERE, "plan_fw.json"))
ap.add_argument("--out", required=True)
a = ap.parse_args()
L = C.Lite(tokenizer=False)
T = L.T
res = {"firmware_sha256": hashlib.sha256(open(X.build_elf(), "rb").read()).hexdigest(), "load_before": SP.load(), "jobs": []}
ex = None
tot_chip = tot_s = wrong = 0
by_fn = {}
for job in json.load(open(a.plan)):
    g = job["graph"] if isinstance(job["graph"], dict) else json.load(open(D.graph_path(job["graph"])[0]))
    m = D.parked_machine(g, T, job.get("setup"))
    snap = __import__("copy").deepcopy(m)
    ses = BR.Session(T, m)
    core.snapshot(L.c, snap)
    if ex is None:
        ex = CExec(L.c, L.T)
    ex.clear()
    ex.load_init()
    ex.p.flags = 0
    rows = []
    for fn, args in job["calls"]:
        k = len(ses.toks)
        ses.qwen([T.TCO] + T.encode(X.template_text(fn, args)) + [T.TCC], max_records=4_000_000)
        s, nc, n, w = SP.free_run(ex, ses.toks[k:])
        wrong += w
        tot_chip += nc
        tot_s += s
        d = by_fn.setdefault(fn, {"calls": 0, "chip": 0})
        d["calls"] += 1
        d["chip"] += nc
        rows.append({"fn": fn, "chip": nc, "echo_and_text": n - nc, "seconds": round(s, 4), "wrong": w, "result": T.decode_bytes(ses.runs[-1]).decode("utf-8", "replace").split("\n")[2][:60]})
    res["jobs"].append({"name": job["name"], "chip": sum(r["chip"] for r in rows), "flags": ex.flags(), "calls": rows})
    print(job["name"], res["jobs"][-1]["chip"], ex.flags(), flush=True)
res.update(chip_tokens=tot_chip, seconds=round(tot_s, 2), chip_per_s=round(tot_chip / tot_s, 1), wrong=wrong, by_fn={k: {**v, "mean_chip": round(v["chip"] / v["calls"], 1)} for k, v in by_fn.items()}, engine=ex.lib_hash, load_after=SP.load())
print(json.dumps({k: res[k] for k in ("firmware_sha256", "chip_tokens", "seconds", "chip_per_s", "wrong", "by_fn")}), res["load_after"][-30:], flush=True)
json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
