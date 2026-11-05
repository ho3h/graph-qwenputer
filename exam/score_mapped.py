#!/usr/bin/env python3
"""exam/AFTER.md E from saved rows."""
import json
import os
import re
import sys

D = sys.argv[1]
SAID = re.compile(r"(?i)stopped|did not finish|didn't finish|not finish|no further|couldn't|cannot|can't")
out = {}
for arm in ("M1", "M2", "M3", "M4"):
    p = os.path.join(D, arm + ".jsonl")
    if not os.path.exists(p):
        continue
    c = {"n": 0, "finished": 0, "plain_n": 0, "plain_strict": 0, "plain_generous": 0, "stop_n": 0, "stop_strict": 0, "stop_generous": 0, "other_n": 0, "seconds": 0, "wrong_finished": 0}
    for r in map(json.loads, open(p)):
        g, ans = r["gold"], r["answer"].replace("*", "").strip()
        c["n"] += 1
        c["finished"] += r["finished"]
        c["seconds"] += r["seconds"]
        if g.startswith("@"):
            want = g.split(" ", 1)[1]
            c["plain_n"] += 1
            s = ans.rstrip(".").strip() == want
            c["plain_strict"] += s
            c["plain_generous"] += want in ans
            c["wrong_finished"] += r["finished"] and want not in ans
        elif g.startswith("Stopped"):
            want = re.search(r"at @\d+ (.+?)(?:, |$)", g).group(1)
            c["stop_n"] += 1
            c["stop_strict"] += want in ans and bool(SAID.search(ans))
            c["stop_generous"] += want in ans
        else:
            c["other_n"] += 1
    out[arm] = c
json.dump(out, open(os.path.join(D, "score.json"), "w"), indent=1)
print(json.dumps(out))
