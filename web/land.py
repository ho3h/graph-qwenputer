#!/usr/bin/env python3
"""Borough shorelines for the map. NYC Open Data, Borough Boundaries, data.cityofnewyork.us/resource/gthc-hcne.geojson. python3 -I web/land.py RAW writes web/land.json."""
import hashlib, json, sys

raw = open(sys.argv[1], "rb").read()
TOL = 0.00016
MIN_AREA = 1.5e-6


def rdp(P, t):
    keep = [False] * len(P)
    keep[0] = keep[-1] = True
    st = [(0, len(P) - 1)]
    while st:
        a, b = st.pop()
        ax, ay = P[a]; bx, by = P[b]
        dx, dy = (bx - ax) * .76, by - ay
        L = (dx * dx + dy * dy) ** .5 or 1e-12
        best, bi = 0, None
        for i in range(a + 1, b):
            d = abs(((P[i][0] - ax) * .76) * dy - (P[i][1] - ay) * dx) / L
            if d > best:
                best, bi = d, i
        if bi is not None and best > t:
            keep[bi] = True
            st += [(a, bi), (bi, b)]
    return [p for p, k in zip(P, keep) if k]


def area(r):
    return abs(sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))) * .38


out = {}
for f in json.loads(raw)["features"]:
    rings = []
    for poly in f["geometry"]["coordinates"]:
        for r in poly:
            if area(r) < MIN_AREA:
                continue
            # A closed ring has no single chord: split at the far point.
            k = max(range(len(r)), key=lambda i: (r[i][0] - r[0][0]) ** 2 + (r[i][1] - r[0][1]) ** 2)
            s = rdp(r[:k + 1], TOL)[:-1] + rdp(r[k:], TOL)[:-1]
            if len(s) >= 3:
                rings.append([[round(x, 5), round(y, 5)] for x, y in s])
    out[f["properties"]["boroname"]] = rings
json.dump({"source": "NYC Open Data, Borough Boundaries (gthc-hcne)", "sha256": hashlib.sha256(raw).hexdigest(), "tolerance_deg": TOL, "boroughs": out}, open("web/land.json", "w"), separators=(",", ":"))
print({k: (len(v), sum(map(len, v))) for k, v in out.items()})
