#!/usr/bin/env python3
"""exam/AFTER.md T's draw: the post's walkthrough trip, downtown to east Brooklyn. python3 exam/draw_demo.py"""
import json
import os
import sys

os.environ["T8_R1"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "lib"), os.path.join(X210, "t8", "fw")]
import noun as N
import reflib

g = N.with_noun(json.load(open(os.path.join(X210, "data", "heldout", "nyc", "nyc.graph.json"))))
Q = "Start at Bowling Green station. Ride the 4 train 5 stops southbound, then change to the 3 and ride the 3 train 5 stops southbound. One stop means the next station. At which station are you now? Answer with the station name only."
LEGS = "4 southbound 5; 3 southbound 5"
X = "Saratoga Av"
h = [i for i, n in enumerate(g["nodes"]) if n["label"] == X][0]
G = reflib.Graph(g)
base = G.chase("Bowling Green", LEGS)
G.close(f"@{h}")
closed = G.chase("Bowling Green", LEGS)
print(base, "|", closed)
assert base != closed
conv = [{"key": "nyc-demo:0", "graph": "nyc", "node": h, "label": X, "changed": True, "turns": [
    {"user": Q, "gold": base, "wants": None},
    {"user": f"Flooding has shut {X}. " + Q, "gold": closed, "wants": ["close", h]},
    {"user": f"Repairs are done and {X} is back. " + Q, "gold": base, "wants": ["reopen", h]},
]}]
json.dump({"seed": 20261103, "conversations": conv, "plain": []}, open(os.path.join(HERE, "results", "after", "demo_draw.json"), "w"), ensure_ascii=False, indent=0)
