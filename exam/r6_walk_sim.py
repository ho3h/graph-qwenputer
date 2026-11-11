#!/usr/bin/env python3
"""exam/AFTER.md r6e's calls on the simulator, with the reference machine on every call. Through tokrun with T8_R6=1: r6_walk_sim.py --out R.json"""
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
g = N.with_noun(json.load(open(os.path.join(HERE, "items", "nyc_b.graph.json"))))
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
G = reflib.Graph(g)
a, b, x = "Bowling Green", "Pennsylvania Av", "Saratoga Av"
calls = [("chase", {"start": a, "legs": "4 southbound 5; 3 southbound 5"}), ("path", {"from": a, "to": b}), ("close", {"node": x}), ("path", {"from": a, "to": b}), ("reopen", {"node": x}), ("path", {"from": a, "to": b})]
pair.fresh()
rows = []
for fn, args in calls:
    r = pair.call(pair.T.encode(XX.template_text(fn, args)))
    w = G.call(fn, args)
    assert r["same"] and r["body"] == w, (fn, r["body"], w)
    rows.append({"fn": fn, "args": args, "body": r["body"], "chip": r["chip"], "digest": r["digest"]})
json.dump({"ran_on": "simulator, with the reference machine on every call", "calls": rows}, open(out, "w"), ensure_ascii=False, indent=0)
print("walk sim finished", [(x["fn"], x["chip"]) for x in rows], flush=True)
