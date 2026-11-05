#!/usr/bin/env python3
"""The whole chain: told, the cleaner firmware, one call, the machine's line as the answer, on the executor through speed/fast.py. Base: ~/Models/x210/x210-tok.

    python t8/fw/chain.py --set dev|hard --out t8/fw/results/chain_dev --stock N --deadline-s S [--force slow]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(X210, "speed"))
import fast  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--set", required=True, choices=["dev", "hard"])
ap.add_argument("--out", required=True)
ap.add_argument("--stock", type=int, default=2)
ap.add_argument("--deadline-s", type=float, required=True)
ap.add_argument("--force", choices=["fast", "slow"])
ap.add_argument("--rows", type=int, default=8)
ap.add_argument("--flow", default="print-one", choices=["print-one", "read-one", "print-writes", "read-writes"])
ap.add_argument("--machine", default="clean", choices=["clean", "writes"])
ap.add_argument("--draw", default="chain_draw.json")
a = ap.parse_args()
g = fast.setup(a.machine)
draw = json.load(open(os.path.join(HERE, "results", a.draw)))
if a.set == "dev":
    its = fast.items([tuple(k) for k in draw["dev"]])
else:
    its = []
    for q in draw["hard"]:
        sub = "cities" if q["graph"].startswith("c") else "random"
        gr = json.load(open(os.path.join(X210, "data", "dev", sub, q["graph"] + ".graph.json")))
        i = int(q["key"].split(":")[1])
        qq = {"id": i, "kind": "chase", "text": q["text"], "call": {"fn": "chase", "args": {"start": q["start"], "legs": "; ".join(f"{r} {k}" for r, k in q["legs"])}}, "answer": [int(q["gold_line"].split()[0][1:])] if q["gold_line"].startswith("@") else [], "answer_text": q["gold_line"]}
        its.append((gr, qq, (f"{sub}/{q['graph']}", i)))
fl = fast.flow(a.flow)
m = fast.run(its, fl, a.out, rows=a.rows, stock=a.stock, force=a.force, deadline_s=a.deadline_s)
print({k: m.get(k) for k in ("path", "ran_on", "firmware_sha256", "flow_key", "bad")}, flush=True)
