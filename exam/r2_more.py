#!/usr/bin/env python3
"""exam/AFTER.md S. T8_R1=1 T8_R2=1 T8_WRITES=1 T8_NOUN=on through tokrun; units claimed by directory. r2_more.py --out R --limit-s S"""
import collections
import gzip
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
out, lim = a[a.index("--out") + 1], float(a[a.index("--limit-s") + 1])
os.makedirs(os.path.join(out, "claims"), exist_ok=True)
it = json.load(open(os.path.join(HERE, "items", "nyc.json")))
g = N.with_noun(json.load(open(os.path.join(os.path.dirname(HERE), "data", "heldout", "nyc", "nyc.graph.json"))))
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
T = pair.T
enc = lambda f, x: T.encode(XX.template_text(f, x))
Q = it["questions"]
G0 = reflib.Graph(g)
stations = [k for k, v in G0.by_label.items() if G0._joined(sorted(v))]
assert len(stations) == 18, len(stations)
labels = sorted(G0.by_label)
units = [("close", u) for u in it["units"]] + [("paths", i) for i in range(0, 500, 50)] + [("station", s) for s in stations] + [("names", i) for i in range(0, 2000, 100)]
sub = random.Random("20261108:r2:sub").sample(range(len(Q)), 30)
t0 = time.time()
for kind, u in units:
    if time.time() - t0 > lim:
        print("deadline", flush=True)
        break
    name = f"{kind}-{u['unit'] if kind == 'close' else u}".replace("/", "_").replace(" ", "_")
    try:
        os.mkdir(os.path.join(out, "claims", name))
    except FileExistsError:
        continue
    pair.fresh()
    G = reflib.Graph(g)
    with gzip.open(os.path.join(out, name + ".jsonl.gz"), "wt", encoding="utf-8", errors="surrogateescape") as f:
        def one(tag, ids, want):
            r = pair.call(ids)
            f.write(json.dumps({"tag": tag, "body": r["body"], "same": bool(r["same"]), "want": want, "eq": r["body"] == want, "chip": r["chip"], "status": r["status"]}, ensure_ascii=False) + "\n")
        if kind == "close":
            one("close", u["close_ids"], u["close_want"])
            for i, w in enumerate(u["closed_want"]):
                one("closed", Q[i]["ids"], w)
            one("reopen", u["reopen_ids"], u["reopen_want"])
            for i in sub:
                one("restored", Q[i]["ids"], Q[i]["base"])
        elif kind == "paths":
            for p in it["pairs"][u:u + 50]:
                pair.fresh()
                one("path", p["ids"], p["want"])
        elif kind == "station":
            one("close", enc("close", {"node": u}), G.call("close", {"node": u}))
            for q in Q:
                one("closed", q["ids"], G.call("chase", q["args"]))
            one("reopen", enc("reopen", {"node": u}), G.call("reopen", {"node": u}))
            for i in sub:
                one("restored", Q[i]["ids"], G.call("chase", Q[i]["args"]))
        else:
            rng = random.Random(f"20261108:r2:names:{u}")
            for _ in range(100):
                x = {"from": rng.choice(labels), "to": rng.choice(labels)}
                pair.fresh()
                one("name", enc("path", x), reflib.Graph(g).call("path", x))
    json.dump({"unit": name, "seconds": round(time.time() - t0), "finished": True}, open(os.path.join(out, name + ".json"), "w"))
    print(name, round(time.time() - t0), flush=True)
print("worker done", flush=True)
