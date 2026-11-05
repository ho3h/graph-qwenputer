#!/usr/bin/env python3
"""exam/AFTER.md P(1)(2). T8_R1=1 T8_R2=1 T8_WRITES=1 T8_NOUN=on python t8/fw/tokrun.py ../exam/r2_fuzz.py --shard K/N --out DIR --limit-s S. Random operation sequences on New York with new stops; also, shard 0: base questions with nothing added against r1's saved lines."""
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
g = N.with_noun(json.load(open(os.path.join(HERE, "items", "nyc_t.graph.json"))))
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
T = pair.T
enc = lambda f, x: T.encode(XX.template_text(f, x))
f = open(os.path.join(out, f"shard{k}.jsonl"), "w", buffering=1)
t0 = time.time()
if k == 0:
    base = {}
    for ln in open(os.path.join(HERE, "results", "nyc_r1", "base.jsonl")):
        r = json.loads(ln)
        base[r["i"]] = r["body"]
    same = 0
    pair.fresh()
    for i, q in enumerate(it["questions"]):
        same += pair.call(q["ids"])["body"] == base[i]
    json.dump({"base": len(it["questions"]), "same_as_r1": same}, open(os.path.join(out, "base_vs_r1.json"), "w"))
    print("base", same, flush=True)
labels = sorted({x["label"] for x in g["nodes"]})
rels = g["relations"]
WORDS = ["Moss", "Fern", "Oak", "Wren", "Lark", "Quay", "Ash", "Vale"]
SUF = ["Pk", "St", "Sq", "Av", "Rd"]
for s in range(2000):
    if s % n != k:
        continue
    if time.time() - t0 > lim:
        print("deadline", flush=True)
        break
    rng = random.Random(f"{os.environ.get('R2_SEED', '20261108:r2')}:{s}")
    pair.fresh()
    G = reflib.Graph(g)
    new = []
    for j in range(12):
        pool = labels + new * 40
        x = rng.choice(pool)
        y = rng.choice(pool)
        h = rng.random()
        rel = rng.choice(["T northbound", "T southbound"] + rels[:8])
        if h < .28 or not new:
            nm = f"{rng.choice(WORDS)} {rng.choice(SUF)}"
            if nm not in new:
                new.append(nm)
            c = ("add_node", {"name": nm if rng.random() > .05 else rng.choice(["", "@7", "x" * 40, labels[0]])})
        elif h < .5:
            c = ("link", {"from": x, "relation": rel, "to": y})
        elif h < .6:
            c = ("unlink", {"from": x, "relation": rel, "to": y})
        elif h < .68:
            c = ("close", {"node": x})
        elif h < .74:
            c = ("reopen", {"node": x})
        elif h < .82:
            c = ("find", {"name": x})
        elif h < .88:
            c = ("neighbours", {"node": x, "relation": rel})
        elif h < .94:
            c = ("chase", {"start": x, "legs": f"{rel} {rng.randint(1, 3)}"})
        elif h < .98:
            c = ("path", {"from": x, "to": y})
        else:
            c = ("cheapest", {"from": x, "to": y})
        ids = enc(*c)
        if XX.capture_rule(ids, T):
            continue
        r = pair.call(ids)
        w = G.call(*c)
        f.write(json.dumps({"s": s, "j": j, "fn": c[0], "args": c[1], "body": r["body"], "same": bool(r["same"]), "flags": r["flags"], "status": r["status"], "want": w, "eq": r["body"] == w}, ensure_ascii=False) + "\n")
print("shard finished", time.time() - t0, flush=True)
