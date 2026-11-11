#!/usr/bin/env python3
"""exam/LIMITS.md: one worker; units claimed by directory. T8_R1=1 T8_WRITES=1 T8_NOUN=on python t8/fw/tokrun.py ../exam/run_limits.py --items I --out R --limit-s S"""
import argparse
import gzip
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mach as M  # noqa: E402
import noun as N  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--items", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--limit-s", type=float, required=True)
a = ap.parse_args()
t0 = time.time()
it = json.load(open(a.items))
os.makedirs(os.path.join(a.out, "claims"), exist_ok=True)


def graph(name, n, es, rels):
    return N.with_noun({"format": "x210-graph/1", "name": name, "domain": "limits", "nodes": [{"label": f"Stop {i:04d}", "prop": 0, "src": str(i)} for i in range(n)], "relations": rels, "splice": [], "change": None, "edges": [[x, r, y, 1] for x, r, y in es]})


for u in it["units"] + [{"unit": "edits"}]:
    if time.time() - t0 > a.limit_s:
        print("deadline", flush=True)
        break
    if u.get("refused"):
        continue
    try:
        os.mkdir(os.path.join(a.out, "claims", u["unit"]))
    except FileExistsError:
        continue
    tu = time.time()
    e = it["edits"] if u["unit"] == "edits" else u
    pair = M.Pair(graph(u["unit"], e["n"], e["edges"], e["rels"]), it["prompt_ids"], it["between_ids"], coverage=False)
    with gzip.open(os.path.join(a.out, u["unit"] + ".jsonl.gz"), "wt", encoding="utf-8", errors="surrogateescape", compresslevel=3) as f:
        def one(tag, i, ids, want):
            r = pair.call(ids)
            r.update(tag=tag, i=i, want=want, t=round(time.time() - tu, 1))
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
        if u["unit"] == "edits":
            pair.fresh()
            for i, c in enumerate(e["add"]):
                one("link", i, c["ids"], None)
        else:
            for i, c in enumerate(u["calls"]):
                pair.fresh()
                one(c["tag"], i, c["ids"], c["want"])
            for k, c in enumerate(u["closes"]):
                pair.fresh()
                one("close", k, c["ids"], None)
                for i, ids in enumerate(c["chase_ids"]):
                    one("closed", i, ids, c["want"][i])
    json.dump({"unit": u["unit"], "seconds": round(time.time() - tu, 1), "finished": True}, open(os.path.join(a.out, u["unit"] + ".json"), "w"))
    print(u["unit"], round(time.time() - tu, 1), flush=True)
print("worker done", flush=True)
