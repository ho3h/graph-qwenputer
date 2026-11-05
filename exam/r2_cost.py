#!/usr/bin/env python3
"""exam/AFTER.md X. Through tokrun with T8_R2=1: r2_cost.py --out FILE"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mach as M
import noun as N
import reflib
import box as XX

out = sys.argv[sys.argv.index("--out") + 1]
elf = hashlib.sha256(open(os.environ["CHIP_FIRMWARE"], "rb").read()).hexdigest()
it = json.load(open(os.path.join(HERE, "items", "nyc.json")))
g = N.with_noun(json.load(open(os.path.join(HERE, "items", "nyc_t.graph.json"))))
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
T = pair.T
f = open(out, "a", buffering=1)


def run(tag, setup, last):
    pair.fresh()
    G = reflib.Graph(g)
    for fn, a in setup + [last]:
        t0 = time.time()
        r = pair.call(T.encode(XX.template_text(fn, a)))
        w = G.call(fn, a)
        row = {"tag": tag, "fn": fn, "args": a, "elf": elf, "status": r["status"], "chip": r["chip"], "same": bool(r["same"]), "body": r["body"], "ref_body": r["ref_body"], "reflib": w, "eq_reflib": r["ref_body"] == w, "seconds": round(time.time() - t0, 1), "is_last": (fn, a) == last}
        f.write(json.dumps(row) + "\n")
    print(tag, row["status"], row["chip"], row["same"], row["eq_reflib"], flush=True)


ADD = ("add_node", {"name": "Capstop 00"})
LINK = ("link", {"from": "Roosevelt Island", "relation": "T northbound", "to": "Junius St"})
ROUTES = {"r7": ("Bedford Av", "WTC Cortlandt"), "r14": ("Roosevelt Island", "Junius St"), "r49": ("Far Rockaway-Mott Av", "Wakefield-241 St")}
for name, (a, b) in ROUTES.items():
    p = ("path", {"from": a, "to": b})
    run(name + ":none", [], p)
    run(name + ":add", [ADD], p)
    run(name + ":link", [LINK], p)
names = [f"Capstop {i:02d}" for i in range(16)]
for k in (2, 6, 10, 12, 14):
    c = [("add_node", {"name": n}) for n in names[:k]]
    prev = "Roosevelt Island"
    for n in names[:k]:
        c.append(("link", {"from": prev, "relation": "T northbound", "to": n}))
        prev = n
    run(f"chain{k}", c, ("path", {"from": "Roosevelt Island", "to": names[k - 1]}))
print("cost finished", flush=True)
