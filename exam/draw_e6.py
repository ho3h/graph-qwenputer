#!/usr/bin/env python3
"""exam/AFTER.md E6: r1's 40 conversations and 30 traps, same trips, stops and wordings, with gold from reflib on the blocking map. python3 exam/draw_e6.py"""
import json
import os
import sys

os.environ.update(T8_R1="1", T8_R2="1")
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "lib"), os.path.join(X210, "t8", "fw")]
import noun as N  # noqa: E402
import reflib  # noqa: E402

g = N.with_noun(json.load(open(os.path.join(HERE, "items", "nyc_b.graph.json"))))
d = json.load(open(os.path.join(HERE, "results", "nyc_r1_edit_draw.json")))
Q = {f"nyc:{q['id']}": q for q in json.load(open(os.path.join(X210, "data", "heldout", "nyc", "nyc.questions.json")))["questions"]}


def lines(key, x=None):
    c = Q[key]["call"]["args"]
    G = reflib.Graph(g)
    if x is not None:
        G.close(f"@{x}")
    return G.chase(c["start"], c["legs"])


moved = 0
for c in d["conversations"]:
    c["graph"] = "nyc-b"
    op, cl = lines(c["key"]), lines(c["key"], c["node"])
    c["changed"] = cl != op
    moved += c["changed"]
    c["turns"][0]["gold"], c["turns"][1]["gold"] = cl, op
for t in d["plain"]:
    t["graph"] = "nyc-b"
    op = lines(t["key"])
    t["on_route"] = lines(t["key"], t["node"]) != op
    t["turns"][0]["gold"] = op
json.dump(d, open(os.path.join(HERE, "results", "after", "e6_draw.json"), "w"), ensure_ascii=False, indent=0)
print(len(d["conversations"]), moved, len(d["plain"]), sum(t["on_route"] for t in d["plain"]))
