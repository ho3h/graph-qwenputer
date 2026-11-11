#!/usr/bin/env python3
"""exam/AFTER.md U0. T8_R1=1 T8_R2=1 T8_WRITES=1 T8_NOUN=on through tokrun: r2_cap.py --out FILE"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mach as M
import noun as N
import reflib
import box as XX

out = sys.argv[sys.argv.index("--out") + 1]
it = json.load(open(os.path.join(HERE, "items", "nyc.json")))
g = N.with_noun(json.load(open(os.path.join(HERE, "items", "nyc_t.graph.json"))))
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
T = pair.T
G = reflib.Graph(g)
pair.fresh()
names = [f"Capstop {i:02d}" for i in range(20)]
calls = [("add_node", {"name": "x" * 31}), ("add_node", {"name": "y" * 32})]
calls += [("add_node", {"name": n}) for n in names]
prev = "Roosevelt Island"
for n in names[:14]:
    calls.append(("link", {"from": prev, "relation": "T northbound", "to": n}))
    prev = n
calls += [("path", {"from": "Roosevelt Island", "to": names[13]}), ("chase", {"start": "Roosevelt Island", "legs": "T northbound 14"}), ("find", {"name": names[0]}), ("find", {"name": names[19]})]
with open(out, "w") as f:
    for fn, a in calls:
        r = pair.call(T.encode(XX.template_text(fn, a)))
        w = G.call(fn, a)
        row = {"fn": fn, "args": a, "body": r["body"], "same": bool(r["same"]), "ref_body": r.get("ref_body"), "reflib": w, "chip": r["chip"]}
        f.write(json.dumps(row) + "\n")
        print(fn, a, "|", r["body"][:90], "| same", r["same"], "| reflib eq", r["body"] == w, flush=True)
print("cap finished", flush=True)
