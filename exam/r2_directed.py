#!/usr/bin/env python3
"""exam/AFTER.md Y. Through tokrun with T8_R2=1: r2_directed.py --shard K/N --out DIR --limit-s S"""
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
elf = hashlib.sha256(open(os.environ["CHIP_FIRMWARE"], "rb").read()).hexdigest()
it = json.load(open(os.path.join(HERE, "items", "nyc.json")))
g = N.with_noun(json.load(open(os.environ.get("R2_D_GRAPH", os.path.join(HERE, "items", "nyc_t.graph.json")))))
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
T = pair.T
G0 = reflib.Graph(g)
uniq = sorted(l for l, v in G0.by_label.items() if len(v) == 1)
W1 = ["Moss", "Fern", "Wren", "Lark", "Quay", "Ash", "Vale", "Heron", "Sable", "Tamar"]
W2 = ["Pk", "St", "Sq", "Av", "Rd"]
f = open(os.path.join(out, f"shard{k}.jsonl"), "a", buffering=1)
t0 = time.time()


def seq(s, calls, kind):
    pair.fresh()
    G = reflib.Graph(g)
    for j, (fn, x) in enumerate(calls):
        ids = T.encode(XX.template_text(fn, x))
        if XX.capture_rule(ids, T):
            continue
        r = pair.call(ids)
        w = G.call(fn, x)
        f.write(json.dumps({"s": s, "j": j, "kind": kind, "fn": fn, "args": x, "body": r["body"], "ref_body": r["ref_body"], "same": bool(r["same"]), "status": r["status"], "chip": r["chip"], "want": w, "eq": r["body"] == w, "elf": elf}) + "\n")


REL = os.environ.get("R2_D_REL", "T northbound")
SEED = os.environ.get("R2_D_SEED", "20261104:r2d")
COUNT = int(os.environ.get("R2_D_N", "400"))
for s in range(COUNT):
    if s % n != k:
        continue
    if time.time() - t0 > lim:
        print("deadline", flush=True)
        break
    rng = random.Random(f"{SEED}:{s}")
    if s % 100 == 7:
        seq(s, [("add_node", {"name": f"Fill {i:02d}"}) for i in range(18)], "fill_stops")
        continue
    if s % 100 == 57:
        st = rng.sample(uniq, 40)
        pairs = [(x, y) for x in st for y in st if x != y]
        rng.shuffle(pairs)
        seq(s, [("link", {"from": x, "relation": REL, "to": y}) for x, y in pairs[:262]], "fill_edges")
        continue
    m = rng.randint(2, 5)
    new = []
    while len(new) < m:
        nm = f"{rng.choice(W1)} {rng.choice(W2)}"
        if nm not in new:
            new.append(nm)
    a_, d_, x_ = rng.sample(uniq, 3)
    chain = [a_] + new + [d_]
    c = [("add_node", {"name": nm}) for nm in new]
    links = list(zip(chain, chain[1:]))
    c += [("link", {"from": p, "relation": REL, "to": q}) for p, q in links]
    c += [("chase", {"start": a_, "legs": f"{REL} {rng.randint(1, m + 1)}"}), ("neighbours", {"node": new[0], "relation": REL}), ("neighbours", {"node": new[-1], "relation": REL, "direction": "in"})]
    c += [("close", {"node": new[rng.randrange(m)]}), ("chase", {"start": a_, "legs": f"{REL} {m}"})]
    c += [("reopen", {"node": n_}) for n_ in new]
    c += [("close", {"node": x_}), ("reopen", {"node": x_})]
    if s % 4 == 0:
        c.append(("path", {"from": a_, "to": new[-1]}))
    i_ = rng.randrange(len(links))
    c += [("unlink", {"from": links[i_][0], "relation": REL, "to": links[i_][1]}), ("chase", {"start": a_, "legs": f"{REL} {m + 1}"}), ("link", {"from": links[i_][0], "relation": REL, "to": links[i_][1]})]
    c += [("unlink", {"from": p, "relation": REL, "to": q}) for p, q in links]
    c.append(("chase", {"start": a_, "legs": f"{REL} 1"}))
    seq(s, c, "aimed")
print("shard finished", time.time() - t0, flush=True)
