#!/usr/bin/env python3
"""exam/MINI.md: one worker; units are claimed by directory. T8_R1=1 T8_WRITES=1 python t8/fw/tokrun.py ../exam/run_all.py --items I --out R --limit-s S [--only fuzz,longest]"""
import argparse
import gzip
import hashlib
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
ap.add_argument("--only", default="")
a = ap.parse_args()
t0 = time.time()
it = json.load(open(a.items))
gp = os.environ.get("RUN_ALL_GRAPH") or os.path.join(os.path.dirname(HERE), "data", "heldout", "nyc", "nyc.graph.json")  # exam/AFTER.md r6
assert hashlib.sha256(open(gp, "rb").read()).hexdigest() == it["graph_sha256"]
os.makedirs(os.path.join(a.out, "claims"), exist_ok=True)
pair = M.Pair(N.with_noun(json.load(open(gp))), it["prompt_ids"], it["between_ids"], coverage=False)
Q = it["questions"]
elf = hashlib.sha256(open(os.environ["CHIP_FIRMWARE"], "rb").read()).hexdigest()
only = tuple(x for x in a.only.split(",") if x)
for u in [{"unit": "base", "kind": "base"}] + it["units"]:
    if time.time() - t0 > a.limit_s:
        print("deadline", flush=True)
        break
    if only and not u["unit"].startswith(only):
        continue
    try:
        os.mkdir(os.path.join(a.out, "claims", u["unit"]))
    except FileExistsError:
        continue
    tu = time.time()
    pair.fresh()
    with gzip.open(os.path.join(a.out, u["unit"] + ".jsonl.gz"), "wt", encoding="utf-8", errors="surrogateescape", compresslevel=3) as f:
        def one(tag, i, ids, want):
            r = pair.call(ids)
            r.update(tag=tag, i=i, want=want)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        k = u["kind"]
        if k == "base":
            for i, q in enumerate(Q):
                one("base", i, q["ids"], q["base"])
        elif k == "close":
            one("close", -1, u["close_ids"], u["close_want"])
            for i, w in enumerate(u["closed_want"]):
                one("closed", i, Q[i]["ids"], w)
            one("reopen", -1, u["reopen_ids"], u["reopen_want"])
            for i in it["restored"]:
                one("restored", i, Q[i]["ids"], Q[i]["base"])
        elif k == "blackout":
            for i, s in enumerate(it["blackout"]):
                one(s["tag"], i, s["ids"], s["want"])
        elif k == "longest":
            for i, s in enumerate(it["longest"]):
                one("longest", i, s["ids"], s["want"])
        else:
            for i, s in enumerate(it["fuzz"]):
                one("fuzz:" + s["kind"], i, s["ids"], s["want"])
    json.dump({"unit": u["unit"], "seconds": round(time.time() - tu, 1), "finished": True, "elf_sha256": elf}, open(os.path.join(a.out, u["unit"] + ".json"), "w"))
    print(u["unit"], round(time.time() - tu, 1), "s", flush=True)
print("worker done", round(time.time() - t0), flush=True)
