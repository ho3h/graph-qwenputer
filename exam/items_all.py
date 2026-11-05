#!/usr/bin/env python3
"""exam/MINI.md's items. T8_R1=1 T8_WRITES=1 python t8/fw/tokrun.py ../exam/items_all.py --out exam/items/nyc_all.json"""
import argparse
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import items as I  # noqa: E402

N, X, reflib, O, dlib, BR = I.N, I.X, I.reflib, I.O, I.dlib, I.BR
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
a = ap.parse_args()
it = json.load(open(os.environ.get("ITEMS_BASE") or os.path.join(HERE, "items", "nyc.json")))   # exam/AFTER.md S1
gp, _ = I.load("nyc")
gp = os.environ.get("ITEMS_GRAPH", gp)                             # exam/AFTER.md r6
g = N.with_noun(json.load(open(gp)))
T = BR.Text(X.tokenizer_json())
net = O.Net(g)
Q = it["questions"]
rng = random.Random("20261105:nyc:all")
n = len(g["nodes"])
disagree = []
enc = lambda fn, args: T.encode(X.template_text(fn, args))


def want(fn, args, closed=()):
    G = reflib.Graph(g)
    for h in closed:
        G.close(f"@{h}")
    got = G.call(fn, args)
    o = reflib.reword(net.state(closed).call({"fn": fn, "args": args}))
    if got != o:
        disagree.append([fn, args, list(closed)[:5], len(closed), got, o])
    return got


order = rng.sample(range(n), n)
sub = sorted(rng.sample(range(len(Q)), 30))
units = [{"unit": "fuzz", "kind": "fuzz"}, {"unit": "longest", "kind": "longest"}, {"unit": "blackout", "kind": "blackout"}]
for k, h in enumerate(order):
    lab = g["nodes"][h]["label"]
    units.append({"unit": f"all{k:03d}", "kind": "close", "node": h, "close_ids": enc("close", {"node": f"@{h}"}), "reopen_ids": enc("reopen", {"node": f"@{h}"}), "close_want": f"closed @{h} {lab}", "reopen_want": f"reopened @{h} {lab}", "closed_want": [want("chase", q["args"], (h,)) for q in Q]})
    if k % 50 == 0:
        print(k, len(disagree), flush=True)
# blackout
bo = rng.sample(range(n), n)
bq = sorted(rng.sample(range(len(Q)), 30))
steps, closed = [], []
for k, h in enumerate(bo):
    closed.append(h)
    steps.append({"tag": "close", "ids": enc("close", {"node": f"@{h}"}), "want": f"closed @{h} {g['nodes'][h]['label']}"})
    if k % 31 == 30 or k == n - 1:
        steps += [{"tag": "during", "ids": Q[i]["ids"], "want": want("chase", Q[i]["args"], tuple(closed))} for i in bq]
for k, h in enumerate(reversed(bo)):
    closed.remove(h)
    steps.append({"tag": "reopen", "ids": enc("reopen", {"node": f"@{h}"}), "want": f"reopened @{h} {g['nodes'][h]['label']}"})
    if k % 31 == 30:
        steps += [{"tag": "during", "ids": Q[i]["ids"], "want": want("chase", Q[i]["args"], tuple(closed))} for i in bq]
steps += [{"tag": "final", "ids": q["ids"], "want": q["base"]} for q in Q]
# longest
adj = dlib.adjacency(g)
out = collections.defaultdict(set)
for x, r, y, w in g["edges"]:
    out[x].add(y)
far = []
for s in range(n):
    d = {s: 0}
    q = [s]
    for v in q:
        for y in out[v]:
            if y not in d:
                d[y] = d[v] + 1
                q.append(y)
    far += [(d[t], s, t) for t in d if t != s]
far.sort(key=lambda x: (-x[0], x[1], x[2]))
longest = []
for hops, s, t in far[:50]:
    args = {"from": f"@{s}", "to": f"@{t}"}
    w = want("path", args)
    assert w == dlib.canon_path(g, s, t, adj) and w.startswith(f"{hops} steps"), (args, w)
    longest.append({"args": args, "hops": hops, "ids": enc("path", args), "want": w})
# fuzz
G0 = reflib.Graph(g)
names = g["relations"]
routes = [r for r in names if r.endswith("bound")]
at = collections.defaultdict(list)
for x, r, y, w in g["edges"]:
    at[x].append(names[r])
leg = lambda: f"{rng.choice(routes)} {rng.randint(1, 5)}"
fuzz, dropped = [], 0
kinds = ["one"] * 2000 + ["two"] * 2000 + ["three"] * 500 + ["awkward"] * 500
for kind in kinds:
    h = rng.randrange(n)
    lab = g["nodes"][h]["label"]
    on = [r for r in at[h] if r.endswith("bound")] or routes
    first = f"{rng.choice(on)} {rng.randint(1, 5)}"
    if kind == "one":
        args = {"start": lab, "legs": first}
    elif kind == "two":
        args = {"start": lab, "legs": f"{first}; {leg()}"}
    elif kind == "three":
        args = {"start": lab, "legs": f"{first}; {leg()}; {leg()}"}
    else:
        w = rng.randrange(4)
        args = {"start": lab, "legs": f"Z northbound {rng.randint(1, 4)}"} if w == 0 else {"start": lab[:-1] + "x", "legs": first} if w == 1 else {"start": lab, "legs": f"{rng.choice(routes)} {rng.randint(1, 4)}"} if w == 2 else {"start": lab, "legs": f"{rng.choice(on)} {rng.choice([0, 50, 400])}"}
    ids = enc("chase", args)
    if X.capture_rule(ids, T):
        dropped += 1
        continue
    fuzz.append({"kind": kind, "args": args, "ids": ids, "want": reflib.Graph(g).call("chase", args)})
print("disagree", len(disagree), disagree[:5], "fuzz", len(fuzz), "dropped", dropped, "longest", far[0], "blackout steps", len(steps), flush=True)
assert not disagree
json.dump({"graph_sha256": __import__("hashlib").sha256(open(gp, "rb").read()).hexdigest() if os.environ.get("ITEMS_GRAPH") else it["graph_sha256"], "prompt_ids": it["prompt_ids"], "between_ids": it["between_ids"], "questions": Q, "restored": sub, "units": units, "blackout": steps, "longest": longest, "fuzz": fuzz, "fuzz_dropped": dropped}, open(a.out, "w"), ensure_ascii=False)
