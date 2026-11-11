#!/usr/bin/env python3
"""D2m and D4m from saved rows and items only. Writes --out.

    python3 exam/score_machine.py --items exam/items/c024.json --rows exam/results/c024 --out exam/results/c024_score.json
"""
import argparse
import glob
import json
import os
from collections import Counter

ap = argparse.ArgumentParser()
ap.add_argument("--items", required=True)
ap.add_argument("--rows", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
it = json.load(open(a.items))


def rows(name):
    p = os.path.join(a.rows, name + ".jsonl")
    return [json.loads(x) for x in open(p, encoding="utf-8", errors="surrogateescape")] if os.path.exists(p) else []


def good(r):
    return r["status"] == "ok" and r["wrap"] and not r["flags"] and r["same"] and r["body"] == r["want"]


D2, D4, bad, kinds = Counter(), Counter(), [], Counter()
base = rows("base")
base_body = {r["i"]: r["body"] for r in base}
D2["base"], D2["base_right"] = len(base), sum(good(r) for r in base)
bad += [dict(r, unit="base") for r in base if not good(r)]
for u in it["units"]:
    rs = rows(u["unit"])
    D2["units_finished"] += os.path.exists(os.path.join(a.rows, u["unit"] + ".json"))
    for r in rs:
        ok = good(r)
        if r["tag"] in ("close", "reopen"):
            k = "edit_lines"
        elif r["tag"] == "closed":
            was = it["questions"][r["i"]]["base"]
            if r["want"] != was:
                k = "affected"
                ok = ok and r["body"] != base_body.get(r["i"])
                kinds[r["want"].split(" ")[0] if not r["want"].startswith("@") else "station"] += 1
            else:
                k = "unaffected"
                ok = ok and r["body"] == base_body.get(r["i"])
        else:
            k = "restored"
            ok = ok and r["body"] == base_body.get(r["i"])
        D2[k] += 1
        D2[k + "_right"] += ok
        D2["chip"] += r["chip"]
        if not ok:
            bad.append(dict(r, unit=u["unit"]))
for f in sorted(glob.glob(os.path.join(a.rows, "paths*.jsonl"))):
    for ln in open(f, encoding="utf-8", errors="surrogateescape"):
        r = json.loads(ln)
        D4["path"] += 1
        D4["right"] += good(r)
        D4["chip"] += r["chip"]
        D4["max_chip"] = max(D4["max_chip"], r["chip"])
        if not good(r):
            bad.append(dict(r, unit=os.path.basename(f)))
assert len(it["questions"]) == 600 and len(it["units"]) == 20
need = 20 * len(it["questions"])
d2_pass = D2["units_finished"] == 20 and D2["affected"] + D2["unaffected"] == need and D2["affected_right"] == D2["affected"] and D2["unaffected_right"] == D2["unaffected"] and D2["restored_right"] == D2["restored"] == need and D2["base_right"] == D2["base"] == len(it["questions"]) and D2["edit_lines_right"] == D2["edit_lines"] == 40
d4_pass = D4["path"] == len(it["pairs"]) and D4["right"] == D4["path"]
out = {"name": it["name"], "D2m": dict(D2), "affected_kinds": dict(kinds), "D2m_pass": d2_pass, "D4m": dict(D4), "D4m_pass": d4_pass, "bad_n": len(bad), "bad": bad[:40]}
json.dump(out, open(a.out, "w", encoding="utf-8", errors="surrogateescape"), indent=0, ensure_ascii=False)
print(json.dumps({k: v for k, v in out.items() if k != "bad"}), "first bad", json.dumps(bad[:2])[:800])
