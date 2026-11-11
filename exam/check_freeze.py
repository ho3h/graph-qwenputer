#!/usr/bin/env python3
"""Every frozen file against exam/FREEZE.json. Exit 1 on any difference."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X = os.path.dirname(HERE)
d = json.load(open(os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else "FREEZE.json")))
bad = []
for p, v in d.items():
    if p == "nyc_manifest":
        for k, w in v.items():
            if hashlib.sha256(open(os.path.join(X, "data", k), "rb").read()).hexdigest() != w:
                bad.append(k)
        continue
    q = os.path.expanduser(p) if p.startswith("~") else os.path.join(X, p)
    if hashlib.sha256(open(q, "rb").read()).hexdigest() != v:
        bad.append(p)
print("frozen files differing:", bad, "of", len(d))
sys.exit(1 if bad else 0)
