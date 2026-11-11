#!/usr/bin/env python3
"""exam/AFTER.md Q's draw. python3 exam/draw_journeys.py"""
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

g = N.with_noun(json.load(open(os.path.join(X210, "data", "heldout", "nyc", "nyc.graph.json"))))
G0 = reflib.Graph(g)
TRIPS = [("Bowling Green", "Mets-Willets Point"), ("Bedford Av", "WTC Cortlandt"), ("Coney Island-Stillwell Av", "Flushing-Main St"), ("Howard Beach-JFK Airport", "Pelham Bay Park"), ("Far Rockaway-Mott Av", "Wakefield-241 St"), ("Inwood-207 St", "Coney Island-Stillwell Av"), ("Astoria-Ditmars Blvd", "Canarsie-Rockaway Pkwy"), ("Bay Ridge-95 St", "Brooklyn Bridge-City Hall"), ("Forest Hills-71 Av", "Whitehall St-South Ferry"), ("Prospect Park", "Van Cortlandt Park-242 St"), ("Sutphin Blvd-Archer Av-JFK Airport", "Bowling Green"), ("Jamaica-179 St", "Rockaway Park-Beach 116 St"), ("Times Sq-42 St", "Coney Island-Stillwell Av"), ("Grand Central-42 St", "Flushing-Main St"), ("Atlantic Av-Barclays Ctr", "Wakefield-241 St")]
Q = "What's the route with the fewest stops from {a} to {b}?"
W = ["{x} is closed. What's the route now?", "Flooding has shut {x}. What's the route now?", "Trains are skipping {x} today. What's the route now?"]
rng = random.Random("20261108:nyc:journeys")
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
    assert best, (a, b)
    h, p = best
    lab = g["nodes"][h]["label"]
    conv.append({"key": f"nyc-j:{i}", "graph": "nyc", "from": a, "to": b, "closed": h, "routes": [gold, p], "turns": [{"user": Q.format(a=a, b=b), "gold": gold, "wants": None}, {"user": W[i % 3].format(x=lab), "gold": p, "wants": ["close", h]}]})
    print(a, ">", b, gold.split(":")[0], "| close", lab, p.split(":")[0], flush=True)
json.dump({"seed": 20261108, "conversations": conv, "plain": []}, open(os.path.join(HERE, "results", "after", "journeys_draw.json"), "w"), ensure_ascii=False, indent=0)
