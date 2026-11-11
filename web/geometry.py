#!/usr/bin/env python3
"""The post's map: real track geometry from the MTA feed already on disk (xseries/X2.7/raw/gtfs_subway.zip, GTFS shapes.txt). Each pair of stops gets the track between them, simplified. Writes web/geometry.json."""
import collections
import csv
import io
import json
import math
import zipfile

Z = zipfile.ZipFile("../X2.7/raw/gtfs_subway.zip")
rd = lambda n: csv.DictReader(io.TextIOWrapper(Z.open(n), "utf-8-sig"))
x27 = json.load(open("../X2.7/graph.json"))
S = x27["stations"]
shape_route = collections.defaultdict(set)
for t in rd("trips.txt"):
    if t.get("shape_id"):
        shape_route[t["route_id"]].add(t["shape_id"])
pts = collections.defaultdict(list)
for r in rd("shapes.txt"):
    pts[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
for k in pts:
    pts[k] = [(a, b) for _, a, b in sorted(pts[k])]
print(len(pts), "shapes", sorted(shape_route)[:40])
C = math.cos(math.radians(40.7))
d2 = lambda a, b: ((a[0] - b[0]) * C) ** 2 + (a[1] - b[1]) ** 2


def nearest(line, p):
    b, bd = 0, 1e9
    for i, q in enumerate(line):
        d = d2(q, p)
        if d < bd:
            b, bd = i, d
    return b, bd


def rdp(p, eps):
    if len(p) < 3:
        return p
    a, b = p[0], p[-1]
    ax, ay, bx, by = a[0] * C, a[1], b[0] * C, b[1]
    L = math.hypot(bx - ax, by - ay) or 1e-9
    mx, mi = 0, 0
    for i in range(1, len(p) - 1):
        x, y = p[i][0] * C, p[i][1]
        d = abs((bx - ax) * (ay - y) - (ax - x) * (by - ay)) / L
        if d > mx:
            mx, mi = d, i
    if mx < eps:
        return [a, b]
    return rdp(p[: mi + 1], eps)[:-1] + rdp(p[mi:], eps)


pairs = {}
routes = collections.defaultdict(set)
fall = 0
ROUTE_SHAPES = lambda r: shape_route.get(r, set())
for e in x27["edges"]:
    a, b, r = e["from"], e["to"], e["route"]
    k = tuple(sorted((a, b)))
    routes[k].add(r)
    if k in pairs:
        continue
    A, B = (S[a]["lon"], S[a]["lat"]), (S[b]["lon"], S[b]["lat"])
    best = None
    for sid in ROUTE_SHAPES(r):
        ln = pts[sid]
        i, di = nearest(ln, A)
        j, dj = nearest(ln, B)
        if i == j:
            continue
        sc = di + dj
        if best is None or sc < best[0]:
            best = (sc, sid, i, j)
    lim = (0.0035) ** 2
    if best and best[0] < 2 * lim:
        _, sid, i, j = best
        seg = pts[sid][min(i, j): max(i, j) + 1]
        if i > j:
            seg = seg[::-1]
        L = sum(math.sqrt(d2(seg[n], seg[n + 1])) for n in range(len(seg) - 1))
        if L <= 3.5 * math.sqrt(d2(A, B)) + 0.002:
            pairs[k] = [A] + seg[1:-1] + [B]
            continue
    fall += 1
    pairs[k] = [A, B]
out = []
for k, line in pairs.items():
    line = rdp(line, 0.00006)
    out.append({"a": k[0], "b": k[1], "routes": sorted(routes[k]), "pts": [[round(x, 5), round(y, 5)] for x, y in line]})
json.dump(out, open("web/geometry.json", "w"), separators=(",", ":"))
print(len(out), "pairs", fall, "straight fallbacks", sum(len(o["pts"]) for o in out), "points", len(json.dumps(out)))
