#!/usr/bin/env python3
"""The fresh draws for the whole-chain run. No model. Reads data/dev and ci/pool/ci.jsonl only. Writes t8/fw/results/chain_draw.json.
dev: seed 20261112, 70 cities and 30 random chases, none of chain3's, chain4's, ctrl arm 4's, qw2's t0_300, t8's easy and name-probe panels, rb/'s, nor r092, r096, r097, r099-style graphs that don't fit.
hard: seed 20261113, 100 from pool 1, 5 per shape, none of t8's hard panel. Real start and legs fields, chain3's prompt, as t8's hard panel.
"""
import glob
import hashlib
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(ROOT / "lib"), str(ROOT / "ci")]
from score_word import gold_of, graph_of  # noqa: E402

USED = {("cities/c024", i) for i in (0, 1, 100, 101, 200, 201)} | {("cities/c025", i) for i in (0, 1, 100, 101, 200, 201)} | {("random/r001", 17)}
for p in ("rvc/results/chain3_draw.json", "rvc/results/chain4_draw.json", "ctrl/results/arm4_draw.json"):
    USED |= {tuple(k) for k in json.load(open(ROOT / p))["draw"]}
for ln in open(ROOT / "qw2" / "dev" / "t0_300.jsonl"):
    a, b = json.loads(ln)["id"].split(":")
    USED.add((f"cities/{a}", int(b)))
P = json.load(open(ROOT / "t8" / "results" / "panels.json"))
for name in ("easy", "nomatch"):
    for q in P[name]:
        a, b = q["key"].split(":")[:2]
        USED.add((f"cities/{a}", int(b)))
TOOBIG = {"r092", "r096", "r097", "r099"}
pool = {"cities": [], "random": []}
for f in sorted(glob.glob(str(ROOT / "data" / "dev" / "*" / "*.questions.json"))):
    assert "heldout" not in f
    s, b = f.split(os.sep)[-2], os.path.basename(f).split(".")[0]
    if b in TOOBIG:
        continue
    for q in json.load(open(f))["questions"]:
        if q.get("kind") == "chase" and (f"{s}/{b}", q["id"]) not in USED:
            pool[s].append((f"{s}/{b}", q["id"]))
rng = random.Random(20261112)
dev = rng.sample(pool["cities"], 70) + rng.sample(pool["random"], 30)
rng.shuffle(dev)
spent = {q["key"] for q in P["hard"]}
byf = defaultdict(list)
for ln in open(ROOT / "ci" / "pool" / "ci.jsonl"):
    q = json.loads(ln)
    if f"{q['graph']}:{q['id']}" not in spent and q["graph"] not in TOOBIG:
        byf[q["frame"]].append(q)
rng = random.Random(20261113)
hard = []
for f in sorted(byf):
    for q in rng.sample(byf[f], 5):
        g = graph_of(q["graph"])
        start, legs = gold_of(q)
        line = g.chase(g.fmt(start) if isinstance(start, int) else start, "; ".join(f"{r} {k}" for r, k in legs))
        hard.append({"key": f"{q['graph']}:{q['id']}", "graph": q["graph"], "shape": q["frame"], "text": q["text"], "start": f"@{start}" if isinstance(start, int) else start, "start_label": g.labels[start] if isinstance(start, int) else start, "legs": [[r, k] for r, k in legs], "gold_line": line})
rng.shuffle(hard)
out = {"seeds": {"dev": 20261112, "hard": 20261113}, "pool": {k: len(v) for k, v in pool.items()}, "dev": dev, "hard": hard}
s = json.dumps(out, ensure_ascii=False, indent=0)
(HERE / "results" / "chain_draw.json").write_text(s)
print(hashlib.sha256(s.encode()).hexdigest()[:16], out["pool"], len(dev), len(hard))
