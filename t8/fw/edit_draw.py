#!/usr/bin/env python3
"""The Qwen-written edit arm's questions. No model. Reads data/dev only. Writes t8/fw/results/edit_draw.json.
Seed 20261114. 50 conversations on dev cities, two turns each: "X is closed. <chase question>", then "X has reopened. <same question>". 25 where closing X changes the gold line and 25 where it doesn't. X is never the start. 20 plain questions with the same tools, where any write is unasked. None used by chain3, chain4, ctrl arm 4, qw2's t0_300, t8's panels or F3's draw."""
import glob
import hashlib
import json
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path[:0] = [str(HERE), str(ROOT / "lib")]
import reflib  # noqa: E402
import noun as N  # noqa: E402

USED = {("cities/c024", i) for i in (0, 1, 100, 101, 200, 201)} | {("cities/c025", i) for i in (0, 1, 100, 101, 200, 201)}
for p in ("rvc/results/chain3_draw.json", "rvc/results/chain4_draw.json", "ctrl/results/arm4_draw.json"):
    USED |= {tuple(k) for k in json.load(open(ROOT / p))["draw"]}
for ln in open(ROOT / "qw2" / "dev" / "t0_300.jsonl"):
    a, b = json.loads(ln)["id"].split(":")
    USED.add((f"cities/{a}", int(b)))
for name in ("easy", "nomatch"):
    for q in json.load(open(ROOT / "t8" / "results" / "panels.json"))[name]:
        a, b = q["key"].split(":")[:2]
        USED.add((f"cities/{a}", int(b)))
USED |= {tuple(k) for k in json.load(open(HERE / "results" / "chain_draw.json"))["dev"]}
pool = []
for f in sorted(glob.glob(str(ROOT / "data" / "dev" / "cities" / "*.questions.json"))):
    assert "heldout" not in f
    b = os.path.basename(f).split(".")[0]
    for q in json.load(open(f))["questions"]:
        if q.get("kind") == "chase" and (f"cities/{b}", q["id"]) not in USED:
            pool.append((b, q))
rng = random.Random(20261114)
rng.shuffle(pool)
GR = {}
conv, want = [], {True: 25, False: 25}
plain = []
for b, q in pool:
    g = GR.setdefault(b, N.with_noun(json.load(open(ROOT / "data" / "dev" / "cities" / f"{b}.graph.json"))))
    a = q["call"]["args"]
    G = reflib.Graph(g)
    open_line = G.chase(a["start"], a["legs"])
    if open_line != q["answer_text"] and open_line != reflib.reword(q["answer_text"]):
        raise SystemExit(("gold", b, q["id"]))
    if len(plain) < 20:
        plain.append({"key": f"{b}:{q['id']}", "graph": f"cities/{b}", "turns": [{"user": q["text"], "gold": open_line, "wants": None}]})
        continue
    if not any(want.values()):
        break
    start = int(a["start"][1:])
    # candidates: unique labels; those on the walk first by trying each
    order = rng.sample(range(len(g["nodes"])), min(60, len(g["nodes"])))
    for x in order:
        lab = g["nodes"][x]["label"]
        if x == start or len(G.by_label[lab]) != 1:
            continue
        G2 = reflib.Graph(g)
        G2.close(f"@{x}")
        closed_line = G2.chase(a["start"], a["legs"])
        changed = closed_line != open_line
        if want[changed] and (changed or rng.random() < .2):
            want[changed] -= 1
            conv.append({"key": f"{b}:{q['id']}", "graph": f"cities/{b}", "node": x, "label": lab, "changed": changed, "turns": [
                {"user": f"{lab} is closed. {q['text']}", "gold": closed_line, "wants": ("close", x)},
                {"user": f"{lab} has reopened. {q['text']}", "gold": open_line, "wants": ("reopen", x)}]})
            break
assert len(conv) == 50 and len(plain) == 20, (len(conv), len(plain))
rng.shuffle(conv)
out = {"seed": 20261114, "conversations": conv, "plain": plain}
s = json.dumps(out, ensure_ascii=False, indent=0)
(HERE / "results" / "edit_draw.json").write_text(s)
print(hashlib.sha256(s.encode()).hexdigest()[:16], sum(c["changed"] for c in conv), conv[0]["turns"][0]["user"][:110], conv[0]["turns"][0]["gold"], conv[0]["turns"][1]["gold"])
