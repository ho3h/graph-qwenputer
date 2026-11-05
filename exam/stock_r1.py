#!/usr/bin/env python3
"""exam/R1.md's stock job: the first three of the new 100 by id, each by its shared name. T8_R1=1."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import d1m
qs, _ = d1m.draw("nyc", 200)
g = json.load(open(d1m.base_of("nyc") + ".graph.json"))
new = sorted((q for q in qs if q["id"] >= 910000), key=lambda q: q["id"])[:3]
plan = [{"name": f"r1s{i}", "graph": g, "calls": [["chase", {"start": re.match(r"Start at (.+?) station\.", q["text"]).group(1), "legs": q["call"]["args"]["legs"]}]], "from": q["id"]} for i, q in enumerate(new)]
import noun, reflib
G = reflib.Graph(noun.with_noun(g))
for p, q in zip(plan, new):
    args = p["calls"][0][1]
    line = G.chase(args["start"], args["legs"])
    assert line == G.chase(q["call"]["args"]["start"], args["legs"]) and "AMBIGUOUS" not in line, (q["id"], args, line)  # the job has to go through the rule
json.dump(plan, open(sys.argv[1], "w"), ensure_ascii=False)
print([(p["from"], p["calls"]) for p in plan])
