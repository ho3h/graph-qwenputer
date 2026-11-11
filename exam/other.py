#!/usr/bin/env python3
"""exam/AFTER.md A and C. T8_R1=1, T8_WRITES=1, T8_NOUN=on.

    python exam/other.py machine --out R --flow print-writes|read-writes --stock 4 --deadline-s S
    python exam/other.py host --out R.jsonl --deadline-s S
    python exam/other.py stops --out R --deadline-s S
"""
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import d1m  # noqa: E402

ORIG = d1m.draw
mode, argv = sys.argv[1], sys.argv[2:]
Q = json.load(open(d1m.base_of("nyc") + ".questions.json"))["questions"]
others = sorted((q for q in Q if q["orig_kind"] != "two"), key=lambda q: q["id"])
assert len(others) == 300
if mode == "host":
    d1m.draw = lambda name, n=300: (others, 300)
    sys.argv = ["host.py", "--name", "nyc", "--n", "300"] + argv
    runpy.run_path(os.path.join(HERE, "host.py"), run_name="__main__")
    sys.exit()
opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
sys.path.insert(0, os.path.join(X210, "speed"))
import fast  # noqa: E402

fast.setup("writes")
gr = json.load(open(d1m.base_of("nyc") + ".graph.json"))
if mode == "stops":
    qs = [dict(q, text=q["text"].replace(" Answer with the station name only.", "")) for q in ORIG("nyc", 200)[0] if q["answer_text"].startswith("Stopped") or "Stopped" in q["answer_text"]]
    assert all("station name only" not in q["text"] for q in qs)
    print(len(qs), "stop-line questions", flush=True)
    fl, stock = fast.flow("read-writes"), 0
else:
    qs, fl, stock = others, fast.flow(opt("--flow")), int(opt("--stock", "0"))
assert fast.proof(fl), "the flow has its proof"
m = fast.run([(gr, q, ("nyc", q["id"])) for q in qs], fl, opt("--out"), rows=8, stock=stock, stock_seed=20261103, stock_limit_s=1500, deadline_s=float(opt("--deadline-s")))
print({k: m.get(k) for k in ("path", "ran_on", "firmware_sha256", "flow_key", "bad", "tokens")}, flush=True)
