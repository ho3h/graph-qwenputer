import torch; torch.set_grad_enabled(False)
import json, time, sys, importlib
import numpy as np, torch.nn.functional as F
import importlib, batchrun as BR2
importlib.reload(BR2)
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
tau = chat.meta["tau_dim"]; nq = ctx.nq
saved = {}
for line in open(TL.CHAIN3):
    x = json.loads(line)
    if not x["verified_positions"]:
        saved[(x["graph"], x["id"])] = x
keys = list(saved)
def summary(k, r):
    s = saved[k]
    return {"calls": [len(s["calls"]), len(r["calls"])], "ids_eq": [a["ids"] == b["ids"] for a, b in zip(s["calls"], r["calls"])], "status": [s["status"], r["status"]], "q": [s["qwen_tokens"], r["qwen_tokens"]], "prose_eq": s["no_call_text"] == r["no_call_text"], "first_diff_prose": next((i for i, (a, b) in enumerate(zip(s["no_call_text"] or "", r["no_call_text"] or "")) if a != b), None)}
T = [("cities/c020", 230), ("random/r021", 22)]
for B, ks in ((2, T), (8, keys[:6] + T)):
    items = []
    for k in ks:
        g, q = TL.question(saved[k]); items.append((g, q, k))
    res = {}
    t0 = time.time()
    st = BR2.drive(ctx, items, B, tool, ctx.v2_layers, ctx.head_v3, tau, lambda tag, r: res.__setitem__(tag, r), ctx.exs, ctx.exp)
    print("B", B, [k for k in ks], round(time.time() - t0, 1), flush=True)
    for k in T:
        if k in res:
            print(k, json.dumps(summary(k, res[k]))[:400], flush=True)
    torch.mps.empty_cache()
