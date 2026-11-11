#!/usr/bin/env python3
"""exam/AFTER.md K3. T8_R1=1 T8_WRITES=1 T8_NOUN=on python t8/fw/tokrun.py ../exam/control_map.py"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mach as M
import noun as N

it = json.load(open(os.path.join(HERE, "items", "nyc.json")))
g = N.with_noun(json.load(open(os.path.join(X210, "data", "dev", "cities", "c024.graph.json"))))
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
c = Counter()
ex = []
for i, q in enumerate(it["questions"]):
    pair.fresh()
    r = pair.call(q["ids"])
    c["n"] += 1
    c["same_as_reference"] += bool(r["same"])
    c["equal_new_york"] += r["body"] == q["base"]
    c["kind:" + r["body"].split(" ")[0][:10] if not r["body"].startswith("@") else "kind:station"] += 1
    if len(ex) < 5:
        ex.append([q["args"], q["base"][:60], r["body"][:60]])
out = {"counts": dict(c), "examples": ex}
json.dump(out, open(os.path.join(HERE, "results", "after", "control_map.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False)[:900])
