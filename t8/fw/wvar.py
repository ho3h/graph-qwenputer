#!/usr/bin/env python3
"""Worked-turn variants on writes.elf, print mode (t8/REGISTRATION.md, step V). Replaces worked.HISTORY in this process only: worked.py and the frozen flow are unchanged. Forced fast: no fast proof for a variant, and the results say so.

    python t8/fw/wvar.py --arm base|r --panel edits|hard1|hard2|easy1|easy2 --mode print|read --out DIR --deadline-s S
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(X210, "speed"))
import fast  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--arm", required=True, choices=["base", "r"])
ap.add_argument("--panel", required=True, choices=["edits", "hard1", "hard2", "easy1", "easy2"])
ap.add_argument("--mode", default="print", choices=["print", "read"])
ap.add_argument("--out", required=True)
ap.add_argument("--deadline-s", type=float, required=True)
a = ap.parse_args()
g = fast.setup("writes")
W = g.worked
Q = W._q
hist = json.loads(json.dumps(W.HISTORY))
if a.arm == "r":          # one redraft: a bracketed name, a two-leg call on another line, a trap with no write, a limit line said as one
    T = W._turn
    hist = (T("Trains aren't stopping at Elm Sq this week. Start at Ash Rd station. Ride the K train 2 stops northbound." + Q, {"start": "Ash Rd", "legs": "K northbound 2", "closed": "Elm Sq"}, "closed @7 Elm Sq\n@9 Birch Av (9 St)", "Birch Av (9 St)")
            + T("Oak Av has a burst pipe and nobody can get in. Start at Birch Av (9 St) station. Ride the K train 1 stop southbound, then change to the 4 and ride the 4 train 2 stops eastbound." + Q, {"start": "Birch Av (9 St)", "legs": "K southbound 1; 4 eastbound 2", "closed": "Oak Av"}, "closed @5 Oak Av\n@12 Mill Ln", "Mill Ln")
            + T("The cafe at Oak Av has shut, they may close Pine St next year, and my sister lives near Pine St. Start at Ash Rd station. Ride the K train 1 stop northbound." + Q, {"start": "Ash Rd", "legs": "K northbound 1"}, "@7 Elm Sq", "Elm Sq")
            + T("Start at Pine St station. Ride the 4 train 5 stops eastbound." + Q, {"start": "Pine St", "legs": "4 eastbound 5"}, "Stopped early on leg 1: after 2 steps at @12 Mill Ln, no further step along this relation exists. The journey did not finish.", "The journey stopped early at Mill Ln, after 2 of the 5 stops. It did not finish.")
            + T("Good news, Oak Av is running again. Start at Birch Av (9 St) station. Ride the K train 1 stop southbound." + Q, {"start": "Birch Av (9 St)", "legs": "K southbound 1", "reopened": "Oak Av"}, "reopened @5 Oak Av\n@5 Oak Av", "Oak Av"))
W.HISTORY = hist
sha = hashlib.sha256(json.dumps(hist, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
d = json.load(open(os.path.join(HERE, "results", "wvar_draw.json")))
its = []
if a.panel == "edits":
    for k in ("stated", "traps"):
        for c in d[k]:
            sub, b = c["graph"].split("/")
            gr = json.load(open(os.path.join(X210, "data", "dev", sub, b + ".graph.json")))
            qq = {"id": c["id"], "kind": "chase", "text": c["text"], "call": c["call"]}
            its.append((gr, qq, (f"{sub}/{b}", c["id"], k)))
elif a.panel.startswith("easy"):
    its = fast.items([tuple(k) for k in json.load(open(os.path.join(HERE, "results", {"easy1": "chain_draw.json", "easy2": "chain2_draw.json"}[a.panel])))["dev"]])
else:
    for q in json.load(open(os.path.join(HERE, "results", {"hard1": "chain_draw.json", "hard2": "chain2_draw.json"}[a.panel])))["hard"]:
        sub = "cities" if q["graph"].startswith("c") else "random"
        gr = json.load(open(os.path.join(X210, "data", "dev", sub, q["graph"] + ".graph.json")))
        i = int(q["key"].split(":")[1])
        qq = {"id": i, "kind": "chase", "text": q["text"], "call": {"fn": "chase", "args": {"start": q["start"], "legs": "; ".join(f"{r} {k}" for r, k in q["legs"])}}, "answer": [int(q["gold_line"].split()[0][1:])] if q["gold_line"].startswith("@") else [], "answer_text": q["gold_line"]}
        its.append((gr, qq, (f"{sub}/{q['graph']}", i)))
m = fast.run(its, fast.flow(a.mode + "-writes"), a.out, rows=8, stock=0, force="fast", deadline_s=a.deadline_s)
json.dump({"arm": a.arm, "panel": a.panel, "mode": a.mode, "history_sha256": sha, "unproven": "a variant prompt has no same-token proof; fast path, forced", "questions": len(its)}, open(os.path.join(a.out, "variant.json"), "w"), indent=0)
print({k: m.get(k) for k in ("path", "firmware_sha256", "flow_key", "bad")}, flush=True)
