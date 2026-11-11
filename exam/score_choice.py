#!/usr/bin/env python3
"""exam/AFTER.md R from saved rows. python3 exam/score_choice.py DIR"""
import json
import os
import sys
from collections import Counter, defaultdict

D = sys.argv[1]
c = defaultdict(Counter)
ex = defaultdict(list)
for r in map(json.loads, open(os.path.join(D, "all.jsonl"))):
    arm = r["key"][0]
    for i, t in enumerate(r["turns"]):
        k = arm if arm != "E" else ("E-chat" if i == 0 else "E-route")
        c[k]["n"] += 1
        n = len(t["calls"])
        c[k]["called"] += n > 0
        if n:
            c[k]["fn_" + t["calls"][0]["fn"]] += 1
            f = t["calls"][-1]["result"].split("\n")[-1]
            c[k]["line_" + (f[:9] if not f.startswith("@") and not f[0].isdigit() else "answer")] += 1
        if len(ex[k]) < 5:
            ex[k].append((t["user"][:60], [x["fn"] for x in t["calls"]], (t["calls"][-1]["result"][:60] if t["calls"] else ""), (t["reply"] or "")[:90]))
    c[arm]["status_" + r["status"]] += 1
out = {k: dict(v) for k, v in c.items()}
json.dump({"counts": out, "examples": ex}, open(os.path.join(D, "choice_score.json"), "w"), indent=1, ensure_ascii=False)
for k in sorted(out):
    print(k, out[k])
    for e in ex[k][:5]:
        print("   ", e)
