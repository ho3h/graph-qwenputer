"""S15's baseline: chain3's unchanged path in a process of its own, with its load counted apart. python slowrun.py --first 0 --n 6 --out results/s15_slow_a.json"""
import argparse, json, os, sys, time
t00 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import textlib as TL
import torch
C2, D = TL.C2, TL.D
ap = argparse.ArgumentParser()
ap.add_argument("--first", type=int, default=0)
ap.add_argument("--n", type=int, default=6)
ap.add_argument("--out", required=True)
a = ap.parse_args()
from chat import ExecChat
from transformers import AutoTokenizer
nq = len(AutoTokenizer.from_pretrained(TL.X.MODEL))
ec = ExecChat(os.path.expanduser("~/Models/x210/x210-rvc"))
load_s = round(time.time() - t00, 1)
print("loaded", load_s, D.mem(), flush=True)
tool = C2.chase_tool("")
saved = {}
for line in open(TL.CHAIN3):
    x = json.loads(line)
    if not x["verified_positions"]:
        saved[(x["graph"], x["id"])] = x
keys = list(saved)[a.first:a.first + a.n]
rows = []
t0 = time.time()
for k in keys:
    g, q = TL.question(saved[k])
    r = C2.run_question(ec, g, q, nq, 1800, tool, verify=False, question_handles=False, told=True, rule=False)
    s = saved[k]
    same = s["no_call_text"] == r["no_call_text"] and s["final"] == r["final"] and all(x["ids"] == y["ids"] for x, y in zip(s["calls"], r["calls"]))
    rows.append({"key": k, "same": same, "seconds": r["seconds"], "tokens": r["qwen_tokens"] + r["echo_tokens"]})
    print(rows[-1], flush=True)
    torch.mps.empty_cache()
res = {"load_seconds": load_s, "seconds": round(time.time() - t0, 1), "tokens": sum(r["tokens"] for r in rows), "same": sum(r["same"] for r in rows), "n": len(rows), "rows": rows, "shared_gpu": True, "mem": D.mem()}
res["tokens_per_s"] = round(res["tokens"] / res["seconds"], 2)
json.dump(res, open(a.out, "w"), indent=1)
