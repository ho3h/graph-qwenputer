#!/usr/bin/env python3
"""What New York's stock window left uncompared: items the exams' executor reached (machine workers' coverage and each candidate's new items, which include D1m's calls) that no stock trace has compared. D1r and E1 aren't counted."""
import glob
import json

ids = lambda a: {x[0] if isinstance(x, list) else x for x in a}  # coverage logs hold [index, first position]
K = ("gates", "channels", "reads", "writes")
base = json.load(open("t8/fw/results/cov_baseline_w.json"))
known = {k: set(base[k]) for k in K}
win = {k: set() for k in K}
for f in sorted(glob.glob("t8/fw/results/cov/nyc_window/ny*.json")):
    j = json.load(open(f))
    assert j["stock_finished"] and j["compared_on_stock"] and not j["flags"], f
    for k in K:
        win[k] |= ids(j[k])
reached = {k: set() for k in K}
for f in sorted(glob.glob("exam/results/nyc/cov-*.json")):
    j = json.load(open(f))
    for k in K:
        reached[k] |= ids(j[k])
for f in sorted(glob.glob("exam/results/nyc_pick/shard*.jsonl")):
    for ln in open(f):
        for k, i in json.loads(ln)["new"]:
            reached[k].add(i)
out = {"totals": {"gates": base["gates_total"], "channels": base["channels_total"]}, "by_kind": {}}
for k in K:
    new = reached[k] - known[k]
    out["by_kind"][k] = {"baseline": len(known[k]), "added_by_window": len(win[k] - known[k]), "compared_now": len(known[k] | win[k]), "exam_reached": len(reached[k]), "new_in_exams": len(new), "left_uncompared": len(new - win[k])}
json.dump(out, open("exam/results/nyc_window_remainder.json", "w"), indent=1)
print(json.dumps(out, indent=1))
