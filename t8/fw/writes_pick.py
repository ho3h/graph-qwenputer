#!/usr/bin/env python3
"""W3's conversations, by rule, from W2's rows. No model. Writes results/writes_stock_draw.json."""
import json
import os
HERE = os.path.dirname(os.path.abspath(__file__))
rows = {json.loads(l)["key"]: json.loads(l) for l in open(os.path.join(HERE, "results", "writes", "all.jsonl"))}
draw = json.load(open(os.path.join(HERE, "results", "edit3_draw.json")))


def full(c):
    r = rows.get(c["key"])
    if not r or r["status"] != "answered" or not r["returned_to_start"]:
        return False
    ls = [(k.get("result") or "") for t in r["turns"] for k in t["calls"]]
    return any(f"closed @{c['node']} " in l and not "not closed" in l for l in ls) and any(f"reopened @{c['node']} " in l for l in ls)


picks = []
for want in (lambda c: c["changed"], lambda c: not c["changed"]):
    for c in draw["conversations"]:
        if full(c) and want(c) and c not in picks:
            picks.append(c)
            break
traps = [c for c in draw["plain"] if c["key"] in rows and not rows[c["key"]]["returned_to_start"]][:1]
json.dump({"conversations": picks, "plain": traps}, open(os.path.join(HERE, "results", "writes_stock_draw.json"), "w"), ensure_ascii=False)
print(len(picks), len(traps), [c["key"] for c in picks + traps])
