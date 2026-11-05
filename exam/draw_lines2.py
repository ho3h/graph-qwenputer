#!/usr/bin/env python3
"""exam/AFTER.md L2's draw. T8_R2=1 python3 exam/draw_lines2.py"""
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
rng = random.Random("20261108:nyc:t2")
NEW = ["Mossbank Park", "Fernhill St", "Wrenfield Av", "Larkmoor Sq", "Quaybrook Rd", "Ashgrove Pkwy", "Valemont St", "Heron Quay", "Tamarind Sq", "Linden Cross", "Marlow Heights", "Sable Point", "Orchard Reach", "Kestrel Av", "Bramble Junction", "Calder Park", "Thistle Row", "Juniper Bay", "Pinecrest Plaza", "Willow Gate", "Hollis Bend", "Rowan Terrace", "Foxglove St", "Ember Lane", "Corran Sq", "Nettle Cross", "Dovetail Av", "Saffron Hill", "Maple Quay", "Cinder Park", "Aster Row", "Birchwood Gate", "Clover Sq", "Elder Bay", "Gorse Av", "Ivy Reach", "Laurel Point", "Myrtle Cross", "Poplar Heights", "Yarrow St"]
rng.shuffle(NEW)
ann = ["A new T train starts today, with two brand-new stations, {b} and {c}. Northbound it runs {a}, {b}, {c}, {d}.", "The T line has opened, and it adds two new stations: {b} and {c}. Going northbound, its stops are {a}, then {b}, then {c}, then {d}.", "They've built {b} and {c}, two new stations, for the new T train: northbound from {a} to {b} to {c} to {d}.", "Say hello to the T, and to its new stations {b} and {c}. Its northbound route is {a}, {b}, {c}, {d}."]
can = ["The T train has been cancelled.", "They've scrapped the T line.", "The T is gone, it never worked out.", "The T train no longer exists."]
ride = "Start at {a} station. Ride the T train 2 stops northbound. One stop means the next station. At which station are you now? Answer with the station name only."
nxt = "What's the next stop after {b} on the T train going northbound? Answer with the station name only."
conv = []
base = len(g["nodes"])
for i in range(20):
    a, d = rng.sample(uniq, 2)
    b, c = NEW[2 * i], NEW[2 * i + 1]
    L = {"a": g["nodes"][a]["label"], "b": b, "c": c, "d": g["nodes"][d]["label"]}
    G = reflib.Graph(g)
    G.add_node(b)
    G.add_node(c)
    for x, y in ((L["a"], b), (b, c), (c, L["d"])):
        G.link(x, "T northbound", y)
    gride = G.chase(L["a"], "T northbound 2")
    gnext = G.neighbours(b, "T northbound")
    for x, y in ((L["a"], b), (b, c), (c, L["d"])):
        G.unlink(x, "T northbound", y)
    gafter = G.chase(L["a"], "T northbound 2")
    conv.append({"key": f"nyc-t2:{i}", "graph": "nyc-t", "labels": L, "turns": [
        {"user": ann[i % 4].format(**L), "gold": "built", "wants": ["build", [b, c], [[L["a"], b], [b, c], [c, L["d"]]]]},
        {"user": ride.format(**L), "gold": gride, "wants": None},
        {"user": nxt.format(**L), "gold": gnext, "wants": None},
        {"user": can[i % 4], "gold": "removed", "wants": ["unlinks", [[L["a"], b], [b, c], [c, L["d"]]]]},
        {"user": ride.format(**L), "gold": gafter, "wants": None}]})
json.dump({"seed": 20261108, "conversations": conv, "plain": []}, open(os.path.join(HERE, "results", "after", "lines2_draw.json"), "w"), ensure_ascii=False, indent=0)
print(json.dumps(conv[0], ensure_ascii=False)[:420], gride)
