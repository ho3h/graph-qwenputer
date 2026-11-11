#!/usr/bin/env python3
"""exam/AFTER.md V1's draw. T8_R2=1 python3 exam/draw_lines3.py"""
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
rng = random.Random("20261104:nyc:t3")
A = ["Ember", "Tolland", "Corbin", "Sable", "Hawthorn", "Ivory", "Juniper", "Kestrel", "Lumen", "Merrow", "Northam", "Orchard", "Pewter", "Rowan", "Sorrel", "Thistle"]
B = ["Park", "St", "Sq", "Av", "Rd"]
NEW = [f"{a} {b}" for a in A for b in B]
rng.shuffle(NEW)
ann = ["A new T train starts today, with five brand-new stations: {new}. Northbound it runs {a}, {all}, {d}.", "The T line has opened, and it adds five new stations: {new}. Going northbound, its stops are {a}, then {all}, then {d}."]
conv = []
for i in range(10):
    a, d = rng.sample(uniq, 2)
    la, ld = g["nodes"][a]["label"], g["nodes"][d]["label"]
    ns = NEW[5 * i:5 * i + 5]
    seq = [la] + ns + [ld]
    G = reflib.Graph(g)
    for n in ns:
        G.add_node(n)
    pairs = list(zip(seq, seq[1:]))
    for x, y in pairs:
        G.link(x, "T northbound", y)
    conv.append({"key": f"nyc-t3:{i}", "graph": "nyc-t", "labels": {"a": la, "d": ld, "new": ns}, "turns": [
        {"user": ann[i % 2].format(a=la, d=ld, new=", ".join(ns), all=(", " if i % 2 == 0 else ", then ").join(ns)), "gold": "built", "wants": ["build", ns, [list(p) for p in pairs]]},
        {"user": f"Start at {la} station. Ride the T train 3 stops northbound. One stop means the next station. At which station are you now? Answer with the station name only.", "gold": G.chase(la, "T northbound 3"), "wants": None},
        {"user": f"What's the next stop after {ns[0]} on the T train going northbound? Answer with the station name only.", "gold": G.neighbours(ns[0], "T northbound"), "wants": None}]})
json.dump({"seed": 20261104, "conversations": conv, "plain": []}, open(os.path.join(HERE, "results", "after", "lines3_draw.json"), "w"), ensure_ascii=False, indent=0)
print(json.dumps(conv[0], ensure_ascii=False)[:500])
