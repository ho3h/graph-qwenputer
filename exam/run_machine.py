#!/usr/bin/env python3
"""D2m and D4m on the executor with the reference machine beside it, every call. One process a worker; units are claimed by mkdir. Rows under --out. A mismatch is recorded and the run carries on, so a miss is counted whole.

    T8_WRITES=1 python t8/fw/tokrun.py ../exam/run_machine.py --items exam/items/c024.json --out exam/results/c024 --limit-s 3600
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mach as M  # noqa: E402
import noun as N  # noqa: E402
import items as _I  # noqa: E402,F401 (for load)


class Union:
    def __init__(self, path):
        self.path, self.u, self.positions, self.head = path, {k: {} for k in M.CV.ns["KINDS"]}, 0, None

    def add(self, cov):
        x = cov.log()
        self.positions += x["positions"]
        for k in self.u:
            for i, f in x[k]:
                self.u[k].setdefault(i, f)
        self.head = {k: x[k] for k in ("tables_sha256", "engine_source_sha256", "gates_total", "channels_total", "value_heads")}
        out = dict(self.head, label="exam", positions=self.positions, flags=x["flags"], compared_on_stock=False, **{k: sorted([i, f] for i, f in self.u[k].items()) for k in self.u})
        tmp = self.path + ".tmp"
        json.dump(out, open(tmp, "w"))
        os.replace(tmp, self.path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit-s", type=float, required=True)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    t0 = time.time()
    it = json.load(open(a.items))
    assert it["gold_bad_n"] == 0 and it["disagree_n"] == 0, "the items' checks failed"
    gp, _ = _I.load(it["name"])
    assert hashlib.sha256(open(gp, "rb").read()).hexdigest() == it["graph_sha256"]
    g = N.with_noun(json.load(open(gp)))
    os.makedirs(os.path.join(a.out, "claims"), exist_ok=True)
    pair = M.Pair(g, it["prompt_ids"], it["between_ids"])
    cov = Union(os.path.join(a.out, f"cov-{os.getpid()}.json"))
    Q = it["questions"]
    units = [{"unit": "base", "qs": True}] + it["units"] + [{"unit": f"paths{k:02d}", "pairs": it["pairs"][k * 50:(k + 1) * 50]} for k in range((len(it["pairs"]) + 49) // 50)]
    only = tuple(x for x in a.only.split(",") if x)
    for u in units:
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
        with open(os.path.join(a.out, u["unit"] + ".jsonl"), "w", encoding="utf-8", errors="surrogateescape") as f:
            def one(tag, i, ids, want):
                r = pair.call(ids)
                r.update(tag=tag, i=i, want=want)
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            if "qs" in u:
                for i, q in enumerate(Q):
                    one("base", i, q["ids"], q["base"])
            elif "pairs" in u:
                for i, p in enumerate(u["pairs"]):
                    one("path", i, p["ids"], p["want"])
            else:
                one("close", -1, u["close_ids"], u["close_want"])
                for i, w in enumerate(u["closed_want"]):
                    one("closed", i, Q[i]["ids"], w)
                one("reopen", -1, u["reopen_ids"], u["reopen_want"])
                for i, q in enumerate(Q):
                    one("restored", i, q["ids"], q["base"])
        cov.add(pair.cov)
        json.dump({"unit": u["unit"], "seconds": round(time.time() - tu, 1), "finished": True, "elf_sha256": hashlib.sha256(open(os.environ["CHIP_FIRMWARE"], "rb").read()).hexdigest()}, open(os.path.join(a.out, u["unit"] + ".json"), "w"))
        print(u["unit"], round(time.time() - tu, 1), "s", flush=True)
    print("worker done", round(time.time() - t0), flush=True)


main()
