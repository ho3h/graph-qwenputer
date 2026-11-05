"""S15: a cold process with blocks only. Chain3's flow, then S7's, on the 98 questions, against chain3's saved tokens.

    python fastrun.py --dir BLOCKS --out results/s15_fast.json
"""
import argparse, json, os, sys, time
t00 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blocks as BL
import torch
torch.set_grad_enabled(False)
import batchrun as BR2
TL = BL.TL
ap = argparse.ArgumentParser()
ap.add_argument("--dir", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--n", type=int, default=98)
a = ap.parse_args()
ctx = BL.load(a.dir)
res = {"load_seconds": round(time.time() - t00, 1), "phases": ctx.load_phases, "mem": TL.D.mem(), "shared_gpu": True, "runs": []}
print(json.dumps(res), flush=True)
ec, chat = ctx.ec, ctx.ec.chat
C2 = TL.C2
tool = C2.chase_tool("")
exs = BR2.make_engines(ctx, 9)
exp = exs.pop()
saved = {}
for line in open(TL.CHAIN3):
    x = json.loads(line)
    if not x["verified_positions"]:
        saved[(x["graph"], x["id"])] = x
keys = list(saved)[:a.n]
items = [(*TL.question(saved[k]), k) for k in keys]
out = open(a.out.replace(".json", ".jsonl"), "w", buffering=1)
for name, flags in (("chain3 flow", {}), ("S7 flow", dict(limit_stop=True, cap=320, lazy_echo=True))):
    rs = []
    def done(tag, r):
        s = saved[tag]
        same = s["no_call_text"] == r["no_call_text"] and s["final"] == r["final"] and s["status"] == r["status"] and len(s["calls"]) == len(r["calls"]) and all(x["ids"] == y["ids"] and x.get("response_ids") == y.get("response_ids") for x, y in zip(s["calls"], r["calls"])) and s["qwen_tokens"] == r["qwen_tokens"] and s["echo_tokens"] == r["echo_tokens"]
        rec = {"flow": name, "key": tag, "same_all": same, "same_final": s["final"] == r["final"], "same_correct": s["correct"] == r["correct"], "gpu": r["gpu_text_steps"], "lock": r["lock_error"], "seconds": r["seconds"]}
        rs.append(rec)
        out.write(json.dumps(rec) + "\n")
    t0 = time.time()
    st = BR2.drive(ctx, items, 8, tool, ctx.layers, ctx.head, ctx.tau, done, exs, exp, **flags)
    res["runs"].append({"flow": name, "n": len(rs), "seconds": round(time.time() - t0, 1), "stats": st, "same_all": sum(r["same_all"] for r in rs), "same_final": sum(r["same_final"] for r in rs), "same_correct": sum(r["same_correct"] for r in rs), "gpu_steps": sum(r["gpu"] for r in rs), "lock_errors": sum(r["lock"] is not None for r in rs), "mem": TL.D.mem()})
    print(json.dumps(res["runs"][-1]), flush=True)
    json.dump(res, open(a.out, "w"), indent=1)
    torch.mps.empty_cache()
