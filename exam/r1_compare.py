#!/usr/bin/env python3
"""exam/R1.md's adoption reading and its predictions, from saved rows only: the same 200 calls against the frozen run, the new 100, replies by source, E1. Writes exam/results/nyc_r1_compare.json."""
import glob
import json
import statistics as st

R = "exam/results/"
rows = lambda p: {str(r["id"]): r for r in map(json.loads, open(p))}
args = lambda r: [c["text"] for c in r["calls"]]
fz, r1 = rows(R + "nyc_d1m/all.jsonl"), rows(R + "nyc_r1_d1m/all.jsonl")
old = [i for i in r1 if i in fz]
new = [i for i in r1 if i not in fz]
ms = json.load(open(R + "nyc_r1_d1m_score.json"))
K = ("gates", "channels", "reads", "writes")
ids = lambda a: {x[0] if isinstance(x, list) else x for x in a}
base = json.load(open("t8/fw/results/cov_baseline_w.json"))
known = {k: set(base[k]) for k in K}
for f in glob.glob("t8/fw/results/cov/nyc_window/ny*.json"):
    j = json.load(open(f))
    for k in K:
        known[k] |= ids(j[k])
reached = {k: set() for k in K}
for f in glob.glob(R + "nyc_r1/cov-*.json"):
    j = json.load(open(f))
    for k in K:
        reached[k] |= ids(j[k])
out = {
    "d1m_same_200": {"n": len(old), "same_call_text": sum(args(fz[i]) == args(r1[i]) for i in old)},
    "d1m_new": {"n": len(new), "right": ms["by_source"].get("shared_right"), "ids_from": min(int(i) for i in new)},
    "d1m_chip_tokens": {"median": st.median(r1[i]["chip_tokens"] for i in r1), "max": max(r1[i]["chip_tokens"] for i in r1)},
    "d1m_qwen_tokens": {"median": st.median(r1[i]["qwen_tokens"] for i in r1)},
    "reach_r1_machine_exams_not_compared_on_frozen_window": {k: len(reached[k] - known[k]) for k in K},
}
rd = rows(R + "nyc_r1_d1r/all.jsonl")
sc = json.load(open(R + "nyc_r1_d1r_score.json"))
out["d1r_counts"] = sc["counts"]
print(json.dumps(out, indent=1))
json.dump(out, open(R + "nyc_r1_compare.json", "w"), indent=1)
