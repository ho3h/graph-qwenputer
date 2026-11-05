#!/usr/bin/env python3
"""exam/AFTER.md T2: runs the stranger's spec through gq.py ask, machine on the simulator, one GPU process. python3 exam/t2_run.py REPO MODEL PYTHON"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "results", "after", "t2")
repo, model, py = sys.argv[1:4]
spec = json.load(open(os.path.join(R, "spec.json")))
rows = os.path.join(R, "rows")
os.makedirs(rows, exist_ok=True)
for c in spec["conversations"]:
    cmd = [py, "gq.py", "ask", os.path.join(R, c["graph_file"]), "--model", model, "--python", py, "--examples", os.path.join(R, c["examples_file"]), "--tools", c["tools"]] + [t["user"] for t in c["turns"]]
    p = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=600)
    open(os.path.join(R, c["id"] + ".txt"), "w").write(p.stdout + p.stderr)
    m = re.search(r"Rows: (\S+)", p.stdout)
    if m:
        shutil.copy(m.group(1), os.path.join(rows, c["id"] + ".jsonl"))
    print(c["id"], "code", p.returncode, "rows" if m else "NO ROWS", flush=True)
