#!/usr/bin/env python3
"""exam/AFTER.md S2, from saved rows: the machine's line against gold, by source; each firmware line against reflib; Qwen's reply. python3 exam/s2_score.py MAP"""
import collections
import json
import os
import re
import sys

os.environ.update(T8_R1="1", T8_R2="1")
HERE = os.path.dirname(os.path.abspath(__file__))
X = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X, "lib"), os.path.join(X, "t8", "fw")]
import noun  # noqa: E402
import reflib  # noqa: E402

m = sys.argv[1]
A = os.path.join(HERE, "results", "after")
g = noun.with_noun(json.load(open(os.path.join(HERE, "items", "sealed", m + "_b.graph.json"))))
draw = {c["key"]: c for c in json.load(open(os.path.join(A, f"s2_{m}_draw.json")))["conversations"]}
rows = [json.loads(x) for x in open(os.path.join(A, f"s2_{m}", "all.jsonl"))]
C = collections.Counter()
by = collections.defaultdict(collections.Counter)
bad = collections.defaultdict(list)
for r in rows:
    d = draw[r["key"]]
    gold = d["turns"][0]["gold"]
    src = d["source"]
    t = r["turns"][0] if r["turns"] else {"calls": [], "reply": ""}
    calls = t["calls"]
    G = reflib.Graph(g)
    for c in calls:
        C["calls"] += 1
        C["firmware_equal_reflib"] += G.call(c["fn"], c["args"]) == c["result"]
    C["state_reference_equal"] += all(s["reference_equal"] for s in r["states"])
    last = (calls[-1]["result"] or "").split("\n")[-1] if calls else None
    kind = "right" if last == gold else "no_call" if last is None else "ambiguous" if last.startswith("AMBIGUOUS") else "none" if last.startswith("NONE") else "norelation" if last.startswith("NORELATION") else "wrong"
    by[src][kind] += 1
    by["all"][kind] += 1
    C["unasked_closed"] += any(c["args"].get("closed") or c["args"].get("reopened") or c["fn"] in ("close", "reopen") for c in calls)
    C["more_than_one_call"] += len(calls) > 1
    name = gold.split(" ", 1)[1] if gold.startswith("@") else None
    rep = t.get("reply") or ""
    if name:
        C["gold_is_station"] += 1
        C["reply_names_gold"] += name in rep
        C["reply_exact"] += rep.strip() == name
    if kind != "right" and len(bad[kind]) < 4:
        bad[kind].append([r["key"], d["turns"][0]["user"][:110], [c["args"] for c in calls][:2], last and last[:80], gold[:60], rep[:50]])
    C["seconds"] += r["seconds"]
out = {"map": m, "rows": len(rows), "by": {k: dict(v) for k, v in by.items()}, "counts": dict(C), "examples": dict(bad), "status": dict(collections.Counter(r["status"] for r in rows)), "ran_on": dict(collections.Counter(r["ran_on"] for r in rows))}
json.dump(out, open(os.path.join(A, f"s2_{m}_score.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: out[k] for k in ("map", "rows", "by", "counts", "status", "ran_on")}))
for k, v in bad.items():
    for e in v:
        print(k, e)
