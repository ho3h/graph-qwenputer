#!/usr/bin/env python3
"""exam/AFTER.md V's scores, from saved rows. python3 exam/score_v.py"""
import collections
import json
import random
import re

A = "exam/results/after/"
draw = {c["key"]: c for c in json.load(open(A + "lines3_draw.json"))["conversations"]}
L = [json.loads(x) for x in open(A + "lines3/all.jsonl")]
adds = links = ride = nx = 0
rows = []
for r in L:
    w = draw[r["key"]]["turns"]
    t = r["turns"]
    calls = t[0]["calls"]
    names = {c["args"].get("name") for c in calls if c["fn"] == "add_node" and c["result"].startswith("added")}
    lk = {(c["args"].get("from"), c["args"].get("to")) for c in calls if c["fn"] == "link" and c["result"].startswith("linked")}
    a, l = set(w[0]["wants"][1]) <= names, {tuple(p) for p in w[0]["wants"][2]} <= lk
    rr = len(t) > 1 and bool(t[1]["calls"]) and t[1]["calls"][-1]["result"].split("\n")[-1] == w[1]["gold"]
    nn = len(t) > 2 and bool(t[2]["calls"]) and t[2]["calls"][-1]["result"].split("\n")[-1] == w[2]["gold"]
    adds += a
    links += l
    ride += rr
    nx += nn
    rows.append({"key": r["key"], "status": r["status"], "ran_on": r["ran_on"], "added": len(names), "linked": len(lk), "turns": len(t), "ride": rr, "next": nn, "fns": [c["fn"] for c in calls], "ride_reply": (t[1]["reply"] or "")[:60] if len(t) > 1 else ""})
g = json.load(open("data/heldout/nyc/nyc.graph.json"))
lab = [n["label"] for n in g["nodes"]]
n = len(lab)
base = collections.defaultdict(set)
for a, r_, b, w_ in g["edges"]:
    base[a].add(b)
rng = random.Random("20261108:nyc:search")
src = rng.sample(range(n), 100)


def hops(extra):
    tot, cnt = 0, 0
    for s in src:
        d = {s: 0}
        q = [s]
        for v in q:
            for y in list(base[v]) + extra.get(v, []):
                if y not in d:
                    d[y] = d[v] + 1
                    q.append(y)
        tot += sum(d.values())
        cnt += len(d)
    return tot, cnt


b0, c0 = hops({})
BASE = b0 / c0


def score(p):
    ex = {p[0]: [p[1]], p[1]: [p[0]]}
    t, c = hops(ex)
    return BASE - t / c


rr = random.Random("20261104:nyc:rec")
rand = sorted(score(rr.sample(range(n), 2)) for _ in range(300))
best = (0, None)
for _ in range(1500):
    p = rr.sample(range(n), 2)
    s_ = score(p)
    for _ in range(1):
        pass
    if s_ > best[0]:
        best = (s_, p)
R = [json.loads(x) for x in open(A + "recommend/all.jsonl")]
rec = []
for r in R:
    t = r["turns"][0]
    rep = t["reply"] or ""
    found = sorted({m for m in set(lab) if re.search(r"(?<![\w-])" + re.escape(m) + r"(?![\w-])", rep)}, key=lambda m: rep.find(m))
    two = found[:2]
    # A name shared by several stops is scored at its best-connected reading: the first stop with the name.
    s_ = score([lab.index(two[0]), lab.index(two[1])]) if len(two) == 2 else None
    rec.append({"key": r["key"], "called": [c["fn"] for c in t["calls"]], "stations": two, "named": len(found), "saving": None if s_ is None else round(s_, 3), "reply": rep[:200], "ran_on": r["ran_on"], "status": r["status"]})
out = {"long_line": {"n": len(L), "all_stops_added": adds, "all_links": links, "ride_right": ride, "next_right": nx, "status": dict(collections.Counter(r["status"] for r in L)), "real_weights": sum(str(r["ran_on"]).startswith("stock") for r in L), "positions": sum(r.get("verified_positions") or 0 for r in L), "mismatches": sum(bool(r.get("verify_mismatch")) for r in L), "rows": rows},
       "recommend": {"mean_hops": BASE, "random_median": rand[150], "random_p95": rand[285], "best_of_1500_random": [round(best[0], 3), [lab[x] for x in best[1]]], "rows": rec, "named_two": sum(x["saving"] is not None for x in rec), "called": sum(bool(x["called"]) for x in rec), "positions": sum(r.get("verified_positions") or 0 for r in R), "mismatches": sum(bool(r.get("verify_mismatch")) for r in R)}}
json.dump(out, open(A + "v_score.json", "w"), indent=0, ensure_ascii=False)
print({k: v for k, v in out["long_line"].items() if k != "rows"})
for x in rows:
    print(x)
print({k: v for k, v in out["recommend"].items() if k != "rows"})
for x in rec:
    print(x)
