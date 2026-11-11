#!/usr/bin/env python3
"""Does lib/reflib.py behave exactly as before on a graph with no noun field? The commit before the cleaner against the working file, on every dev graph's questions and setups, on every label, and on cleaner-shaped names that must stay NONE. No model. Writes results/check_reflib.json. Exit 1 on any difference."""
import glob
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
old = subprocess.run(["git", "show", "d765b77c65:xseries/X2.10/lib/reflib.py"], cwd=X210, capture_output=True, text=True, check=True).stdout
path = os.path.join(HERE, "results", "reflib_before.py")
open(path, "w").write(old)


def load(name, p):
    s = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


A, B = load("ra", path), load("rb", os.path.join(X210, "lib", "reflib.py"))
n, bad = 0, []
for gp in sorted(glob.glob(os.path.join(X210, "data", "dev", "*", "*.graph.json"))):
    assert "heldout" not in gp
    g = json.load(open(gp))
    assert "noun" not in g
    a, b = A.Graph(g), B.Graph(g)
    for x in json.load(open(gp.replace(".graph.json", ".questions.json")))["questions"]:
        a2, b2 = (A.Graph(g), B.Graph(g)) if x.get("setup") or x["call"]["fn"] in ("close", "reopen", "link", "unlink") else (a, b)
        for s in (x.get("setup") or []) + [x["call"]]:
            n += 1
            ra, rb = a2.call(s["fn"], s["args"]), b2.call(s["fn"], s["args"])
            if ra != rb:
                bad.append([os.path.basename(gp), s, ra, rb])
    for lab in sorted({m["label"] for m in g["nodes"]}):
        for name in (lab, lab + ".", lab + " station", lab + " station.", "Out of " + lab):
            n += 1
            ra, rb = a.call("find", {"name": name}), b.call("find", {"name": name})
            ra2, rb2 = a.call("chase", {"start": name, "legs": f"{g['relations'][0]} 1"}), b.chase(name, f"{g['relations'][0]} 1")
            n += 1
            if ra != rb or ra2 != rb2:
                bad.append([os.path.basename(gp), name, ra, rb, ra2, rb2])
json.dump({"calls": n, "differ": len(bad), "first": bad[:20]}, open(os.path.join(HERE, "results", "check_reflib.json"), "w"), indent=1, ensure_ascii=False)
print(n, "calls,", len(bad), "differ", bad[:3])
sys.exit(1 if bad else 0)
