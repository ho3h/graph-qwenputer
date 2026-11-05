#!/usr/bin/env python3
"""exam/AFTER.md O. Pure Python, no project imports. python3 exam/line_search.py GRAPH OUT"""
import collections
import json
import random
import sys

g = json.load(open(sys.argv[1]))
n = len(g["nodes"])
base = collections.defaultdict(set)
for a, r, b, w in g["edges"]:
    base[a].add(b)
rng = random.Random("20261108:nyc:search")
src = rng.sample(range(n), 100)


def hops(extra):
    tot, cnt = 0, 0
    for s in src:
        d = {s: 0}
        q = [s]
        for v in q:
            for y in list(base[v]) + extra.get(v, []):
                if y not in d:
                    d[y] = d[v] + 1
                    q.append(y)
        tot += sum(d.values())
        cnt += len(d)
    return tot, cnt


b0, c0 = hops({})
BASE = b0 / c0


def score(line):
    ex = collections.defaultdict(list)
    for x, y in zip(line, line[1:]):
        ex[x].append(y)
        ex[y].append(x)
    t, c = hops(ex)
    return BASE - t / c


rand = sorted(score(rng.sample(range(n), 8)) for _ in range(500))
best = []
for r in range(8):
    cur = rng.sample(range(n), 8)
    s = score(cur)
    for _ in range(2000):
        c2 = list(cur)
        c2[rng.randrange(8)] = rng.randrange(n)
        if len(set(c2)) < 8:
            continue
        t = score(c2)
        if t > s:
            cur, s = c2, t
    best.append([round(s, 4), cur, [g["nodes"][h]["label"] for h in cur]])
    print(r, best[-1], flush=True)
    json.dump({"base_mean_hops": BASE, "pairs": c0, "random": {"n": 500, "median": rand[250], "p95": rand[475], "max": rand[-1]}, "search": sorted(best, reverse=True)}, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
print("line_search finished", flush=True)
