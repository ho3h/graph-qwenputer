#!/usr/bin/env python3
"""exam/AFTER.md, the sealed maps: check each file against data/MANIFEST.sha256, then write each map with an empty splice list. Theo's word, 4 Nov. python3 exam/sealed_open.py"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X = os.path.dirname(HERE)
want = dict(reversed(ln.split()) for ln in open(os.path.join(X, "data", "MANIFEST.sha256")) if "/nyc-cf/" in ln or "/nyc-relabelled/" in ln)
bad = [k for k, v in want.items() if hashlib.sha256(open(os.path.join(X, "data", k), "rb").read()).hexdigest() != v]
print(len(want), "sealed files against the manifest, differing:", bad)
if bad:
    sys.exit(1)
out = os.path.join(HERE, "items", "sealed")
os.makedirs(out, exist_ok=True)
for m in ("nyc-cf", "nyc-relabelled"):
    g = json.load(open(os.path.join(X, "data", "heldout", m, m + ".graph.json")))
    g["splice"], g["name"] = [], m + "-b"
    json.dump(g, open(os.path.join(out, m + "_b.graph.json"), "w"), ensure_ascii=False, indent=1)
    print(m, len(g["nodes"]), "nodes", len(g["edges"]), "edges", len(g["relations"]), "relations")
