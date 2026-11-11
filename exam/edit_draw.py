#!/usr/bin/env python3
"""E1, the launch item: Qwen writes the edit itself on the frozen flow. 40 two-turn conversations (a stated closure, then a reopen) and 30 one-turn traps, 15 of them on the question's own route, so a false close would move the answer. Wordings no panel has used. Seed 20261104. New York only after exam/FROZEN.

    python3 exam/edit_draw.py --name nyc --out exam/results/nyc_edit_draw.json
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(X210, "lib"), os.path.join(X210, "t8", "fw")]
import noun as N  # noqa: E402
import reflib  # noqa: E402

STATED = ["{X} is out of action today.", "Flooding has closed {X}.", "No trains are calling at {X} right now.", "A signal failure means {X} is being skipped.", "{X} has been taken out of service for repairs.",
          "They've shut {X} after a fire.", "You can't get on or off at {X} this week.", "Trains won't stop at {X} until Friday.", "{X} is closed for track work.", "Crews have closed off {X} overnight."]
REOPEN = ["{X} is open again now.", "Repairs are done and {X} is back.", "Trains are stopping at {X} once more.", "{X} has been reopened.", "Service at {X} has resumed."]
TRAPS = ["The newsstand at {X} has closed for good.", "The elevator at {X} is out of order, but trains still stop there.", "The coffee cart outside {X} shut down last month.", "{X} was closed in 1998 and reopened in 2001.", "There's talk of shutting {X} some day.",
         "My office near {X} is closed on Mondays.", "The museum by {X} closes at six.", "One entrance at {X} is closed, but the station is open.", "Is it true they might close {X}? I doubt it.", "The pharmacy at {X} went out of business."]

ap = argparse.ArgumentParser()
ap.add_argument("--name", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--conv", type=int, default=40)
ap.add_argument("--traps", type=int, default=30)
a = ap.parse_args()
if a.name == "nyc":
    assert os.path.exists(os.path.join(HERE, "FROZEN"))
    base, gname = os.path.join(X210, "data", "heldout", "nyc", "nyc"), "nyc"
elif a.name in ("nyc-cf", "nyc-relabelled"):                       # exam/AFTER.md, the sealed maps, on their blocking copies
    base, gname = os.path.join(X210, "data", "heldout", a.name, a.name), a.name + "-b"
else:
    base, gname = os.path.join(X210, "data", "dev", "cities", a.name), f"cities/{a.name}"
g = N.with_noun(json.load(open(os.path.join(HERE, "items", "sealed", a.name + "_b.graph.json") if gname.endswith("-b") else base + ".graph.json")))
Q = [q for q in json.load(open(base + ".questions.json"))["questions"] if q.get("kind") == "chase" and not q.get("setup") and q["call"]["args"]["legs"].count(";") == 1]
Q.sort(key=lambda q: q["id"])
rng = random.Random(f"20261104:{a.name}" + (":r1" if os.environ.get("T8_R1") == "1" else ""))
rng.shuffle(Q)
G0 = reflib.Graph(g)
uniq = [i for i, n in enumerate(g["nodes"]) if len(G0.by_label[n["label"]]) == 1]
want = {True: a.conv // 2, False: a.conv - a.conv // 2}
tw = {True: a.traps // 2, False: a.traps - a.traps // 2}
conv, traps = [], []


def effect(q, x):
    G = reflib.Graph(g)
    G.close(f"@{x}")
    c = q["call"]["args"]
    return G.chase(c["start"], c["legs"])


for q in Q:
    if not any(want.values()) and not any(tw.values()):
        break
    c = q["call"]["args"]
    open_line = reflib.Graph(g).chase(c["start"], c["legs"])
    start = int(c["start"][1:])
    cands = [x for x in rng.sample(uniq, len(uniq)) if x != start]
    if any(tw.values()) and (len(traps) <= len(conv) or not any(want.values())):
        pick = None
        for ch in ((True, False) if tw[True] else (False,)):
            for x in cands[:400]:
                if (effect(q, x) != open_line) == ch and tw[ch]:
                    pick = (x, ch)
                    break
            if pick:
                break
        if pick:
            x, ch = pick
            tw[ch] -= 1
            w = TRAPS[len(traps) % len(TRAPS)]
            lab = g["nodes"][x]["label"]
            traps.append({"key": f"{a.name}:{q['id']}", "graph": gname, "node": x, "label": lab, "wording": w, "on_route": ch, "turns": [{"user": w.format(X=lab) + " " + q["text"], "gold": open_line, "wants": None}]})
        continue
    for ch in ((True, False) if want[True] else (False,)):
        hit = None
        for x in cands[:400]:
            if (effect(q, x) != open_line) == ch and want[ch]:
                hit = x
                break
        if hit is not None:
            want[ch] -= 1
            i = len(conv)
            lab = g["nodes"][hit]["label"]
            conv.append({"key": f"{a.name}:{q['id']}", "graph": gname, "node": hit, "label": lab, "changed": ch, "wording": STATED[i % 10], "reopen_wording": REOPEN[i % 5], "turns": [
                {"user": STATED[i % 10].format(X=lab) + " " + q["text"], "gold": effect(q, hit), "wants": ["close", hit]},
                {"user": REOPEN[i % 5].format(X=lab) + " " + q["text"], "gold": open_line, "wants": ["reopen", hit]}]})
            break
assert len(conv) == a.conv and len(traps) == a.traps, (len(conv), len(traps))
json.dump({"seed": 20261104, "conversations": conv, "plain": traps}, open(a.out, "w"), ensure_ascii=False, indent=0)
print(len(conv), sum(c["changed"] for c in conv), len(traps), sum(t["on_route"] for t in traps), flush=True)
