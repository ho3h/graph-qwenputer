#!/usr/bin/env python3
"""exam/AFTER.md T1, from the saved rows: each firmware answer against reflib, and the calls per turn for reading. python3 exam/t1_score.py"""
import json
import os
import sys

os.environ.update(T8_R1="1", T8_R2="1")
X = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(X, "lib"), os.path.join(X, "t8", "fw")]
import noun  # noqa: E402
import reflib  # noqa: E402

R = os.path.join(X, "exam", "results", "after", "t1")
GRAPHS = {"packages": os.path.join(R, "t1-packages.graph.json"), "flights": os.path.join(R, "t1-flights.graph.json"), "team": os.path.join(X, "release", "examples", "team.graph.json"), "nyc": os.path.join(X, "exam", "items", "nyc_b.graph.json")}
out = {"conversations": {}}
for name, path in GRAPHS.items():
    g = json.load(open(path, encoding="utf-8"))
    G = reflib.Graph(noun.with_noun(g))
    r = json.loads(open(os.path.join(R, "rows", name + ".jsonl")).readline())
    calls = [c for t in r["turns"] for c in t["calls"]]
    eq = sum(G.call(c["fn"], c["args"]) == c["result"] for c in calls)
    out["conversations"][name] = {"status": r["status"], "ran_on": r["ran_on"], "turns": len(r["turns"]), "calls": len(calls), "equal_reflib": eq, "chip_tokens": r["chip_tokens"], "seconds": r["seconds"], "by_turn": [[t["user"], [[c["fn"], c["args"]] for c in t["calls"]], t.get("reply", "").strip()] for t in r["turns"]]}
c = out["conversations"].values()
out["turns"], out["calls"], out["equal_reflib"] = sum(x["turns"] for x in c), sum(x["calls"] for x in c), sum(x["equal_reflib"] for x in c)
json.dump(out, open(os.path.join(R, "score.json"), "w"), indent=1, ensure_ascii=False)
print(out["turns"], out["calls"], out["equal_reflib"], {k: (v["status"], v["chip_tokens"], round(v["seconds"])) for k, v in out["conversations"].items()})
