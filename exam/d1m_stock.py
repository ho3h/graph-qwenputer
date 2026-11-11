#!/usr/bin/env python3
"""exam/AFTER.md I: the r1 D1m questions in lockstep on the real weights, against their saved records. T8_R1=1. d1m_stock.py --part K --out R --limit-s S. Part K is the Kth 100 in seeded order."""
import json
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(X210, "speed")]
import d1m  # noqa: E402
import fast  # noqa: E402

a = sys.argv
k, out, lim = int(a[a.index("--part") + 1]), a[a.index("--out") + 1], float(a[a.index("--limit-s") + 1])
fast.setup("writes")
qs, _ = d1m.draw("nyc", 200)
assert len(qs) == 300
order = list(range(300))
random.Random("20261106:nyc:i").shuffle(order)
part = [qs[i] for i in order[k * 100:(k + 1) * 100]]
gr = json.load(open(d1m.base_of("nyc") + ".graph.json"))
os.makedirs(out, exist_ok=True)
shutil.copy(os.path.join(HERE, "results", "nyc_r1_d1m", "all.jsonl"), os.path.join(out, "all.jsonl"))
fl = fast.flow("print-writes")
assert fast.proof(fl)
m = fast.run([(gr, q, ("nyc", q["id"])) for q in part], fl, out, rows=8, stock=100, stock_seed=20261106, stock_limit_s=lim, deadline_s=60)
s = m["stock_sample"]
print({x: s.get(x) for x in ("asked", "positions", "mismatches", "head_mismatch", "token_differences", "passed")}, len(s["questions"]), flush=True)
sys.exit(0 if s["passed"] and len(s["questions"]) == 100 else 1)
