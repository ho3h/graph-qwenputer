"""Chip tokens per second of the C engine on real teacher-forced streams, single process or several at once. Only the engine and its Python driver are timed; the stream is built on the reference first. What else ran is saved with the figure.

    python speed.py --job c024-chase --rep 3 --out results/speed.json
    python speed.py --job tiny-ten --calls 8 --procs 6 --out results/speed_6.json

Three figures per run:
  teacher    chip_run over the whole stream: every position's tokens given, nothing returned to Python
  free       chip tokens via chip_burst (the circuit picks each next token) with text tokens stepped from Python, the lock checked on each burst: what a machine-only run or RvChat's chip side costs
  overheads  core.snapshot, prompt through the circuit, state save/restore
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import decode as D  # noqa: E402

import numpy as np  # noqa: E402

from chipformer.rv import core  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402
from cexec import CExec  # noqa: E402


def load():
    return subprocess.run("ps -axo pcpu,comm | sort -rn | head -8 | cut -c1-90; sysctl -n vm.loadavg", shell=True, capture_output=True, text=True).stdout


def free_run(ex, stream):
    """The stream decoded by the circuit: chip bursts in C, text tokens one at a time. Returns (seconds, chip tokens, positions, wrong)."""
    wrong = 0
    n_chip = 0
    i = 0
    n = len(stream)
    t0 = time.perf_counter()
    while i < n:
        t = stream[i]
        if t < S.VOCAB:
            end = i
            while end < n and stream[end] < S.VOCAB:      # the reference knows the burst's length; the circuit must reach it itself
                end += 1
            status, nxt, k, rec = ex.burst(t, end - i, record=True)
            n_chip += k
            want = stream[i + 1: i + k + 1]
            got = rec[:k].tolist()
            if got[: len(want)] != want:
                wrong += 1
            i += k
        else:
            ex.step(t)
            i += 1
    return time.perf_counter() - t0, n_chip, n, wrong


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", default="tiny-ten")
    ap.add_argument("--calls", type=int, default=0)
    ap.add_argument("--rep", type=int, default=3)
    ap.add_argument("--procs", type=int, default=1)
    ap.add_argument("--go-at", type=float, default=0, help="internal: all processes start timing together")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.procs > 1:
        go = time.time() + 75
        ps = []
        for k in range(a.procs):
            out = f"{a.out}.{k}.json"
            ps.append((subprocess.Popen([sys.executable, __file__, "--job", a.job, "--calls", str(a.calls), "--rep", str(a.rep), "--go-at", str(go), "--out", out]), out))
        for p, _ in ps:
            p.wait(timeout=1800)
        rs = [json.load(open(o)) for _, o in ps]
        for _, o in ps:
            os.remove(o)
        res = {"procs": a.procs, "job": a.job, "per_proc_free_chip_per_s_median": [r["free_chip_per_s_median"] for r in rs], "per_proc_teacher_positions_per_s_median": [r["teacher_positions_per_s_median"] for r in rs],
               "aggregate_free_chip_per_s": round(sum(r["free_chip_per_s_median"] for r in rs), 1), "aggregate_teacher_positions_per_s": round(sum(r["teacher_positions_per_s_median"] for r in rs), 1), "load_before": rs[0]["load_before"], "load_after": rs[0]["load_after"]}
        print(json.dumps({k: v for k, v in res.items() if not k.startswith("load")}), flush=True)
        print(res["load_after"], flush=True)
        json.dump(res, open(a.out, "w"), indent=1)
        return
    L = C.Lite()
    job = next(j for j in json.load(open(os.path.join(HERE, "plan_accept.json"))) if j["name"] == a.job)
    g = job["graph"] if isinstance(job["graph"], dict) else json.load(open(D.graph_path(job["graph"])[0]))
    calls = [tuple(x) for x in job["calls"]]
    if a.calls:
        calls = calls[:a.calls]
    prompt = D.prompt_for(L, g, "Answer with the graph tools.")
    m0, stream, own, ses = D.session_for(L, g, prompt, calls, job.get("setup"), between=" ", tail="Done.")
    t0 = time.perf_counter()
    core.snapshot(L.c, m0)
    snap_cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    core.snapshot(L.c, m0)
    snap_warm = time.perf_counter() - t0
    ex = CExec(L.c, L.T)
    ptoks = [C.to_stream(L.v0, i) for i in prompt]
    arr = np.array(stream, np.int32)
    chip = int((arr < S.VOCAB).sum())
    t0 = time.perf_counter()
    ex.start(ptoks)
    start_cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    ex.start(ptoks)
    start_warm = time.perf_counter() - t0
    st0 = ex.save()
    t0 = time.perf_counter()
    ex.restore(st0)
    restore = time.perf_counter() - t0
    ex.run(arr, keep=False)             # features filled, caches warm
    res = {"job": a.job, "calls": len(calls), "positions": len(arr), "chip_tokens": chip, "text_tokens": len(arr) - chip, "prompt_tokens": len(prompt), "engine": ex.lib_hash, "teacher_s": [], "free_s": [], "load_before": load(), "free_wrong": 0,
           "overheads_s": {"snapshot_cold": round(snap_cold, 4), "snapshot_warm": round(snap_warm, 4), "start_prompt_cold": round(start_cold, 4), "start_prompt_warm": round(start_warm, 4), "restore_state": round(restore, 5)}}
    if a.go_at:
        time.sleep(max(0, a.go_at - time.time()))
    for r in range(a.rep):
        ex.restore(st0)
        ex.p.steps = ex.p.units_on = ex.p.reads = ex.p.writes = 0
        t0 = time.perf_counter()
        ex.run(arr, keep=False)
        res["teacher_s"].append(round(time.perf_counter() - t0, 4))
        ex.restore(st0)
        s, nc, n, wrong = free_run(ex, stream)
        res["free_s"].append(round(s, 4))
        res["free_wrong"] += wrong
    med = lambda x: sorted(x)[len(x) // 2]
    res["units_on_per_token"] = round(ex.p.units_on / max(ex.p.steps, 1), 1)
    res["teacher_positions_per_s_median"] = round(len(arr) / med(res["teacher_s"]), 1)
    res["teacher_positions_per_s_best"] = round(len(arr) / min(res["teacher_s"]), 1)
    res["free_chip_per_s_median"] = round(chip / med(res["free_s"]), 1)
    res["free_chip_per_s_best"] = round(chip / min(res["free_s"]), 1)
    res["hours_for_66_5M_chip_at_median"] = round(66.5e6 / res["free_chip_per_s_median"] / 3600, 2)
    res["load_after"] = load()
    res["flags"] = ex.flags()
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("load")}), flush=True)
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
