#!/usr/bin/env python3
"""Candidates for New York's stock window, per exam/REGISTRATION.md. Each candidate is run alone on a fresh executor with coverage; items new against the baseline are saved. One process a shard, through tokrun, T8_WRITES=1; `choose` then picks greedily, new items per position, with the required close job and one path first.

    python t8/fw/tokrun.py ../exam/pick_nyc.py run --shard 0/6 --baseline B --out DIR
    python exam/pick_nyc.py choose --dir DIR --budget N --out plan.json
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)


def run():
    sys.path.insert(0, HERE)
    import mach as M
    import noun as N
    import items as I
    import numpy as np
    a = sys.argv
    k, n = map(int, a[a.index("--shard") + 1].split("/"))
    base = json.load(open(a[a.index("--baseline") + 1]))
    out = a[a.index("--out") + 1]
    known = {x: set(base[x]) for x in ("gates", "channels", "reads", "writes")}
    it = json.load(open(os.path.join(HERE, "items", "nyc.json")))
    gp, _ = I.load("nyc")
    g = N.with_noun(json.load(open(gp)))
    Q = it["questions"]
    T = None
    pair = M.Pair(g, it["prompt_ids"], it["between_ids"])
    T = pair.T
    cands = []
    for i, q in enumerate(Q):
        cands.append({"kind": "chase", "name": f"base{i}", "calls": [["chase", q["args"]]], "ids": [q["ids"]]})
    for i, p in enumerate(it["pairs"]):
        cands.append({"kind": "path", "name": f"path{i}", "calls": [["path", p["args"]]], "ids": [p["ids"]]})
    for ln in open(os.path.join(HERE, "results", "nyc_d1m", "all.jsonl")):
        r = json.loads(ln)
        c = r["calls"][0]
        cands.append({"kind": "chase", "name": f"d1m{r['id']}", "calls": [["chase", c["args"]]], "ids": [c["ids"]]})
    # the required job: one closure, an affected answer, an unaffected answer, reopen, the answer again
    for u in it["units"]:
        moved = [i for i, w in enumerate(u["closed_want"]) if w != Q[i]["base"]]
        same = [i for i, w in enumerate(u["closed_want"]) if w == Q[i]["base"]]
        if moved and same:
            m, s = moved[0], same[0]
            cands.append({"kind": "edit", "name": u["unit"], "calls": [["close", {"node": f"@{u['node']}"}], ["chase", Q[m]["args"]], ["chase", Q[s]["args"]], ["reopen", {"node": f"@{u['node']}"}], ["chase", Q[m]["args"]]],
                          "ids": [u["close_ids"], Q[m]["ids"], Q[s]["ids"], u["reopen_ids"], Q[m]["ids"]]})
    with open(os.path.join(out, f"shard{k}.jsonl"), "w") as f:
        for j, c in enumerate(cands):
            if j % n != k:
                continue
            pair.fresh()
            tok = 0
            for ids in c["ids"]:
                r = pair.call(ids)
                tok += r["chip"] + r["echo"] + len(ids) + 2
            new = []
            cov = pair.cov
            for kind, arr in (("gates", cov.gate), ("channels", cov.chan), ("reads", cov.read), ("writes", cov.write)):
                new += [[kind, int(i)] for i in np.nonzero(arr)[0] if int(i) not in known[kind]]
            f.write(json.dumps({"kind": c["kind"], "name": c["name"], "calls": c["calls"], "positions": tok, "new": new}, ensure_ascii=False) + "\n")
            f.flush()
    print("shard done", k, flush=True)


def choose():
    a = sys.argv
    C = []
    for p in glob.glob(os.path.join(a[a.index("--dir") + 1], "shard*.jsonl")):
        C += [json.loads(l) for l in open(p)]
    budget = int(a[a.index("--budget") + 1])
    for c in C:
        c["new"] = {tuple(x) for x in c["new"]}
    every = set().union(*(c["new"] for c in C))
    left, chosen, used = set(every), [], 0

    def take(c):
        nonlocal used, left
        chosen.append({"name": c["name"], "kind": c["kind"], "calls": c["calls"], "positions": c["positions"], "adds": len(c["new"] & left)})
        used += c["positions"]
        left = left - c["new"]
    for kind in ("edit", "path"):
        take(max((c for c in C if c["kind"] == kind), key=lambda y: len(y["new"] & left) / y["positions"]))
    while left:
        fit = [c for c in C if used + c["positions"] <= budget and c["new"] & left]
        if not fit:
            break
        take(max(fit, key=lambda y: len(y["new"] & left) / y["positions"]))
    g = json.load(open(os.path.join(X210, "data", "heldout", "nyc", "nyc.graph.json")))
    plan = [{"name": f"ny{i:02d}", "graph": g, "calls": x["calls"], "from": x["name"]} for i, x in enumerate(chosen)]
    json.dump(plan, open(a[a.index("--out") + 1], "w"), ensure_ascii=False)
    by = lambda s: {k: sum(1 for x, _ in s if x == k) for k in ("gates", "channels", "reads", "writes")}
    print(json.dumps({"candidates": len(C), "new_in_all": by(every), "chosen": len(chosen), "positions": used, "left": by(left), "picks": [(x["name"], x["adds"], x["positions"]) for x in chosen]}), flush=True)


if sys.argv[1] == "run":
    run()
else:
    choose()
