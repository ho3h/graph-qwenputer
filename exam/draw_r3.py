#!/usr/bin/env python3
"""exam/AFTER.md r3's real-weights check, its draw. T8_R2=1 python3 exam/draw_r3.py"""
import json
import os
import random
import sys

os.environ["T8_R2"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "lib"), os.path.join(X210, "t8", "fw")]
import noun as N
import reflib

g = N.with_noun(json.load(open(os.path.join(HERE, "items", "nyc_t.graph.json"))))
G0 = reflib.Graph(g)
uniq = [i for i, n in enumerate(g["nodes"]) if len(G0.by_label[n["label"]]) == 1]
rng = random.Random("20261104:nyc:r3")
NEW = [("Gannet Sq", "Bracken Rd"), ("Sedge Av", "Plover St"), ("Yarrow Park", "Tansy Rd")]
conv = []
for i, (b, c) in enumerate(NEW):
    a, d = rng.sample(uniq, 2)
    la, ld = g["nodes"][a]["label"], g["nodes"][d]["label"]
    G = reflib.Graph(g)
    G.add_node(b)
    G.add_node(c)
    pairs = [(la, b), (b, c), (c, ld)]
    for x, y in pairs:
        G.link(x, "T northbound", y)
    conv.append({"key": f"nyc-r3:{i}", "graph": "nyc-t", "labels": {"a": la, "b": b, "c": c, "d": ld}, "turns": [
        {"user": f"The T line has opened, and it adds two new stations: {b} and {c}. Going northbound, its stops are {la}, then {b}, then {c}, then {ld}.", "gold": "built", "wants": ["build", [b, c], [list(p) for p in pairs]]},
        {"user": f"What's the route with the fewest stops from {la} to {c}?", "gold": G.path(la, c), "wants": None}]})
json.dump({"seed": 20261104, "conversations": conv, "plain": []}, open(os.path.join(HERE, "results", "after", "r3_draw.json"), "w"), ensure_ascii=False, indent=0)
print([(c["labels"]["a"], c["turns"][1]["gold"][:90]) for c in conv])
