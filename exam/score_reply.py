#!/usr/bin/env python3
"""D1r: pass to Qwen on D1m's questions, from saved rows only. The machine's line, and Qwen's reply marked strictly: the reply, with an optional @h handle and final full stop removed, is the gold label and nothing else. A stopped-early gold: the reply names the station it stopped at and says it stopped. Generous marking (host/score.py's, any right label) beside it. Every reply is saved in --md for Theo to read.

    python3 exam/score_reply.py --rows exam/results/nyc_d1r --out exam/results/nyc_d1r_score.json --md exam/results/nyc_d1r_replies.md
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "t8"), os.path.join(X210, "lib")]
import arms as A  # noqa: E402
import reflib  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--rows", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--md", required=True)
a = ap.parse_args()
R = [json.loads(x) for x in open(os.path.join(a.rows, "all.jsonl"))]
SAID = re.compile(r"(?i)stopped|did not finish|didn't finish|not finish|no further|couldn't|cannot|can't")
c = Counter()
md = open(a.md, "w")
md.write("# Every reply, whole\n")
for r in R:
    gold = reflib.reword(r["gold_text"])
    calls = r.get("calls") or []
    line = reflib.split_reading(calls[-1].get("result") or "")[1].split("\n")[-1] if calls else None
    c["line_" + A.outcome(line, gold)] += 1
    reply = (r.get("final") or "").strip()
    c["generous_right"] += bool(r.get("correct"))
    m = re.match(r"(?:Stopped early.*?at )?@(\d+) (.+?)(?:,| no|$)", gold)
    if gold.startswith("Stopped early"):
        lab = re.search(r"at @\d+ (.+?), ", gold) or re.search(r"at @\d+ (.+?)$", gold)
        strict = bool(lab) and lab.group(1) in reply and bool(SAID.search(reply))
        c["limit_golds"] += 1
        c["limit_strict"] += strict
    elif gold.startswith("@"):
        want = gold.split(" ", 1)[1]
        strict = re.sub(r"^@\d+\s+", "", reply).rstrip(".").strip() == want
    else:
        strict = reply.rstrip(".") == gold
    c["strict_right"] += strict
    c["status_" + r["status"]] += 1
    c["seconds"] += r["seconds"]
    md.write(f"\n## {r['id']}\n{r['text']}\n\nGold: `{gold}`\n\nMachine: `{line}`\n\nReply ({'right' if strict else 'not right'}, strict): {reply}\n")
out = {"n": len(R), "counts": dict(c)}
json.dump(out, open(a.out, "w"), indent=0)
print(json.dumps(out))
