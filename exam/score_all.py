#!/usr/bin/env python3
"""exam/MINI.md from saved rows. python3 exam/score_all.py ROWS ITEMS MAC_BASE OUT"""
import collections
import glob
import gzip
import json
import os
import sys

R, I, MAC, OUT = sys.argv[1:5]
it = json.load(open(I))
Q = it["questions"]
rows = lambda u: [json.loads(x) for x in gzip.open(os.path.join(R, u + ".jsonl.gz"), "rt", encoding="utf-8", errors="surrogateescape")]
ok = lambda r: r["status"] == "ok" and r["wrap"] and not r["flags"] and r["same"]
out = {"elf": set()}
fin = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(os.path.join(R, "*.json"))}
for v in fin.values():
    out["elf"].add(v["elf_sha256"])
out["elf"] = sorted(out["elf"])
c = collections.Counter()
bad = []
for u in it["units"]:
    if u["kind"] != "close" or u["unit"] not in fin:
        continue
    c["units"] += 1
    for r in rows(u["unit"]):
        t = r["tag"]
        right = ok(r) and r["body"] == r["want"]
        c[t] += 1
        c[t + "_right"] += right
        if t == "closed":
            aff = u["closed_want"][r["i"]] != Q[r["i"]]["base"]
            c["affected" if aff else "unaffected"] += 1
            c[("affected" if aff else "unaffected") + "_right"] += right
        if not right and len(bad) < 20:
            bad.append([u["unit"], t, r["i"], r["body"][:120], r["want"][:120], r["same"]])
out["every_station"] = dict(c)
out["every_station_bad"] = bad
out["uses"] = {"seconds_median": sorted(v["seconds"] for k, v in fin.items() if k.startswith("all"))[len([k for k in fin if k.startswith("all")]) // 2] if any(k.startswith("all") for k in fin) else None}
for name in ("blackout", "longest", "fuzz"):
    if name not in fin:
        continue
    d = collections.Counter()
    b = []
    mx = 0
    for r in rows(name):
        t = r["tag"]
        d[t] += 1
        d[t + "_same_as_reference"] += bool(r["same"])
        d[t + "_equal_want"] += r["body"] == r["want"]
        mx = max(mx, r["chip"])
        if (not r["same"] or r["body"] != r["want"]) and len(b) < 40:
            b.append([t, r["i"], r["body"][:150], r["want"][:150], r["same"]])
    out[name] = dict(d, max_chip=mx, seconds=fin[name]["seconds"])
    out[name + "_differences"] = b
if "longest" in fin:
    out["longest"]["hops"] = [it["longest"][0]["hops"], it["longest"][-1]["hops"]]
    out["longest"]["trip"] = it["longest"][0]["want"][:300]
if "base" in fin and MAC != "-":                                    # exam/AFTER.md S1: "-" when no second machine ran this map's base
    mac = {json.loads(x)["i"]: json.loads(x)["digest"] for x in open(MAC)}
    me = rows("base")
    out["base_digest_same_as_mac"] = sum(r["digest"] == mac[r["i"]] for r in me)
    out["base_n"] = len(me)
json.dump(out, open(OUT, "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in out.items() if not k.endswith(("differences", "bad"))}, ensure_ascii=False)[:1800])
