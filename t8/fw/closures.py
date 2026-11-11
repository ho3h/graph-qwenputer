#!/usr/bin/env python3
"""edits2's units on writes.elf, reference machine (t8/REGISTRATION.md, step C). One fresh machine a unit, edits2's call order. Each line twice: against reflib on the same state, and against edits2's own oracle (oracle.py, reworded to SPEC 3's words). Affected and unaffected are scored as score.py scores them, from the oracle's lines. Nothing touches the executor.

    T8_WRITES=1 T8_NOUN=on python t8/fw/closures.py --workers 4
"""
import argparse
import glob
import json
import multiprocessing as mp
import os
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fwb as W  # noqa: E402

M, X = W.M, W.X
reflib = M.reflib
X210 = W.X210


def init():
    W.build()
    M.init_worker()
    W.O.set_text(M.T)
    W.noun_mode(True)
    W.patch_box(True)
    global reflib
    reflib = M.reflib


def task(job):
    path, ui = job
    items = json.load(open(path))
    found = [p for p in glob.glob(os.path.join(X210, "data", "dev", "*", items["graph"] + ".graph.json")) + glob.glob(os.path.join(X210, "d", "graphs", items["graph"] + ".graph.json")) if "heldout" not in p]
    assert len(found) == 1, (items["graph"], found)
    g = json.load(open(found[0]))
    Q, u = items["questions"], items["units"][ui]
    t = M.Tally("closures")
    c, bad = Counter(), []
    box = X.Box(g, M.T, track=True)
    G = reflib.Graph(g)
    w = reflib.reword

    def line(ids, where, fn):
        r = t.run(box, G, ids, where, fn)
        return None if r is None else r.result

    for s in u["script"]:
        if s["do"] != "check":
            got = line(s["ids"], f"{items['graph']}/{u['unit']} {s['do']} {s['node']}", s["do"])
            ok = got == w(s["want"])
            c["edit_lines"] += 1
            c["edit_right"] += ok
            if not ok:
                bad.append({"unit": u["unit"], "step": s["do"], "want": s["want"], "got": got})
            continue
        for i, want in zip(s["qs"], s["want"]):
            q = Q[i]
            got = line(q["ids"], f"{items['graph']}/{u['unit']} {s['tag']} q{i}", q["fn"])
            want, was = w(want), w(q["base"])
            if s["tag"].startswith("restored"):
                key = "restored"
                ok = got == want == was
            else:
                pre = "" if s["tag"] == "closed" else "partial_"
                key = pre + ("affected" if want != was else "unaffected")
                ok = got == want
            c[key] += 1
            c[key + "_right"] += ok
            if not ok:
                bad.append({"unit": u["unit"], "tag": s["tag"], "state": s["state"], "fn": q["fn"], "args": q["args"], "want": want, "got": got})
    return {"graph": items["graph"], "unit": u["unit"], "kind": u["kind"], "counts": dict(c), "bad": bad[:20], "checks": t.checks, "match": t.match, "toolong": t.toolong, "mism": t.mism[:20], "mism_n": len(t.mism)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default=os.path.join(HERE, "results", "writes_closures.json"))
    a = ap.parse_args()
    jobs = []
    for p in sorted(glob.glob(os.path.join(X210, "edits2", "items", "*.json"))):
        jobs += [(p, i) for i in range(len(json.load(open(p))["units"]))]
    jobs = jobs[:a.limit]
    t0, tot, rows = time.time(), Counter(), []
    W.build()
    with mp.get_context("spawn").Pool(a.workers, initializer=init) as pool:
        for n, r in enumerate(pool.imap_unordered(task, jobs), 1):
            rows.append(r)
            tot.update(r["counts"])
            for k in ("checks", "match", "toolong", "mism_n"):
                tot[k] += r[k]
            if n % 10 == 0:
                print(n, "of", len(jobs), dict(tot), round(time.time() - t0), flush=True)
                json.dump({"done": n, "of": len(jobs), "totals": dict(tot)}, open(a.out + ".partial", "w"))
    assert len(rows) == len(jobs), (len(rows), len(jobs))
    out = {"firmware": "writes.elf", "seconds": round(time.time() - t0), "units": len(rows), "totals": dict(tot), "bad": [b for r in rows for b in r["bad"]][:200], "mism": [b for r in rows for b in r["mism"]][:200]}
    json.dump(out, open(a.out, "w"), indent=0, ensure_ascii=False)
    print(json.dumps({k: out[k] for k in ("seconds", "units", "totals")}), "bad", len(out["bad"]), "first", json.dumps(out["bad"][:2] + out["mism"][:2], ensure_ascii=False)[:1500], flush=True)


if __name__ == "__main__":
    main()
