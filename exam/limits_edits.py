#!/usr/bin/env python3
"""exam/LIMITS.md, corrected edit-table unit: 300 links on a 256-node graph, then unlink them. T8_R1=1 T8_WRITES=1 T8_NOUN=on through tokrun."""
import json
import os
import random
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mach as M
import noun as N
import reflib
import box as XX

it = json.load(open(os.path.join(HERE, "items", "limits.json")))
e = it["edits"]
g = N.with_noun({"format": "x210-graph/1", "name": "edits", "domain": "limits", "nodes": [{"label": f"Stop {i:04d}", "prop": 0, "src": str(i)} for i in range(e["n"])], "relations": e["rels"], "splice": [], "change": None, "edges": [[x, r, y, 1] for x, r, y in e["edges"]]})
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
T = pair.T
G = reflib.Graph(g)
rng = random.Random("20261107:limits:edits")
pair.fresh()
c = Counter()
first = None
done = []
for i in range(300):
    a = {"from": f"@{rng.randrange(256)}", "relation": "r0", "to": f"@{rng.randrange(256)}"}
    r = pair.call(T.encode(XX.template_text("link", a)))
    w = G.call("link", a)
    c["link"] += 1
    c["same"] += bool(r["same"])
    c["eq_reflib"] += r["body"] == w
    c[r["body"].split(" ")[0]] += 1
    if r["body"].startswith("linked"):
        done.append(a)
    if first is None and not r["body"].startswith(("linked", "already")):
        first = [i, r["body"][:80], w[:80]]
out = {"counts": dict(c), "first_refusal": first}
print(json.dumps(out))
json.dump(out, open(os.path.join(HERE, "results", "mini", "limits_edits.json"), "w"), indent=1)
