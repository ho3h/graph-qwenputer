#!/usr/bin/env python3
"""exam/AFTER.md D: r1's E1 conversations and D1r's calls, each on a fresh executor with coverage; greedy by never-compared items per position. T8_R1=1.

    python t8/fw/tokrun.py ../exam/pick_after.py run --shard 0/6 --out DIR
    python3 exam/pick_after.py choose --dir DIR --budget N --out plan.json
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
R = os.path.join(HERE, "results")
K = ("gates", "channels", "reads", "writes")


def run():
    sys.path.insert(0, HERE)
    import mach as M
    import noun as N
    import items as I
    import numpy as np
    a = sys.argv
    k, n = map(int, a[a.index("--shard") + 1].split("/"))
    out = a[a.index("--out") + 1]
    base = json.load(open(os.path.join(X210, "t8", "fw", "results", "cov_baseline_w.json")))
    known = {x: set(base[x]) for x in K}
    ids = lambda v: {x[0] if isinstance(x, list) else x for x in v}
    for f in glob.glob(os.path.join(X210, "t8", "fw", "results", "cov", "nyc_window", "ny*.json")):
        j = json.load(open(f))
        for x in K:
            known[x] |= ids(j[x])
    it = json.load(open(os.path.join(HERE, "items", "nyc.json")))
    gp, _ = I.load("nyc")
    pair = M.Pair(N.with_noun(json.load(open(gp))), it["prompt_ids"], it["between_ids"])
    T = pair.T
    cands = []
    for ln in open(os.path.join(R, "nyc_r1_edit", "all.jsonl")):
        r = json.loads(ln)
        cs = [c for t in r["turns"] for c in t["calls"]]
        cands.append(("edit", r["key"], cs))
    for ln in open(os.path.join(R, "nyc_r1_d1r", "all.jsonl")):
        r = json.loads(ln)
        cands.append(("reply", f"d1r{r['id']}", r["calls"]))
    with open(os.path.join(out, f"shard{k}.jsonl"), "w") as f:
        for j, (kind, name, cs) in enumerate(cands):
            if j % n != k or not cs:
                continue
            pair.fresh()
            tok = 0
            for c in cs:
                e = T.encode(c["text"])
                r = pair.call(e)
                tok += r["chip"] + r["echo"] + len(e) + 2
            new = []
            for x, arr in zip(K, (pair.cov.gate, pair.cov.chan, pair.cov.read, pair.cov.write)):
                new += [[x, int(i)] for i in np.nonzero(arr)[0] if int(i) not in known[x]]
            f.write(json.dumps({"kind": kind, "name": name, "calls": [[c["fn"], c["args"]] for c in cs], "positions": tok, "new": new, "same": bool(r["same"])}, ensure_ascii=False) + "\n")
            f.flush()
    print("shard done", k, flush=True)


def choose():
    a = sys.argv
    C = []
    for p in glob.glob(os.path.join(a[a.index("--dir") + 1], "shard*.jsonl")):
        C += [json.loads(x) for x in open(p)]
    budget = int(a[a.index("--budget") + 1])
    for c in C:
        c["new"] = {tuple(x) for x in c["new"]}
    every = set().union(*(c["new"] for c in C))
    left, chosen, used = set(every), [], 0
    while left:
        fit = [c for c in C if used + c["positions"] <= budget and c["new"] & left]
        if not fit:
            break
        c = max(fit, key=lambda y: len(y["new"] & left) / y["positions"])
        chosen.append(c)
        used += c["positions"]
        left -= c["new"]
    g = json.load(open(os.path.join(X210, "data", "heldout", "nyc", "nyc.graph.json")))
    json.dump([{"name": f"af{i:02d}", "graph": g, "calls": c["calls"], "from": c["name"]} for i, c in enumerate(chosen)], open(a[a.index("--out") + 1], "w"), ensure_ascii=False)
    by = lambda s: {k: sum(1 for x, _ in s if x == k) for k in K}
    print(json.dumps({"candidates": len(C), "new_in_all": by(every), "chosen": len(chosen), "positions": used, "left": by(left), "kinds": [c["kind"] for c in chosen]}))


if sys.argv[1] == "run":
    run()
else:
    choose()
