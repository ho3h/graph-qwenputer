#!/usr/bin/env python3
"""exam/AFTER.md G. wordings.py build; T8_R1=1 T8_WRITES=1 T8_NOUN=on: wordings.py machine --out R --flow F --stock N --deadline-s S | host --out R.jsonl --deadline-s S"""
import json
import os
import random
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
P = os.path.join(HERE, "items", "nyc_wordings.json")
ASK = " Answer with the station name only."
WORD = {1: "one", 2: "two", 3: "three", 4: "four"}
stops = lambda k: f"{k} stop" + ("" if k == 1 else "s")
TEMPLATES = [
    lambda S, L1, D1, K1, L2, D2, K2: f"I'm at {S}. Take the {L1} {D1} for {stops(K1)}, switch to the {L2} going {D2}, and get off after {stops(K2)}. Where do I end up?",
    lambda S, L1, D1, K1, L2, D2, K2: f"From {S}, go {stops(K1)} on the {L1}, {D1}. Then transfer to the {L2} and continue {D2} for {stops(K2)}. Which station is that?",
    lambda S, L1, D1, K1, L2, D2, K2: f"Where will I be after {stops(K2)} on the {L2} {D2}, if I first ride the {L1} {D1} for {stops(K1)} from {S}?",
    lambda S, L1, D1, K1, L2, D2, K2: f"My friend boarded the {L1} at {S}, heading {D1}, and rode it for {stops(K1)}. From there they took the {L2} {D2} for {stops(K2)}. What station did they reach?",
    lambda S, L1, D1, K1, L2, D2, K2: f"Take the {L1} train {D1} from {S}. Get off {stops(K1)} later. Now board the {L2} train heading {D2}. It's {stops(K2)} from there to your stop. What's your stop?",
    lambda S, L1, D1, K1, L2, D2, K2: f"From {S}, ride the {D1} {L1} for {WORD[K1]} {'stop' if K1 == 1 else 'stops'}, then the {D2} {L2} for {WORD[K2]} {'stop' if K2 == 1 else 'stops'}. Where are you?",
    lambda S, L1, D1, K1, L2, D2, K2: f"{S} is where you begin. {L1} train, {D1}, {stops(K1)}. Change there to the {L2}, {D2}, {stops(K2)}. Final station?",
    lambda S, L1, D1, K1, L2, D2, K2: f"Two legs. First leg: {L1} {D1}, {stops(K1)}, starting at {S}. Second leg: {L2} {D2}, {stops(K2)}. Where does it end?",
    lambda S, L1, D1, K1, L2, D2, K2: f"{S}: {L1} {D1} x{K1}, then {L2} {D2} x{K2}. Where am I?",
    lambda S, L1, D1, K1, L2, D2, K2: f"Hi! I get on at {S}, going {D1} on the {L1}. {K1} later I hop on the {L2} going {D2}. {K2} after that I'm there. Where's there?",
]
mode = sys.argv[1]
if mode == "build":
    g = json.load(open(os.path.join(X210, "data", "heldout", "nyc", "nyc.graph.json")))
    Q = sorted((q for q in json.load(open(os.path.join(X210, "data", "heldout", "nyc", "nyc.questions.json")))["questions"] if q["orig_kind"] == "two"), key=lambda q: q["id"])
    rng = random.Random("20261106:nyc:w")
    which = [i for i in range(10) for _ in range(10)]
    rng.shuffle(which)
    out = []
    for q, w in zip(Q, which):
        a = q["call"]["args"]
        l1, l2 = [x.strip().rsplit(" ", 2) for x in a["legs"].split(";")]
        S = g["nodes"][int(a["start"][1:])]["label"]
        out.append(dict(q, text=TEMPLATES[w](S, l1[0], l1[1], int(l1[2]), l2[0], l2[1], int(l2[2])) + ASK, wording=w))
    json.dump(out, open(P, "w"), ensure_ascii=False, indent=0)
    print(len(out), out[0]["text"], out[3]["text"])
    sys.exit()
import d1m  # noqa: E402

qs = json.load(open(P))
argv = sys.argv[2:]
if mode == "host":
    d1m.draw = lambda name, n=100: (qs, 100)
    sys.argv = ["host.py", "--name", "nyc", "--n", "100"] + argv
    runpy.run_path(os.path.join(HERE, "host.py"), run_name="__main__")
    sys.exit()
opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
sys.path.insert(0, os.path.join(X210, "speed"))
import fast  # noqa: E402

fast.setup("writes")
gr = json.load(open(d1m.base_of("nyc") + ".graph.json"))
fl = fast.flow(opt("--flow"))
assert fast.proof(fl)
m = fast.run([(gr, q, ("nyc", q["id"])) for q in qs], fl, opt("--out"), rows=8, stock=int(opt("--stock", "0")), stock_seed=20261103, stock_limit_s=1500, deadline_s=float(opt("--deadline-s")))
print({k: m.get(k) for k in ("path", "firmware_sha256", "flow_key", "bad", "tokens")}, flush=True)
