#!/usr/bin/env python3
"""The stated-edit test's questions: the same 50 conversations and 20 plain questions as edit_draw.json, the user turns now orders. Half, chosen by seed 20261115 within changed and unchanged, name the node with the graph's noun: "Close X station." No model."""
import hashlib
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "results", "edit_draw.json")))
rng = random.Random(20261115)
for changed in (True, False):
    keys = [c["key"] for c in d["conversations"] if c["changed"] == changed]
    pick = set(rng.sample(keys, 13 if changed else 12))
    for c in d["conversations"]:
        if c["key"] in pick:
            c["form"] = "station"
        elif "form" not in c:
            c["form"] = "name" if c["changed"] == changed else c.get("form")
for c in d["conversations"]:
    c["form"] = c.get("form") or "name"
    n = c["label"] + (" station" if c["form"] == "station" else "")
    q = c["turns"][0]["user"].split(" is closed. ", 1)[1]
    c["turns"][0]["user"] = f"Close {n}. Then: {q}"
    c["turns"][1]["user"] = f"Reopen {n}. Then: {q}"
d["seed_form"] = 20261115
s = json.dumps(d, ensure_ascii=False, indent=0)
open(os.path.join(HERE, "results", "edit2_draw.json"), "w").write(s)
from collections import Counter
print(hashlib.sha256(s.encode()).hexdigest()[:16], Counter((c["changed"], c["form"]) for c in d["conversations"]), d["conversations"][0]["turns"][0]["user"][:90])
