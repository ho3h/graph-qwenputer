#!/usr/bin/env python3
"""exam/AFTER.md Q's score, from saved rows. python3 exam/score_journeys.py"""
import json
import re

g = json.load(open("data/heldout/nyc/nyc.graph.json"))
lab = [n["label"] for n in g["nodes"]]
rows = [json.loads(x) for x in open("exam/results/after/journeys/all.jsonl")]


def listed(t):
    pos = -1
    names = []
    for h in re.findall(r"@(\d+)", t["calls"][-1]["result"]):
        if not names or names[-1] != lab[int(h)]:  # a change between same-name platforms counts once; round 10
            names.append(lab[int(h)])
    for n in names:
        pos = (t["reply"] or "").find(n, pos + 1)
        if pos < 0:
            return False
    return True


first = [r for r in rows if r["turns"][0]["calls"] and r["turns"][0]["calls"][-1]["result"] == r["item"]["routes"][0]]
second = [r for r in rows if len(r["turns"]) > 1]
s = {
    "conversations": len(rows),
    "first_route_right": len(first),
    "reached_closure_turn": len(second),
    "closure_written": sum(any(c["fn"] == "close" for c in r["turns"][1]["calls"]) for r in second),
    "new_route_right": sum(r["turns"][1]["calls"][-1]["result"] == r["item"]["routes"][1] for r in second),
    "turns": sum(len(r["turns"]) for r in rows),
    "reply_lists_every_stop_in_order": sum(listed(t) for r in rows for t in r["turns"]),
    "real_weights_conversations": sum(str(r["ran_on"]).startswith("stock") for r in rows),
    "verified_positions": sum(r.get("verified_positions") or 0 for r in rows),
    "verify_mismatches": sum(bool(r.get("verify_mismatch")) for r in rows),
    "firmware": sorted({r["firmware_sha256"][:8] for r in rows}),
}
json.dump(s, open("exam/results/after/journeys_score.json", "w"), indent=0)
print(s)
