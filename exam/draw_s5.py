#!/usr/bin/env python3
"""exam/AFTER.md S5: the walkthrough's four turns, every name passed through nyc-relabelled's mapping, gold from reflib on the blocking copy. T8_R1=1 T8_R2=1 python3 exam/draw_s5.py"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X, "lib"), os.path.join(X, "t8", "fw")]
import noun as N  # noqa: E402
import reflib  # noqa: E402

A = os.path.join(HERE, "results", "after")
m = {old: new for new, old in json.load(open(os.path.join(X, "data", "heldout", "nyc-relabelled", "nyc-relabelled.mapping.json")))["name"].items()}
g = N.with_noun(json.load(open(os.path.join(HERE, "items", "sealed", "nyc-relabelled_b.graph.json"))))
d = json.load(open(os.path.join(A, "r6_walk_draw.json")))
c = d["conversations"][0]
a, b, x = m["Bowling Green"], m["Pennsylvania Av"], m["Saratoga Av"]
sub = lambda s: s.replace("Bowling Green", a).replace("Pennsylvania Av", b).replace("Saratoga Av", x)
G = reflib.Graph(g)
assert len(G.by_label[a]) == len(G.by_label[b]) == len(G.by_label[x]) == 1
gold = [G.chase(a, "4 southbound 5; 3 southbound 5"), G.path(a, b)]
hx = G.by_label[x][0]
G.close(x)
gold.append(G.path(a, b))
G.reopen(x)
gold.append(G.path(a, b))
turns = [{"user": sub(t["user"]), "gold": gold[i], "wants": t.get("wants")} for i, t in enumerate(c["turns"])]
out = {"seed": "exam/AFTER.md S5, mechanical", "conversations": [{"key": "nyc-relabelled:walk", "graph": "nyc-relabelled-b", "from": a, "to": b, "closed": str(hx), "routes": gold[1:], "turns": turns}], "plain": []}
json.dump(out, open(os.path.join(A, "s5_draw.json"), "w"), ensure_ascii=False, indent=0)
for t in turns:
    print(t["user"][:90], "->", t["gold"][:70])
