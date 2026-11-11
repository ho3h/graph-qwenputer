#!/usr/bin/env python3
"""The page's demo trip on r1's executor, reference machine beside it: nothing closed, then each station closed by handle and by name, on a fresh machine each time. T8_R1=1. Writes exam/results/after/demo_check.json."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mach as M
import noun as N
import items as I

it = json.load(open(os.path.join(HERE, "items", "nyc.json")))
gp, _ = I.load("nyc")
g = N.with_noun(json.load(open(gp)))
pair = M.Pair(g, it["prompt_ids"], it["between_ids"], coverage=False)
T = pair.T
LEGS = "A northbound 1; 5 southbound 3"
STOPS = {483: "Wall St", 223: "Bowling Green", 220: "Borough Hall", 401: "Nevins St", 181: "Atlantic Av-Barclays Ctr"}


def call(closed=None):
    t = f"\n<function=chase>\n<parameter=start>\nHigh St\n</parameter>\n<parameter=legs>\n{LEGS}\n</parameter>\n" + (f"<parameter=closed>\n{closed}\n</parameter>\n" if closed else "") + "</function>\n"
    pair.fresh()
    r = pair.call(T.encode(t))
    return {"body": r["body"], "same_as_reference": r["same"], "flags": r["flags"]}


out = {"open": call()}
for h, name in STOPS.items():
    out[name] = {"by_handle": call(f"@{h}"), "by_name": call(name)}
json.dump(out, open(os.path.join(HERE, "results", "after", "demo_check.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False)[:1800])
