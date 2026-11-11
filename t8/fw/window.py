#!/usr/bin/env python3
"""How often a chase with a closed field overflows the 80-token capture window, by leg count, on every dev chase's canonical call with a seeded closed name, and on t8's hard panel's legs. No machine, no model: the tokenizer and rvc/box.py's capture rule. Writes results/window.json."""
import glob
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fwb as W  # noqa: E402

M, X = W.M, W.X
M.init_worker()
W.O.set_text(M.T)
T = M.T
rng = random.Random(20261116)
tab = defaultdict(lambda: {"calls": 0, "long": 0, "tokens": 0, "max": 0})


def one(kind, fn_args):
    n = len(T.encode(X.template_text("chase", fn_args)))
    d = tab[kind]
    d["calls"] += 1
    d["tokens"] += n
    d["max"] = max(d["max"], n)
    d["long"] += n > 80


for p in sorted(glob.glob(os.path.join(W.X210, "data", "dev", "*", "*.questions.json"))):
    if "heldout" in p:
        continue
    g = json.load(open(p.replace(".questions.json", ".graph.json")))
    L = [n["label"] for n in g["nodes"]]
    for x in json.load(open(p))["questions"]:
        if x.get("kind") != "chase":
            continue
        a = x["call"]["args"]
        k = len(a["legs"].split(";"))
        lab = L[int(a["start"][1:])] if a["start"].startswith("@") else a["start"]
        side = "cities" if os.sep + "cities" + os.sep in p else "random"
        one(f"{side} {k} legs, start by name, no field", {"start": lab, "legs": a["legs"]})
        one(f"{side} {k} legs, start by name, closed", {"start": lab, "legs": a["legs"], "closed": rng.choice(L)})
for q in json.load(open(os.path.join(W.X210, "t8", "results", "panels.json")))["hard"]:
    g = json.load(open(os.path.join(W.X210, "data", "dev", "cities" if q["graph"].startswith("c") else "random", q["graph"] + ".graph.json")))
    k = len(q["legs"])
    legs = "; ".join(f"{r} {n}" for r, n in q["legs"])
    one(f"hard panel {k} legs, no field", {"start": q["start_label"], "legs": legs})
    one(f"hard panel {k} legs, closed", {"start": q["start_label"], "legs": legs, "closed": rng.choice([n["label"] for n in g["nodes"]])})
out = {k: dict(v, mean=round(v["tokens"] / v["calls"], 1)) for k, v in sorted(tab.items())}
json.dump(out, open(os.path.join(HERE, "results", "window.json"), "w"), indent=1)
for k, v in out.items():
    print(k, v["calls"], "over 80:", v["long"], "mean", v["mean"], "max", v["max"])
