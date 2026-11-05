#!/usr/bin/env python3
"""exam/LIMITS.md's items. T8_R1=1 T8_WRITES=1 T8_NOUN=on python t8/fw/tokrun.py ../exam/items_limits.py --out exam/items/limits.json"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import items as I  # noqa: E402

N, X, reflib, O, dlib, BR = I.N, I.X, I.reflib, I.O, I.dlib, I.BR
T = BR.Text(X.tokenizer_json())
sys.modules["overlay"].set_text(T)
rng = random.Random("20261107:limits")
enc = lambda fn, args: T.encode(X.template_text(fn, args))


def graph(name, n, edges, rels):
    return N.with_noun({"format": "x210-graph/1", "name": name, "domain": "limits", "nodes": [{"label": f"Stop {i:04d}", "prop": 0, "src": str(i)} for i in range(n)], "relations": rels, "splice": [], "change": None, "edges": [[a, r, b, 1] for a, r, b in edges]})


def fits(g):
    try:
        X.machine_for(g)
        return True
    except Exception as e:
        if type(e).__name__ != "BootLimit":
            raise
        return False


def rand_edges(n, m, r, seed):
    q = random.Random(seed)
    seen, out = set(), []
    while len(out) < m:
        e = (q.randrange(n), q.randrange(r), q.randrange(n))
        if e[0] != e[2] and e not in seen:
            seen.add(e)
            out.append(e)
    return out


search = {}
for r in (1, 8):
    lo, hi = 4000, 30000
    rels = [f"r{k}" for k in range(r)]
    while hi - lo > 5:
        mid = (lo + hi) // 2
        if fits(graph("fit", 1024, rand_edges(1024, mid, r, 7), rels)):
            lo = mid
        else:
            hi = mid
    search[r] = lo
    print("fit", r, lo, flush=True)


def scale_free(n, m=3):
    q = random.Random(n)
    tg, out = list(range(m)), []
    pool = []
    for v in range(m, n):
        for t in set(tg):
            out.append((v, 0, t))
            out.append((t, 0, v))
        pool += list(set(tg)) + [v] * m
        tg = [q.choice(pool) for _ in range(m)]
    return out


n = 1024
G = {}
two = lambda es: [(a, 0, b) for a, b in es] + [(b, 0, a) for a, b in es]
G["chain"] = (n, [(i, 0, i + 1) for i in range(n - 1)], ["next"])
G["ring"] = (n, [(i, 0, (i + 1) % n) for i in range(n)], ["next"])
G["star"] = (n, two([(0, i) for i in range(1, n)]), ["spoke"])
G["tree"] = (1023, two([((i - 1) // 2, i) for i in range(1, 1023)]), ["branch"])
G["grid"] = (n, [(y * 32 + x, 0, y * 32 + x + 1) for y in range(32) for x in range(31)] + [(y * 32 + x + 1, 1, y * 32 + x) for y in range(32) for x in range(31)] + [(y * 32 + x, 2, (y + 1) * 32 + x) for y in range(31) for x in range(32)] + [((y + 1) * 32 + x, 3, y * 32 + x) for y in range(31) for x in range(32)], ["east", "west", "south", "north"])
for s in (64, 128, 256, 512, 1024):
    G[f"sf{s:04d}"] = (s, scale_free(s), ["link"])
G["densest"] = (n, rand_edges(n, search[8], 8, 11), [f"r{k}" for k in range(8)])
out = {"search": search, "units": [], "prompt_ids": None}
base = json.load(open(os.path.join(HERE, "items", "nyc.json")))
out["prompt_ids"], out["between_ids"] = base["prompt_ids"], base["between_ids"]
for name, (nn, es, rels) in G.items():
    g = graph(name, nn, es, rels)
    if not fits(g):
        out["units"].append({"unit": name, "refused": True, "n": nn, "e": len(es)})
        print(name, "refused", nn, len(es), flush=True)
        continue
    adj = collections.defaultdict(set)
    at = collections.defaultdict(list)
    for a, r, b in es:
        adj[a].add(b)
        at[a].append(r)
    far = []
    for s in random.Random(name).sample(range(nn), min(40, nn)):
        d = {s: 0}
        q = [s]
        for v in q:
            for y in adj[v]:
                if y not in d:
                    d[y] = d[v] + 1
                    q.append(y)
        t = max(d, key=lambda k: (d[k], k))
        far.append((d[t], s, t))
    far.sort(reverse=True)
    pts = {"chain": (0, nn - 1), "ring": (0, nn - 1), "tree": (nn - 1, nn // 2 + 1)}
    pairs = ([(pts[name][0], pts[name][1])] if name in pts else []) + [(s, t) for _, s, t in far[:5]] + [(rng.randrange(nn), rng.randrange(nn)) for _ in range(35)]
    calls = []
    G0 = reflib.Graph(g)
    for s, t in pairs:
        a = {"from": f"@{s}", "to": f"@{t}"}
        calls.append({"tag": "path", "ids": enc("path", a), "want": reflib.Graph(g).call("path", a)})
    cs = []
    for _ in range(40):
        h = rng.randrange(nn)
        if not at[h]:
            continue
        a = {"start": f"@{h}", "legs": f"{rels[rng.choice(at[h])]} {rng.randint(1, 8)}"}
        cs.append(a)
        calls.append({"tag": "chase", "ids": enc("chase", a), "want": reflib.Graph(g).call("chase", a)})
    closes = []
    for x in rng.sample(range(nn), 5):
        Gx = reflib.Graph(g)
        Gx.close(f"@{x}")
        closes.append({"node": x, "ids": enc("close", {"node": f"@{x}"}), "reopen_ids": enc("reopen", {"node": f"@{x}"}), "want": [Gx.call("chase", a) for a in cs[:20]], "chase_ids": [enc("chase", a) for a in cs[:20]]})
    out["units"].append({"unit": name, "n": nn, "e": len(es), "rels": rels, "edges": es, "calls": calls, "closes": closes, "hops": [p[0] for p in far[:5]]})
    print(name, nn, len(es), far[0][0], flush=True)
g = graph("edits", 256, rand_edges(256, 300, 2, 3), ["r0", "r1"])
Ge = reflib.Graph(g)
add, m = [], 0
for _ in range(300):
    a = {"from": f"@{rng.randrange(256)}", "rel": "r0", "to": f"@{rng.randrange(256)}"}
    add.append({"ids": enc("link", a), "args": a})
out["edits"] = {"edges": rand_edges(256, 300, 2, 3), "rels": ["r0", "r1"], "n": 256, "add": add}
json.dump(out, open(sys.argv[sys.argv.index("--out") + 1], "w"), ensure_ascii=False)
print("written", len(out["units"]), flush=True)
