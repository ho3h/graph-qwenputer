#!/usr/bin/env python3
"""exam/AFTER.md S2's draw: d1m.draw's rule on a sealed map, gold from reflib on its blocking copy. T8_R1=1 T8_R2=1 python3 exam/sealed_q.py MAP"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(X, "lib"), os.path.join(X, "t8", "fw")]
import d1m  # noqa: E402
import noun as N  # noqa: E402
import reflib  # noqa: E402

m = sys.argv[1]
qs, pool = d1m.draw(m, 200)
g = N.with_noun(json.load(open(os.path.join(HERE, "items", "sealed", m + "_b.graph.json"))))
conv = []
for q in qs:
    gold = reflib.Graph(g).call(q["call"]["fn"], q["call"]["args"])
    src = "file" if int(q["id"]) < 900000 else "generated" if int(q["id"]) < 900200 else "shared"
    conv.append({"key": f"{m}:{q['id']}", "graph": m + "-b", "source": src, "turns": [{"user": q["text"], "gold": gold, "wants": None}]})
json.dump({"seed": f"20261103:{m}:d1m", "conversations": conv, "plain": []}, open(os.path.join(HERE, "results", "after", f"s2_{m}_draw.json"), "w"), ensure_ascii=False, indent=0)
print(m, len(conv), "questions, pool", pool, {s: sum(c["source"] == s for c in conv) for s in ("file", "generated", "shared")})
