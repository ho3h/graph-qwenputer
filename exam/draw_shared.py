#!/usr/bin/env python3
"""exam/AFTER.md H: E1's conversations, closing a stop whose name is shared. python3 exam/draw_shared.py OUT"""
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
base = os.path.join(X210, "data", "heldout", "nyc", "nyc")
g = N.with_noun(json.load(open(base + ".graph.json")))
Q = sorted((q for q in json.load(open(base + ".questions.json"))["questions"] if q["orig_kind"] == "two"), key=lambda q: q["id"])
rng = random.Random("20261106:nyc:shared")
rng.shuffle(Q)
G0 = reflib.Graph(g)
shared = [i for i, n in enumerate(g["nodes"]) if len(G0.by_label[n["label"]]) > 1]


def effect(q, x):
    G = reflib.Graph(g)
    G.close(f"@{x}")
    c = q["call"]["args"]
    return G.chase(c["start"], c["legs"])


want = {True: 20, False: 20}
conv = []
for q in Q:
    if not any(want.values()):
        break
    c = q["call"]["args"]
    op = reflib.Graph(g).chase(c["start"], c["legs"])
    start = int(c["start"][1:])
    for ch in ((True, False) if want[True] else (False,)):
        hit = next((x for x in rng.sample(shared, len(shared)) if x != start and (effect(q, x) != op) == ch), None)
        if hit is not None:
            want[ch] -= 1
            i = len(conv)
            lab = g["nodes"][hit]["label"]
            conv.append({"key": f"nyc:{q['id']}", "graph": "nyc", "node": hit, "label": lab, "changed": ch, "wording": STATED[i % 10], "reopen_wording": REOPEN[i % 5], "turns": [
                {"user": STATED[i % 10].format(X=lab) + " " + q["text"], "gold": effect(q, hit), "wants": ["close", hit]},
                {"user": REOPEN[i % 5].format(X=lab) + " " + q["text"], "gold": op, "wants": ["reopen", hit]}]})
            break
assert len(conv) == 40
json.dump({"seed": 20261106, "conversations": conv, "plain": []}, open(sys.argv[1], "w"), ensure_ascii=False, indent=0)
print(len(conv), sum(c["changed"] for c in conv), flush=True)
