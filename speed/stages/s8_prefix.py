import torch; torch.set_grad_enabled(False)
import importlib, json, os, time
import numpy as np
import batchrun as BR2
importlib.reload(BR2)
from transformers import DynamicCache
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
prompts = {}
for k in keys:
    g, q = TL.question(saved[k])
    prompts[k] = TL.prompt_of(chat, g, q, tool)
lcp = None
p0 = prompts[keys[0]]
for p in prompts.values():
    n = 0
    while n < min(len(p0), len(p)) and p0[n] == p[n]:
        n += 1
    lcp = n if lcp is None else min(lcp, n)
print("common prefix across all", lcp, "prompt mean", sum(map(len, prompts.values())) / len(keys), flush=True)
KK = lcp
def run(layers, hc, cache, first):
    n = hc.shape[1]
    tp = (torch.arange(n, device="mps") + first).view(1, -1)
    pe = chat.lm.rotary_emb(hc, tp.view(1, 1, -1).expand(3, 1, -1))
    mask = torch.ones(n, first + n, dtype=torch.bool, device="mps").tril(first)[None, None]
    h = hc
    for lay, i in zip(layers, range(chat.n_chip, len(chat.lm.layers))):
        ty = chat.model.config.layer_types[i]
        h = lay(h, position_embeddings=pe, attention_mask=mask if ty == "full_attention" else None, position_ids=tp, past_key_values=cache)
    return chat.lm.norm(h)[:, -1:, :], cache
hc0 = BR2.prompt_hc(ctx, ctx.exp, p0[:KK])
_, base = run(ctx.v2_layers, hc0, DynamicCache(config=chat.model.config), 0)
base.layers[chat.n_chip].recurrent_states[0][0, 0, 0, 0].item()
def pref(ctx_, hc):
    c = TL.clone_cache(base)
    return run(ctx.v2_layers, hc[:, KK:], c, KK)
# whole against shared-prefix time, alternating on 12 prompts
T = {"whole": 0.0, "suffix": 0.0}
for k in keys[:12]:
    hc = BR2.prompt_hc(ctx, ctx.exp, prompts[k])
    hc[0, 0, 0].item()
    s = time.perf_counter(); n0, c0 = run(ctx.v2_layers, hc, DynamicCache(config=chat.model.config), 0); n0[0, 0, 0].item(); T["whole"] += time.perf_counter() - s
    s = time.perf_counter(); n1, c1 = pref(ctx, hc); n1[0, 0, 0].item(); T["suffix"] += time.perf_counter() - s
    del c0, c1
T = {k: round(v / 12, 3) for k, v in T.items()}
print("prefill mean", T, flush=True)
out = open("results/s8_prefix.jsonl", "w", buffering=1)
res = []
def done(tag, r):
    s = saved[tag]
    d = dict(n_calls=len(s["calls"]) == len(r["calls"]), ids=all(a["ids"] == b["ids"] for a, b in zip(s["calls"], r["calls"])), final=s["final"] == r["final"], status=s["status"] == r["status"], prose=s["no_call_text"] == r["no_call_text"], qwen=s["qwen_tokens"] == r["qwen_tokens"], echo=s["echo_tokens"] == r["echo_tokens"], correct=s["correct"] == r["correct"])
    res.append({"key": tag, "same": all(d.values()), **d})
    out.write(json.dumps(res[-1]) + "\n")
    print(tag, res[-1]["same"], {a: b for a, b in d.items() if not b}, flush=True)
items = [(*TL.question(saved[k]), k) for k in keys]
t0 = time.time()
st = BR2.drive(ctx, items, 8, tool, ctx.v2_layers, ctx.head_v3, tau, done, ctx.exs, ctx.exp, prefill_layers=pref)
sm = {"prefix": KK, "prefill_alternating_12": T, "n": len(res), "all_same": sum(r["same"] for r in res), "first_attempt_same": sum(r["ids"] for r in res), "final_same": sum(r["final"] for r in res), "correct_same": sum(r["correct"] for r in res), "prose_same": sum(r["prose"] for r in res), "seconds": round(time.time() - t0, 1), "stats": st, "shared_gpu": True}
json.dump(sm, open("results/s8_prefix.json", "w"), indent=1)
print(json.dumps(sm), flush=True)
