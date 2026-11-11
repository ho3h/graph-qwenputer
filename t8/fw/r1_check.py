#!/usr/bin/env python3
"""exam/R1.md: every proof on build_r1/writes.elf, from saved results. Exit 1 on any failure."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
X = os.path.dirname(os.path.dirname(HERE))
R = os.path.join(HERE, "results", "r1")
load = lambda *p: json.load(open(os.path.join(*p)))
ok = True
def say(n, good, what):
    global ok
    ok &= bool(good)
    print(("ok  " if good else "FAIL"), n, what)
for part in ("r1", "writes", "stops", "awkward", "fuzz", "labels"):
    d = load(R, f"writes_{part}.json")
    say(part, d["mismatches_n"] == 0, d["parts"])
a, b = load(R, "writes_fuzzfw.json"), load(HERE, "results", "writes_fuzzfw.json")
ka = sorted(m["where"] for m in a["mismatches"]); kb = sorted(m["where"] for m in b["mismatches"])
say("fuzzfw", a["mismatches_n"] == b["mismatches_n"] and ka == kb, f"{a['mismatches_n']} against frozen {b['mismatches_n']}, same calls: {ka == kb}")
if os.environ.get("R1_SKIP_PROOFS") != "1":
    c = load(R, "closures.json")
    say("closures", not c["bad"] and c["units"] == 159, (c["units"], c["totals"]))
    p = load(X, "speed", "proofs.json")
    p = p if isinstance(p, list) else p.get("proofs", p)
    names = {e.get("name") for e in p} if isinstance(p, list) else set(p)
    for n in ("r1-print-writes", "r1-read-writes"):
        say(n, n in names, "in speed/proofs.json")
        q = load(R, "proofs", n[3:] + ".json")
        say(n + " result", q["questions_compared"] == 40 and q["same"] == 40 and not q["differ"] and q["stock_passed"] and q["elf_sha256"] == "ad1abcc6cec073b52e088c4d0d1752dd9908f6f77d39d950ff0d5a5e70c41fe0", (q["same"], q["questions_compared"], q["stock_positions"]))
t = load(R, "tablecheck.json")
say("tablecheck", not t.get("problems"), {k: t[k] for k in list(t)[:6] if not isinstance(t[k], (list, dict))})
m1 = load(R, "m1_writes_on", "m1_full.summary.json")
say("m1", m1["parts"] and all(v["mismatches"] == 0 for v in m1["parts"].values()), {k: (v["checks"], v["match"], v["toolong"], v["mismatches"]) for k, v in m1["parts"].items()})
sys.exit(0 if ok else 1)
