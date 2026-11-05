#!/usr/bin/env python3
"""exam/AFTER.md L: the map with an empty T line, and the draw. python3 exam/draw_lines.py"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "lib"), os.path.join(X210, "t8", "fw")]
import noun as N
import reflib

raw = json.load(open(os.path.join(X210, "data", "heldout", "nyc", "nyc.graph.json")))
raw2 = json.loads(json.dumps(raw))
raw2["name"] = "nyc-t"
raw2["relations"] = raw["relations"] + ["T northbound", "T southbound"]
raw2["splice"] = raw["splice"] + ["T northbound", "T southbound"]
json.dump(raw2, open(os.path.join(HERE, "items", "nyc_t.graph.json"), "w"), ensure_ascii=False)
g = N.with_noun(raw2)
G0 = reflib.Graph(g)
uniq = [i for i, n in enumerate(g["nodes"]) if len(G0.by_label[n["label"]]) == 1]
rng = random.Random("20261108:nyc:t")
ann = ["A new T train starts today. Northbound it runs {a}, {b}, {c}, {d}.", "The T line has opened. Going northbound, its stops are {a}, then {b}, then {c}, then {d}.", "They've launched the T train: northbound from {a} to {b} to {c} to {d}.", "Say hello to the T. Its northbound route is {a}, {b}, {c}, {d}."]
can = ["The T train has been cancelled.", "They've scrapped the T line.", "The T is gone, it never worked out.", "The T train no longer exists."]
ride = "Start at {a} station. Ride the T train 2 stops northbound. One stop means the next station. At which station are you now? Answer with the station name only."
nxt = "What's the next stop after {b} on the T train going northbound? Answer with the station name only."
conv = []
for i in range(20):
    a, b, c, d = rng.sample(uniq, 4)
    L = {k: g["nodes"][v]["label"] for k, v in zip("abcd", (a, b, c, d))}
    G = reflib.Graph(g)
    for x, y in ((a, b), (b, c), (c, d)):
        G.link(f"@{x}", "T northbound", f"@{y}")
    gride = G.chase(f"@{a}", "T northbound 2")
    gnext = G.neighbours(f"@{b}", "T northbound")
    for x, y in ((a, b), (b, c), (c, d)):
        G.unlink(f"@{x}", "T northbound", f"@{y}")
    gafter = G.chase(f"@{a}", "T northbound 2")
    conv.append({"key": f"nyc-t:{i}", "graph": "nyc-t", "stops": [a, b, c, d], "labels": L, "turns": [
        {"user": ann[i % 4].format(**L), "gold": "built", "wants": ["links", [[a, b], [b, c], [c, d]]]},
        {"user": ride.format(**L), "gold": gride, "wants": None},
        {"user": nxt.format(**L), "gold": gnext, "wants": None},
        {"user": can[i % 4], "gold": "removed", "wants": ["unlinks", [[a, b], [b, c], [c, d]]]},
        {"user": ride.format(**L), "gold": gafter, "wants": None}]})
json.dump({"seed": 20261108, "conversations": conv, "plain": []}, open(os.path.join(HERE, "results", "after", "lines_draw.json"), "w"), ensure_ascii=False, indent=0)
print(json.dumps(conv[0], ensure_ascii=False)[:700])
