#!/usr/bin/env python3
"""D1m from saved rows only: the machine's four outcomes on the exact line (T6), the host's beside them, the bar, agreement on the written call, reserved ids. Writes --out.

    python3 exam/score_d1m.py --rows exam/results/nyc_d1m --host exam/results/nyc_host.jsonl --out exam/results/nyc_d1m_score.json
"""
import argparse
import json
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "t8"), os.path.join(X210, "lib")]
import arms as A  # noqa: E402
import reflib  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--rows", required=True)
ap.add_argument("--host", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--n", type=int, default=200)
a = ap.parse_args()


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - s) / d, 3), round((c + s) / d, 3)]


def last(res):
    if res is None:
        return None
    return reflib.split_reading(res)[1].split("\n")[-1]


reserved = set(range(0))
tj = json.load(open(os.path.expanduser("~/Models/x210/x210-tok/tokenizer.json")))
reserved = {t["id"] for t in tj["added_tokens"] if t["content"].startswith("<|reserved_")}
M = [json.loads(x) for x in open(os.path.join(a.rows, "all.jsonl"))]
H = {}
if os.path.exists(a.host):
    H = {json.loads(x)["id"]: json.loads(x) for x in open(a.host)}
c, h, same = Counter(), Counter(), Counter()
wrong = []
for r in M:
    gold = reflib.reword(r["gold_text"])
    calls = r.get("calls") or []
    line = last(calls[-1].get("result")) if calls else None
    res_row = any(i in reserved for s in r.get("segments", []) for i in s["ids"])
    o = A.outcome(line, gold)
    if o == "right" and (res_row or r["status"] in ("lock", "engine_flag", "verify_mismatch")):
        o = "void_row"
    c[o] += 1
    c["unasked_closed"] += any("closed" in (k.get("args") or {}) for k in calls)
    c["toolong"] += line == "TOOLONG"
    c["reserved_rows"] += res_row
    c["lock_or_flag"] += r["status"] in ("lock", "engine_flag", "verify_mismatch")
    c["machine_equals_host_tool"] += all(k.get("same_as_host") for k in calls) and bool(calls)
    c["seconds"] += r["seconds"]
    c["qwen_tokens"] += r["qwen_tokens"]
    c["chip_tokens"] += r["chip_tokens"]
    if o != "right":
        wrong.append({"id": r["id"], "text": r["text"], "gold": gold, "call": (calls[-1].get("args") if calls else None), "line": line, "outcome": o})
    x = H.get(r["id"])
    if x is not None:
        ho = A.outcome(last(x["result"]), gold)
        if ho == "right" and any(i in reserved for i in x["seg"]):
            ho = "void_row"
        h[ho] += 1
        same["both"] += 1
        same["same_call"] += bool(calls) and x["inner"] == calls[0].get("text")
        same["same_outcome"] += ho == o
n = len(M)
out = {"n": n, "machine": dict(c), "machine_right_wilson": wilson(c["right"], n), "host": dict(h), "host_n": sum(h.values()), "agreement": dict(same), "wrong": wrong}
p = os.path.join(a.rows, "stock_sample.json")
out["stock"] = {k: v for k, v in json.load(open(p)).items() if k != "questions"} if os.path.exists(p) else None
out["stock_questions"] = len(json.load(open(p))["questions"]) if os.path.exists(p) else 0
whole = n == a.n and sum(h.values()) == n and c["lock_or_flag"] == 0
stock_ok = bool(out["stock"]) and out["stock"]["passed"]
out["void"] = None if stock_ok else "the stock sample did not pass or did not run: the run doesn't count until explained"
if whole:
    out["bar"] = {"machine_points": round(100 * c["right"] / n, 1), "host_points": round(100 * h["right"] / n, 1), "pass": stock_ok and 100 * c["right"] / n >= 100 * h["right"] / n - 2}
else:
    out["bar"] = {"pass": False, "why": f"incomplete: {n} machine rows, {sum(h.values())} host rows of {a.n}, {c['lock_or_flag']} lock or flag rows"}
out["by_source"] = dict(Counter(("shared" if int(r["id"]) >= 910000 else "generated" if int(r["id"]) >= 900000 else "file") + "_" + A.outcome(last((r.get("calls") or [{}])[-1].get("result")), reflib.reword(r["gold_text"])) for r in M))
json.dump(out, open(a.out, "w"), indent=0, ensure_ascii=False)
print(json.dumps({k: v for k, v in out.items() if k != "wrong"}, ensure_ascii=False))
