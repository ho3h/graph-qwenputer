#!/usr/bin/env python3
"""exam/AFTER.md r6d, r6e's draws, on the blocking map. T8_R2=1 python3 exam/draw_r6.py"""
import json
import os
import random
import re
import sys

os.environ["T8_R2"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "lib"), os.path.join(X210, "t8", "fw")]
import noun as N
import reflib

g = N.with_noun(json.load(open(os.path.join(HERE, "items", "nyc_b.graph.json"))))
G0 = reflib.Graph(g)
old = json.load(open(os.path.join(HERE, "results", "after", "journeys_draw.json")))["conversations"]
TRIPS = [(c["from"], c["to"]) for c in old]
Q = "What's the route with the fewest stops from {a} to {b}?"
W = ["{x} is closed. What's the route now?", "Flooding has shut {x}. What's the route now?", "A fire has closed {x}. What's the route now?"]
rng = random.Random("20261104:nyc:r6d")
conv = []
for i, (a, b) in enumerate(TRIPS):
    gold = reflib.Graph(g).path(a, b)
    ids = [int(x) for x in re.findall(r"@(\d+)", gold)]
    mid = [h for h in ids[1:-1] if len(G0.by_label[g["nodes"][h]["label"]]) == 1]
    best = None
    for h in sorted(mid, key=lambda h: abs(ids.index(h) - len(ids) // 2)):
        G = reflib.Graph(g)
        G.close(f"@{h}")
        p = G.path(a, b)
        if p != "NOPATH" and p != gold:
            best = (h, p)
            break
    if not best:                                                   # the line is the only way there: the machine should say so
        h = sorted(mid, key=lambda h: abs(ids.index(h) - len(ids) // 2))[0]
        G = reflib.Graph(g)
        G.close(f"@{h}")
        assert G.path(a, b) == "NOPATH", (a, b)
        best = (h, "NOPATH")
    h, p = best
    lab = g["nodes"][h]["label"]
    conv.append({"key": f"nyc-b:{i}", "graph": "nyc-b", "from": a, "to": b, "closed": h, "routes": [gold, p], "turns": [{"user": Q.format(a=a, b=b), "gold": gold, "wants": None}, {"user": W[i % 3].format(x=lab), "gold": p, "wants": None}]})
    print(a, ">", b, gold.split(":")[0], "| close", lab, p.split(":")[0], flush=True)
json.dump({"seed": 20261104, "conversations": conv, "plain": []}, open(os.path.join(HERE, "results", "after", "r6_journeys_draw.json"), "w"), ensure_ascii=False, indent=0)
a, b, x = "Bowling Green", "Pennsylvania Av", "Saratoga Av"
G = reflib.Graph(g)
r0 = G.chase(a, "4 southbound 5; 3 southbound 5")
p0 = G.path(a, b)
G.close(x)
p1 = G.path(a, b)
G.reopen(x)
p2 = G.path(a, b)
assert p0 == p2 and p0 != p1 and p1 != "NOPATH"
turns = [{"user": "Start at Bowling Green station. Ride the 4 train 5 stops southbound, then change to the 3 and ride the 3 train 5 stops southbound. One stop means the next station. At which station are you now? Answer with the station name only.", "gold": r0, "wants": None},
         {"user": Q.format(a=a, b=b), "gold": p0, "wants": None},
         {"user": f"Flooding has shut {x}. What's the route now?", "gold": p1, "wants": None},
         {"user": f"Repairs are done and {x} is back. What's the route now?", "gold": p2, "wants": None}]
json.dump({"seed": 20261104, "conversations": [{"key": "nyc-r:0", "graph": "nyc-b", "from": a, "to": b, "closed": G0.by_label[x][0], "routes": [p0, p1], "turns": turns}], "plain": []}, open(os.path.join(HERE, "results", "after", "r6_walk_draw.json"), "w"), ensure_ascii=False, indent=0)
print(r0, "|", p0, "|", p1)
