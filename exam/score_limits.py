#!/usr/bin/env python3
"""exam/LIMITS.md from saved rows. python3 exam/score_limits.py ROWS ITEMS OUT"""
import collections
import gzip
import json
import os
import re
import sys

R, I, OUT = sys.argv[1:4]
it = json.load(open(I))
res = {"search": it["search"], "units": {}}
for u in it["units"] + [{"unit": "edits"}]:
    p = os.path.join(R, u["unit"] + ".jsonl.gz")
    if u.get("refused"):
        res["units"][u["unit"]] = {"refused": True, "n": u["n"], "e": u["e"]}
        continue
    if not os.path.exists(p):
        continue
    c = collections.Counter()
    longest = []
    first_refusal = None
    diff = []
    for l in gzip.open(p, "rt", encoding="utf-8", errors="surrogateescape"):
        r = json.loads(l)
        t = r["tag"]
        c[t] += 1
        c[t + "_same_as_reference"] += bool(r["same"])
        if r["want"] is not None:
            eq = r["body"] == r["want"]
            c[t + "_equal_reflib"] += eq
            if not eq and len(diff) < 8:
                diff.append([t, r["i"], r["body"][:100], r["want"][:100]])
        if r["status"] != "ok":
            c["status_" + r["status"]] += 1
        if t == "path" and r["body"][:1].isdigit():
            longest.append((int(r["body"].split(" ")[0]), r["chip"]))
        if t == "link" and first_refusal is None and not r["body"].startswith("linked"):
            first_refusal = [r["i"], r["body"][:80]]
    res["units"][u["unit"]] = {"n": u.get("n"), "e": u.get("e"), "counts": dict(c), "tokens_by_hops": sorted(longest)[-8:], "max_chip": max((x[1] for x in longest), default=0), "first_refusal": first_refusal, "differences": diff, "done": os.path.exists(os.path.join(R, u["unit"] + ".json"))}
json.dump(res, open(OUT, "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: {a: b for a, b in v.items() if a not in ("tokens_by_hops", "differences")} for k, v in res["units"].items()}, ensure_ascii=False)[:2400])
