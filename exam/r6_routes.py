#!/usr/bin/env python3
"""exam/AFTER.md r6c. Through tokrun with T8_R6=1: r6_routes.py --shard K/N --out DIR --limit-s S"""
import hashlib
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mach as M
import noun as N
import reflib
import box as XX

a = sys.argv
k, n = map(int, a[a.index("--shard") + 1].split("/"))
out, lim = a[a.index("--out") + 1], float(a[a.index("--limit-s") + 1])
os.makedirs(out, exist_ok=True)
it = json.load(open(os.path.join(HERE, "items", "nyc.json")))
g = N.with_noun(json.load(open(os.path.join(HERE, "items", "nyc_b.graph.json"))))
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
T = pair.T
G0 = reflib.Graph(g)
uniq = sorted(l for l, v in G0.by_label.items() if len(v) == 1)
elf = hashlib.sha256(open(os.environ["CHIP_FIRMWARE"], "rb").read()).hexdigest()
f = open(os.path.join(out, f"shard{k}.jsonl"), "a", buffering=1)
t0 = time.time()
skip = set(json.load(open(os.environ["R6C_SKIP"]))) if os.environ.get("R6C_SKIP") else set()      # r6c2: the sets r6c didn't finish
for s in range(1000):
    if s % n != k or s in skip:
        continue
    if time.time() - t0 > lim:
        print("deadline", flush=True)
        break
    rng = random.Random(f"20261104:r6c:{s}")
    shut = rng.sample(range(len(g["nodes"])), rng.randint(1, 12))
    trips = [rng.sample(uniq, 2) for _ in range(3)]
    calls = [("close", {"node": f"@{h}"}) for h in shut]
    calls += [("path", {"from": x, "to": y}) for x, y in trips]
    calls += [("reopen", {"node": f"@{h}"}) for h in shut]
    calls += [("path", {"from": trips[0][0], "to": trips[0][1]})]
    pair.fresh()
    G = reflib.Graph(g)
    for j, (fn, x) in enumerate(calls):
        r = pair.call(T.encode(XX.template_text(fn, x)))
        w = G.call(fn, x)
        f.write(json.dumps({"s": s, "j": j, "fn": fn, "args": x, "n_closed": len(shut), "body": r["body"], "ref_body": r["ref_body"], "same": bool(r["same"]), "status": r["status"], "chip": r["chip"], "want": w, "elf": elf[:16]}, ensure_ascii=False) + "\n")
print("worker done", round(time.time() - t0), flush=True)
