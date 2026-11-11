#!/usr/bin/env python3
"""Panels for the worked-turn variants (t8/REGISTRATION.md, step V): 30 stated closures in ten wordings unseen by any panel, 30 traps in ten unseen wordings. Fresh dev-city questions, seed 20261121. Writes results/wvar_draw.json."""
import glob
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
for f in ("chain_draw.json", "chain2_draw.json"):
    USED |= {tuple(k) for k in json.load(open(HERE / "results" / f))["dev"]}
for f in ("edit_draw.json", "edit2_draw.json", "edit3_draw.json"):
    d = json.load(open(HERE / "results" / f))
    for c in d.get("conversations", []) + d.get("plain", []):
        a, b = c["key"].split(":")
        USED.add((f"cities/{a}", int(b)))
for f in glob.glob(str(ROOT / "infer" / "results" / "panel*.json")):
    for q in json.load(open(f))["questions"]:
        a, b = q["key"].split(":")[:2]
        USED.add((f"cities/{a}", int(b)))
STATED = ["Engineers have taken {X} out of use.", "{X} is shut until further notice.", "Nobody can board or alight at {X} today.", "There's a gas leak at {X}, so it's been evacuated and trains run through.",
          "{X} is off limits this morning.", "The roof fell in at {X}, and it won't reopen for months.", "Service to {X} is suspended.", "{X} has been boarded up.", "A strike has shut {X}.", "Trains are running straight through {X} without calling there."]
TRAPS = ["The bakery next to {X} has closed down.", "The council is considering closing {X} in 2040.", "The library at {X} shuts at five.", "{X} closed briefly last spring, but it's been fine since.", "They said {X} might shut, but it never did.",
         "I closed my account at the bank by {X}.", "{X} is closed to cyclists but trains stop as normal.", "Is {X} ever closed on Sundays? Just wondering.", "The ticket office at {X} is shut, though the platforms are open.", "My shop at {X} is closing for the holidays."]
pool = []
for f in sorted(glob.glob(str(ROOT / "data" / "dev" / "cities" / "*.questions.json"))):
    assert "heldout" not in f
    b = os.path.basename(f).split(".")[0]
    for q in json.load(open(f))["questions"]:
        if q.get("kind") == "chase" and (f"cities/{b}", q["id"]) not in USED:
            pool.append((b, q))
rng = random.Random(20261121)
rng.shuffle(pool)
GR, out = {}, {"stated": [], "traps": []}
want = {True: 15, False: 15}
for b, q in pool:
    if not any(want.values()) and len(out["traps"]) == 30:
        break
    g = GR.setdefault(b, N.with_noun(json.load(open(ROOT / "data" / "dev" / "cities" / f"{b}.graph.json"))))
    a = q["call"]["args"]
    G = reflib.Graph(g)
    open_line = G.chase(a["start"], a["legs"])
    start = int(a["start"][1:])
    rec = {"key": f"{b}:{q['id']}", "graph": f"cities/{b}", "id": q["id"], "text0": q["text"], "call": q["call"]}
    if len(out["traps"]) < 30:
        x = next(i for i in rng.sample(range(len(g["nodes"])), len(g["nodes"])) if i != start and len(G.by_label[g["nodes"][i]["label"]]) == 1)
        w = TRAPS[len(out["traps"]) % 10]
        out["traps"].append({**rec, "node": x, "label": g["nodes"][x]["label"], "wording": w, "text": w.format(X=g["nodes"][x]["label"]) + " " + q["text"], "gold": open_line})
        continue
    for x in rng.sample(range(len(g["nodes"])), min(60, len(g["nodes"]))):
        lab = g["nodes"][x]["label"]
        if x == start or len(G.by_label[lab]) != 1:
            continue
        G2 = reflib.Graph(g)
        G2.close(f"@{x}")
        cl = G2.chase(a["start"], a["legs"])
        ch = cl != open_line
        if want[ch] and (ch or rng.random() < .2):
            w = STATED[len(out["stated"]) % 10]
            out["stated"].append({**rec, "node": x, "label": lab, "wording": w, "changed": ch, "text": w.format(X=lab) + " " + q["text"], "gold": cl, "open_line": open_line})
            want[ch] -= 1
            break
assert len(out["stated"]) == 30 and len(out["traps"]) == 30
json.dump(out, open(HERE / "results" / "wvar_draw.json", "w"), ensure_ascii=False, indent=0)
print(sum(c["changed"] for c in out["stated"]), "changed of", len(out["stated"]), "stated;", len(out["traps"]), "traps;", len({c["graph"] for c in out["stated"] + out["traps"]}), "cities")
