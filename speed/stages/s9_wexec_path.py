import torch; torch.set_grad_enabled(False)
import importlib, json, os, time
import numpy as np
import batchrun as BR2
importlib.reload(BR2)
import wexec as WX
importlib.reload(WX)
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
tau = chat.meta["tau_dim"]
if not hasattr(ctx, "wx") or globals().get("WX_REBUILD"):
    t0 = time.time()
    w0 = WX.WExec(chat.c, chat.T, chat.meta)
    ctx.wx = [WX.WExec(chat.c, chat.T, chat.meta, share=w0) for _ in range(8)]
    ctx.wxp = w0
    print("wexec build", round(time.time() - t0, 1), w0.lib_hash, flush=True)
saved = {}
for line in open(TL.CHAIN3):
    x = json.loads(line)
    if not x["verified_positions"]:
        saved[(x["graph"], x["id"])] = x
keys = list(saved)[:globals().get("WX_N", 32)]
items = []
for k in keys:
    g, q = TL.question(saved[k]); items.append((g, q, k))
res = []
out = open("results/s9_wexec_path.jsonl", "w", buffering=1)
def done(tag, r):
    s = saved[tag]
    d = dict(n_calls=len(s["calls"]) == len(r["calls"]), ids=all(a["ids"] == b["ids"] for a, b in zip(s["calls"], r["calls"])), responses=all(a.get("response_ids") == b.get("response_ids") for a, b in zip(s["calls"], r["calls"])), final=s["final"] == r["final"], status=s["status"] == r["status"], prose=s["no_call_text"] == r["no_call_text"], chip=s["chip_tokens"] == r["chip_tokens"], qwen=s["qwen_tokens"] == r["qwen_tokens"], echo=s["echo_tokens"] == r["echo_tokens"])
    res.append({"key": tag, "same": all(d.values()), "d": d, "chip_seconds": r["chip_seconds"], "chip": r["chip_tokens"], "seconds": r["seconds"], "lock": r["lock_error"], "mismatch": r["verify_mismatch"]})
    out.write(json.dumps(res[-1]) + "\n")
    print(tag, res[-1]["same"], r["seconds"], r["chip_seconds"], r["chip_tokens"], flush=True)
t0 = time.time()
st = BR2.drive(ctx, items, 8, tool, ctx.v2_layers, ctx.head_v3, tau, done, ctx.wx, ctx.wxp)
sm = {"n": len(res), "same": sum(r["same"] for r in res), "seconds": round(time.time() - t0, 1), "stats": st, "chip_tokens": sum(r["chip"] for r in res), "chip_seconds": round(sum(r["chip_seconds"] for r in res), 1), "engine": ctx.wxp.lib_hash, "flags": sorted({f for w in ctx.wx for f in w.flags()}), "residue": sum(int(w.p.residue) for w in ctx.wx), "not_saturated": sum(int(w.p.not_saturated) for w in ctx.wx), "shared_gpu": True}
sm["chip_tokens_per_s"] = round(sm["chip_tokens"] / max(1e-9, sm["chip_seconds"]), 1)
json.dump(sm, open("results/s9_wexec_path.json", "w"), indent=1)
print(json.dumps(sm), flush=True)
