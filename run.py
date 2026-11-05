#!/usr/bin/env python3
"""Talk to the model with the graph computer running in its layers. Needs the model, a Mac with Apple silicon, and Homebrew's LLVM.

    python3 run.py --model DIR "What's the route with the fewest stops from Bedford Av to WTC Cortlandt?"
    python3 run.py --model DIR --graph examples/team.graph.json "Who does Dana report to?"

Each argument after the options is one turn of one conversation. Writes last for that conversation.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "toolkit"))
import calls as C  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--model", required=True, help="the model folder, from Hugging Face")
ap.add_argument("--graph", help="an x210-graph/1 file; New York if left out")
ap.add_argument("--examples", help="your own worked turns, a JSON file; see docs/TOOLKIT.md")
ap.add_argument("--tools", help="the calls Qwen can make, separated by commas")
ap.add_argument("--whole", action="store_true", help="run the 11 added layers on the real weights too, checking every token against the simulator: about 60 machine tokens a second")
ap.add_argument("--python", default=sys.executable, help="a Python with requirements.txt installed")
ap.add_argument("turns", nargs="+")
a = ap.parse_args()
for f in ("chipformer.json", "tokenizer.json", "model.safetensors.index.json"):
    if not os.path.exists(os.path.join(a.model, f)):
        sys.exit(f"{a.model} has no {f}. Point --model at the downloaded model folder.")
wanted, msg = C.tools_wanted(a.tools)
if msg:
    sys.exit(msg)
if a.examples:
    _, msg = C.read_examples(a.examples, wanted)
    if msg:
        sys.exit(msg)
try:
    g = json.load(open(a.graph or os.path.join(HERE, "exam", "items", "nyc_b.graph.json"), encoding="utf-8"))
except (OSError, ValueError) as e:
    sys.exit(f"Can't read {a.graph}: {e}")
err = C.problems(g)[0]
if err:
    sys.exit("\n".join(["Fix these first:"] + err[:20]))
tmp = tempfile.mkdtemp(prefix="graph-qwenputer-")
graph = os.path.join(tmp, "run.graph.json")
json.dump(C.filled(g), open(graph, "w", encoding="utf-8"), ensure_ascii=False)
draw = os.path.join(tmp, "draw.json")
turns = [{"user": t, "gold": "open", "wants": None} for t in a.turns]
json.dump({"seed": 0, "conversations": [{"key": "run:0", "graph": "run", "turns": turns}], "plain": []}, open(draw, "w"))
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.path.join(HERE, "vendor", "qwenputer-riscv"), TOK_CKPT=os.path.abspath(a.model),
           T8_NOUN="on", T8_WRITES="1", T8_R1="1", T8_R2="1", T8_R3="1", T8_R4="1", T8_R5="1", T8_R6="1", RUN_GRAPH=graph)
if a.examples:
    env["GQ_EXAMPLES"] = os.path.abspath(a.examples)
if a.tools:
    env["GQ_TOOLS"] = a.tools
out = os.path.join(tmp, "out")
log = os.path.join(tmp, "run.log")
print("Loading the model. The first run also compiles the C engine.", flush=True)
with open(log, "w") as lf:
    c = subprocess.call([a.python, "-B", os.path.join(HERE, "t8", "fw", "tokrun.py"), os.path.join(HERE, "toolkit", "ask_run.py"), "--out", out, "--draw", draw, "--set", "conversations", "--deadline-s", "14400", "--question-limit-s", "7200"] + (["--verify-first", "1"] if a.whole else []), env=env, cwd=HERE, stdout=lf, stderr=subprocess.STDOUT)
rows = os.path.join(out, "all.jsonl")
if c or not os.path.exists(rows):
    print(open(log).read()[-3000:])
    sys.exit(f"The run failed, code {c}. Full log: {log}")
r = json.loads(open(rows).readline())
for t in r["turns"]:
    print("\nYou:", t["user"])
    for k in t["calls"]:
        print("  Machine:", k["fn"], json.dumps(k["args"], ensure_ascii=False), "->", k["result"])
    print("Qwen:", (t.get("reply") or "").strip())
if a.whole:
    print(f"\nEvery token on the real weights, against the simulator: {r['verified_positions']:,} compared, {'0 differ' if not r.get('verify_mismatch') else 'a difference: ' + json.dumps(r['verify_mismatch'])}.")
if r["status"] != "answered":
    print(f"\nThe run stopped early: {r['status']}. {len(r['turns'])} of {len(a.turns)} turns ran. \"cap\" means Qwen made 12 calls, and \"budget\" means Qwen wrote 320 tokens in a turn or 3,072 in all.")
print(f"\nRan on: {r['ran_on']}. \"executor\" means the simulator ran the 11 added layers and Qwen's layers ran on the real weights. {r['chip_tokens']} machine tokens, {round(r['seconds'])} s. Rows: {rows}")
