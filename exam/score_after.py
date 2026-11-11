#!/usr/bin/env python3
"""exam/AFTER.md B from saved rows: Qwen alone, the same strict marking as score_reply.py, and generous: the gold's label appears in the reply."""
import json
import re
import sys
from collections import Counter

R = [json.loads(x) for x in open(sys.argv[1])]
SAID = re.compile(r"(?i)stopped|did not finish|didn't finish|not finish|no further|couldn't|cannot|can't")
c = Counter()
for r in R:
    g, reply = r["gold_text"], r["final"].strip()
    s = r["source"]
    if g.startswith("@"):
        want = g.split(" ", 1)[1]
    else:
        m = re.search(r"at @\d+ (.+?)(?:, |$)", g)
        want = m.group(1) if m else None
    strict = bool(want) and (reply.rstrip(".").strip() == want if g.startswith("@") else want in reply and bool(SAID.search(reply)))
    generous = bool(want) and want in reply
    c["n"] += 1
    c["strict"] += strict
    c["generous"] += generous
    c[s + "_n"] += 1
    c[s + "_strict"] += strict
    c[s + "_generous"] += generous
json.dump(dict(c), open(sys.argv[2], "w"), indent=0)
print(json.dumps(dict(c)))
