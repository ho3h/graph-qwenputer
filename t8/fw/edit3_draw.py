#!/usr/bin/env python3
"""The machine test of Qwen working out the edit: 40 two-turn conversations (stated closure, then reopen) and 20 one-turn traps. Fresh dev-city questions, seed 20261118. Wordings: infer's panel4 for closures and traps (fresh there, spent now), five reopen wordings new here. No model."""
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
for c in json.load(open(HERE / "results" / "edit_draw.json"))["conversations"] + json.load(open(HERE / "results" / "edit_draw.json"))["plain"]:
    a, b = c["key"].split(":")
    USED.add((f"cities/{a}", int(b)))
P4 = json.load(open(ROOT / "infer" / "results" / "panel4.json"))["questions"]
for f in glob.glob(str(ROOT / "infer" / "results" / "panel*.json")):
    for q in json.load(open(f))["questions"]:
        a, b = q["key"].split(":")[:2]
        USED.add((f"cities/{a}", int(b)))
STATED = sorted({q["wording"] for q in P4 if q["kind"] == "stated"})
TRAPS = sorted({q["wording"] for q in P4 if q["kind"] == "distractor"})
REOPEN = ["{X} has reopened.", "{X} is open again.", "Trains are calling at {X} again.", "{X} is back in service.", "The closure at {X} has been lifted."]
pool = []
for f in sorted(glob.glob(str(ROOT / "data" / "dev" / "cities" / "*.questions.json"))):
    assert "heldout" not in f
    b = os.path.basename(f).split(".")[0]
    for q in json.load(open(f))["questions"]:
        if q.get("kind") == "chase" and (f"cities/{b}", q["id"]) not in USED:
            pool.append((b, q))
rng = random.Random(20261118)
rng.shuffle(pool)
GR, conv, traps, want = {}, [], [], {True: 20, False: 20}
for b, q in pool:
    if not any(want.values()) and len(traps) == 20:
        break
    g = GR.setdefault(b, N.with_noun(json.load(open(ROOT / "data" / "dev" / "cities" / f"{b}.graph.json"))))
    a = q["call"]["args"]
    G = reflib.Graph(g)
    open_line = G.chase(a["start"], a["legs"])
    start = int(a["start"][1:])
    if len(traps) < 20:
        x = next(i for i in rng.sample(range(len(g["nodes"])), len(g["nodes"])) if i != start and len(G.by_label[g["nodes"][i]["label"]]) == 1)
        w = TRAPS[len(traps) % len(TRAPS)]
        traps.append({"key": f"{b}:{q['id']}", "graph": f"cities/{b}", "node": x, "label": g["nodes"][x]["label"], "wording": w, "turns": [{"user": w.format(X=g["nodes"][x]["label"]) + " " + q["text"], "gold": open_line, "wants": None}]})
        continue
    for x in rng.sample(range(len(g["nodes"])), min(60, len(g["nodes"]))):
        lab = g["nodes"][x]["label"]
        if x == start or len(G.by_label[lab]) != 1:
            continue
        G2 = reflib.Graph(g)
        G2.close(f"@{x}")
        closed_line = G2.chase(a["start"], a["legs"])
        ch = closed_line != open_line
        if want[ch] and (ch or rng.random() < .2):
            want[ch] -= 1
            i = len(conv)
            conv.append({"key": f"{b}:{q['id']}", "graph": f"cities/{b}", "node": x, "label": lab, "changed": ch, "wording": STATED[i % len(STATED)], "reopen_wording": REOPEN[i % len(REOPEN)], "turns": [
                {"user": STATED[i % len(STATED)].format(X=lab) + " " + q["text"], "gold": closed_line, "wants": ("close", x)},
                {"user": REOPEN[i % len(REOPEN)].format(X=lab) + " " + q["text"], "gold": open_line, "wants": ("reopen", x)}]})
            break
assert len(conv) == 40 and len(traps) == 20
rng.shuffle(conv)
out = {"seed": 20261118, "conversations": conv, "plain": traps}
s = json.dumps(out, ensure_ascii=False, indent=0)
(HERE / "results" / "edit3_draw.json").write_text(s)
print(hashlib.sha256(s.encode()).hexdigest()[:16], STATED[:3], TRAPS[:3], conv[0]["turns"][0]["user"][:100], conv[0]["turns"][1]["user"][:60])
