#!/usr/bin/env python3
"""The conversations for lockstep on the real weights: the first 3 in draw order whose executor rows wrote a close and a reopen. No model. Writes results/edit_stock_draw.json."""
import json
import os
HERE = os.path.dirname(os.path.abspath(__file__))
rows = {json.loads(l)["key"]: json.loads(l) for l in open(os.path.join(HERE, "results", "edit2", "all.jsonl"))}
draw = json.load(open(os.path.join(HERE, "results", "edit2_draw.json")))
picks = []


def good(c):
    r = rows.get(c["key"])
    if not r:
        return False
    fns = [[k["fn"] for k in t["calls"]] for t in r["turns"]]
    return r["status"] == "answered" and "close" in fns[0] and "reopen" in fns[1] and r["returned_to_start"]


for want in (lambda c: c["changed"], lambda c: not c["changed"], lambda c: c["form"] == "station" and c["changed"]):       # one edit that moves the answer, one that doesn't, one with the noun
    for c in draw["conversations"]:
        if good(c) and want(c) and c not in picks:
            picks.append(c)
            break
json.dump({"conversations": picks, "plain": []}, open(os.path.join(HERE, "results", "edit2_stock_draw.json"), "w"), ensure_ascii=False)
print(len(picks), [(c["key"], c["changed"], c["form"]) for c in picks])
