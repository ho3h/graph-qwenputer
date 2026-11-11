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
out = open("results/s11c_rows.jsonl", "w", buffering=1)
meta = {"shared_gpu": True, "rounds": [], "note": "same 24 questions on both arms in each round, 8 rows first then 15, alternating which is first"}
T0 = time.time()
def run(rows, ks, tag):
    res = []
    def done(t, r):
        s = saved[t]
        same = s["no_call_text"] == r["no_call_text"] and s["final"] == r["final"] and s["status"] == r["status"] and len(s["calls"]) == len(r["calls"]) and all(a["ids"] == b["ids"] and a.get("response_ids") == b.get("response_ids") for a, b in zip(s["calls"], r["calls"])) and s["qwen_tokens"] == r["qwen_tokens"] and s["echo_tokens"] == r["echo_tokens"]
        res.append(same)
        out.write(json.dumps({"key": t, "rows": rows, "same": same, "seconds": r["seconds"]}) + "\n")
        if not same:
            print("DIFF", rows, t, flush=True)
    items = [(*TL.question(saved[k]), k) for k in ks]
    t0 = time.time()
    st = BR2.drive(ctx, items, rows, tool, ctx.v2_layers, ctx.head_v3, tau, done, ctx.exs, ctx.exp)
    d = {"rows": rows, "n": len(ks), "same": sum(res), "s": round(time.time() - t0, 1), "stats": st}
    print(json.dumps(d), flush=True)
    return d
i = 0
for rnd in range(4):
    ks = keys[i:i + 24]; i += 24
    if not ks or time.time() - T0 > 1000:
        break
    arms = (8, 15) if rnd % 2 == 0 else (15, 8)
    meta["rounds"].append([run(a, ks, rnd) for a in arms])
    json.dump(meta, open("results/s11c_rows.json", "w"), indent=1)
