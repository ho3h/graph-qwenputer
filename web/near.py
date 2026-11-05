#!/usr/bin/env python3
"""Land around the city, for the map only. US Census cartographic boundary file cb_2023_us_county_500k. python3 -I web/near.py ZIP writes web/near.json."""
import hashlib, json, struct, sys, zipfile

raw = open(sys.argv[1], "rb").read()
z = zipfile.ZipFile(sys.argv[1])
shp = z.read("cb_2023_us_county_500k.shp")
dbf = z.read("cb_2023_us_county_500k.dbf")
W, S, E, N = -74.8, 40.2, -73.2, 41.25
TOL = 0.0004
n, hl, rl = struct.unpack("<IHH", dbf[4:12])
fields, off = [], 32
while dbf[off] != 13:
    name = dbf[off:off + 11].split(b"\0")[0].decode()
    fields.append((name, dbf[off + 16]))
    off += 32
recs = []
for i in range(n):
    r, p, d = dbf[hl + i * rl:hl + (i + 1) * rl], 1, {}
    for name, ln in fields:
        d[name] = r[p:p + ln].decode("latin1").strip()
        p += ln
    recs.append(d)
BOROUGHS = {"36005", "36047", "36061", "36081", "36085"}


def clip(r):
    """Sutherland-Hodgman to the map's box."""
    for inside, cut in (
        (lambda p: p[0] >= W, lambda a, b: (W, a[1] + (b[1] - a[1]) * (W - a[0]) / (b[0] - a[0]))),
        (lambda p: p[0] <= E, lambda a, b: (E, a[1] + (b[1] - a[1]) * (E - a[0]) / (b[0] - a[0]))),
        (lambda p: p[1] >= S, lambda a, b: (a[0] + (b[0] - a[0]) * (S - a[1]) / (b[1] - a[1]), S)),
        (lambda p: p[1] <= N, lambda a, b: (a[0] + (b[0] - a[0]) * (N - a[1]) / (b[1] - a[1]), N)),
    ):
        o = []
        for i, p in enumerate(r):
            q = r[i - 1]
            if inside(p) != inside(q):
                o.append(cut(q, p))
            if inside(p):
                o.append(p)
        r = o
        if not r:
            return []
    return r


def rdp(P, t):
    keep = [False] * len(P)
    keep[0] = keep[-1] = True
    st = [(0, len(P) - 1)]
    while st:
        a, b = st.pop()
        dx, dy = (P[b][0] - P[a][0]) * .76, P[b][1] - P[a][1]
        L = (dx * dx + dy * dy) ** .5 or 1e-12
        best, bi = 0, None
        for i in range(a + 1, b):
            d = abs((P[i][0] - P[a][0]) * .76 * dy - (P[i][1] - P[a][1]) * dx) / L
            if d > best:
                best, bi = d, i
        if bi is not None and best > t:
            keep[bi] = True
            st += [(a, bi), (bi, b)]
    return [p for p, k in zip(P, keep) if k]


def area(r):
    return abs(sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))) * .38


pos, i, rings, used = 100, 0, [], []
while pos < len(shp):
    clen = struct.unpack(">I", shp[pos + 4:pos + 8])[0] * 2
    b = shp[pos + 8:pos + 8 + clen]
    pos += 8 + clen
    rec = recs[i]
    i += 1
    if struct.unpack("<i", b[:4])[0] != 5 or rec["GEOID"] in BOROUGHS:
        continue
    x0, y0, x1, y1 = struct.unpack("<4d", b[4:36])
    if x1 < W or x0 > E or y1 < S or y0 > N:
        continue
    np_, nv = struct.unpack("<2i", b[36:44])
    parts = list(struct.unpack(f"<{np_}i", b[44:44 + 4 * np_])) + [nv]
    v = struct.unpack(f"<{2 * nv}d", b[44 + 4 * np_:44 + 4 * np_ + 16 * nv])
    pts = list(zip(v[0::2], v[1::2]))
    got = False
    for a, c in zip(parts, parts[1:]):
        r = clip(pts[a:c - 1])
        if len(r) < 3 or area(r) < 3e-6:
            continue
        k = max(range(len(r)), key=lambda j: (r[j][0] - r[0][0]) ** 2 + (r[j][1] - r[0][1]) ** 2)
        s = rdp(r[:k + 1], TOL)[:-1] + rdp(r[k:] + [r[0]], TOL)[:-1]
        if len(s) >= 3:
            rings.append([[round(x, 4), round(y, 4)] for x, y in s])
            got = True
    if got:
        used.append(f'{rec["NAME"]} {rec["STUSPS"]}')
json.dump({"source": "US Census cb_2023_us_county_500k", "sha256": hashlib.sha256(raw).hexdigest(), "counties": sorted(used), "rings": rings}, open("web/near.json", "w"), separators=(",", ":"))
print(len(used), sorted(used), len(rings), sum(map(len, rings)))
