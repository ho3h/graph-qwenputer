# S1(b) by layer, S1(d) batches.
import torch; torch.set_grad_enabled(False)
import copy, json, os, time
import numpy as np, torch
import torch.nn.functional as F
from chipformer.rv import core
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
TL.build_v2(ctx)
nq = ctx.nq
OUT = {"shared_gpu": True}
r = TL.sample(1)[0]
g, q = TL.question(r)
m = D.parked_machine(g, chat.T, q.get("setup") or [])
prompt = TL.prompt_of(chat, g, q, tool)
out = chat._prefill(prompt)
base = out.past_key_values
core.snapshot(chat.c, m)
cx.p.flags = 0
ec.start(prompt)
toks = [chat.T.TCO] + r["calls"][0]["ids"] + [chat.T.TCC]
pos0 = len(prompt)
hcs = []
for nxt in toks[:24]:
    keep = cx.step(ec.stream(nxt)).copy()
    hcs.append(ec.hc(nxt, keep))
# By layer, synced after each: V0 and V2
types = chat.model.config.layer_types
def by_layer(layers, kind, steps=12):
    c = TL.clone_cache(base)
    tally = {"linear": 0.0, "full": 0.0, "rotary": 0.0, "norm": 0.0, "head": 0.0, "argmax": 0.0}
    for k in range(steps):
        h = hcs[k].view(1, 1, -1); pos = pos0 + k
        s = time.perf_counter()
        p4 = torch.full((4, 1, 1), pos, device="mps", dtype=torch.long)
        pe = chat.lm.rotary_emb(h, p4[1:]); pe[0].cpu()
        tally["rotary"] += time.perf_counter() - s
        for j, lay in enumerate(layers):
            s = time.perf_counter()
            h = lay(h, position_embeddings=pe, attention_mask=None, position_ids=p4[0], past_key_values=c)
            h[0, 0, 0].item()
            tally["linear" if types[chat.n_chip + j] == "linear_attention" else "full"] += time.perf_counter() - s
        s = time.perf_counter(); n = chat.lm.norm(h); n[0, 0, 0].item(); tally["norm"] += time.perf_counter() - s
        s = time.perf_counter()
        if kind == "V0":
            y = chat.model.lm_head(n)[0, -1][:nq]
        else:
            y = F.linear(n.index_select(-1, ctx.head_v2.cols), ctx.head_v2.W)[0, -1]
        y[0].item()
        tally["head"] += time.perf_counter() - s
        s = time.perf_counter(); int(torch.argmax(y)); tally["argmax"] += time.perf_counter() - s
    return {k2: round(v / steps, 4) for k2, v in tally.items()}
OUT["by_layer"] = {"V0": by_layer(chat.lm.layers[chat.n_chip:], "V0"), "V2": by_layer(ctx.v2_layers, "V2")}
print(json.dumps(OUT["by_layer"]), flush=True)

# Ops in one step: count how many tensor ops Python issues (a rough dispatch count), and unsynced body time
def timing_no_sync(layers, kind, steps=12):
    c = TL.clone_cache(base)
    enc, wait = 0.0, 0.0
    for k in range(steps):
        s = time.perf_counter()
        if kind == "V0":
            n = TL.qwen_body(ctx, layers, hcs[k], c, pos0 + k); y = chat.model.lm_head(n)[0, -1][:nq]
        else:
            n = TL.qwen_body(ctx, layers, hcs[k], c, pos0 + k); y = F.linear(n.index_select(-1, ctx.head_v2.cols), ctx.head_v2.W)[0, -1]
        e = time.perf_counter(); int(torch.argmax(y)); w = time.perf_counter()
        enc += e - s; wait += w - e
    return {"encode": round(enc / steps, 4), "wait": round(wait / steps, 4), "total": round((enc + wait) / steps, 4)}
OUT["no_sync"] = {"V0": timing_no_sync(chat.lm.layers[chat.n_chip:], "V0"), "V2": timing_no_sync(ctx.v2_layers, "V2")}
print(json.dumps(OUT["no_sync"]), flush=True)

# (d) Batches: B copies of the same cache and token
def batch(layers, kind, B, steps=16):
    c = TL.repeat_cache(base, B)
    tt = 0.0; rows0 = []
    for k in range(steps):
        h = hcs[k].view(1, 1, -1).repeat(B, 1, 1)
        s = time.perf_counter()
        n = TL.qwen_body(ctx, layers, h, c, pos0 + k)
        if kind == "V0":
            y = chat.model.lm_head(n)[:, -1][:, :nq]
        else:
            y = F.linear(n.index_select(-1, ctx.head_v2.cols), ctx.head_v2.W)[:, -1]
        am = torch.argmax(y, dim=-1).cpu()
        tt += time.perf_counter() - s
        rows0.append((TL.bits(y[0]), TL.bits(y[-1]), am.tolist()))
    return round(tt / steps, 4), rows0
OUT["batch"] = {}
for kind, layers in (("V0", chat.lm.layers[chat.n_chip:]), ("V2", ctx.v2_layers)):
    ref = None
    for B in (1, 2, 4, 8, 16):
        s, rows0 = batch(layers, kind, B)
        if ref is None:
            ref = rows0
        d0 = sum(int((a[0] != b[0]).sum()) for a, b in zip(ref, rows0))
        dl = sum(int((a[0] != b[1]).sum()) for a, b in zip(ref, rows0))
        am = sum(int(len(set(b[2])) > 1 or b[2][0] != a[2][0]) for a, b in zip(ref, rows0))
        OUT["batch"][f"{kind}_B{B}"] = {"s_per_step": s, "tokens_per_s": round(B / s, 1), "row0_elems_differ": d0, "rowlast_elems_differ": dl, "argmax_steps_differ": am}
        print(kind, B, json.dumps(OUT["batch"][f"{kind}_B{B}"]), flush=True)
        torch.mps.empty_cache()
json.dump(OUT, open("results/s1c_layers.json", "w"), indent=1)
print("mem", D.mem())
