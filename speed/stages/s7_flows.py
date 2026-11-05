import torch; torch.set_grad_enabled(False)
import importlib, json, os, time
import numpy as np
import batchrun as BR2
importlib.reload(BR2)
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
tau = chat.meta["tau_dim"]
saved = {}
for line in open(TL.CHAIN3):
    x = json.loads(line)
    if not x["verified_positions"]:
        saved[(x["graph"], x["id"])] = x
keys = list(saved)
FLAGS = globals().get("FLOW_FLAGS", dict(limit_stop=True, cap=320, lazy_echo=True))
NAME = globals().get("FLOW_NAME", "s7_flow")
PREF = globals().get("FLOW_PREFILL", None)
out = open(f"results/{NAME}.jsonl", "w", buffering=1)
res = []
def done(tag, r):
    s = saved[tag]
    d = {"final": s["final"] == r["final"], "correct": s["correct"] == r["correct"], "first_ids": s["calls"][0]["ids"] == (r["calls"][0]["ids"] if r["calls"] else None), "status": r["status"], "chain3_status": s["status"], "calls": len(r["calls"]), "chain3_calls": len(s["calls"]), "qwen": r["qwen_tokens"], "echo": r["echo_tokens"], "gpu": r["gpu_text_steps"], "never": r["deferred_never_ran"], "ids_prefix": all(a["ids"] == b["ids"] for a, b in zip(s["calls"], r["calls"])), "lock": r["lock_error"], "seconds": r["seconds"], "prefill": r["prefill_seconds"]}
    res.append(d)
    out.write(json.dumps({"key": tag, **d}) + "\n")
    print(tag, d["final"], d["correct"], r["status"], d["gpu"], flush=True)
items = []
for k in keys:
    g, q = TL.question(saved[k])
    items.append((g, q, k))
kw = {}
if PREF:
    kw["prefill_layers"] = PREF
t0 = time.time()
st = BR2.drive(ctx, items, 8, tool, ctx.v2_layers, ctx.head_v3, tau, done, ctx.exs, ctx.exp, **FLAGS, **kw)
sm = {"flags": {k: v for k, v in FLAGS.items()}, "n": len(res), "seconds": round(time.time() - t0, 1), "stats": st, "final_same": sum(d["final"] for d in res), "correct_same": sum(d["correct"] for d in res), "first_call_same": sum(d["first_ids"] for d in res), "ids_prefix_same": sum(d["ids_prefix"] for d in res), "gpu_text_steps": sum(d["gpu"] for d in res), "qwen": sum(d["qwen"] for d in res), "echo": sum(d["echo"] for d in res), "never_ran": sum(d["never"] for d in res), "lock_errors": sum(d["lock"] is not None for d in res), "shared_gpu": True}
json.dump(sm, open(f"results/{NAME}.json", "w"), indent=1)
print(json.dumps(sm), flush=True)
