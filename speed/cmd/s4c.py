import torch; torch.set_grad_enabled(False)
import json, time, sys, importlib
import numpy as np, torch.nn.functional as F
import batchrun as BR2
from chipformer.rv import core
from transformers.models.qwen3_5 import modeling_qwen3_5 as M
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
tau = chat.meta["tau_dim"]; nq = ctx.nq
saved = {}
for line in open(TL.CHAIN3):
    x = json.loads(line)
    if not x["verified_positions"]:
        saved[(x["graph"], x["id"])] = x
k = ("cities/c020", 230); k2 = ("random/r021", 22)
def setup(k, ex):
    g, q = TL.question(saved[k])
    prompt = TL.prompt_of(chat, g, q, tool)
    hc = BR2.prompt_hc(ctx, ctx.exp, prompt)
    nn, cache = BR2.qwen_prefill_hc(ctx, hc)
    m = D.parked_machine(g, chat.T, q.get("setup") or [])
    core.snapshot(chat.c, m); ex.p.flags = 0; ex.start([ec.stream(i) for i in prompt])
    return prompt, cache, g, q
p1, c1, g1, q1 = setup(k, ctx.exs[0])
p2, c2, g2, q2 = setup(k2, ctx.exs[1])
A = BR2.Slots(ctx, 1, tau, ctx.v2_layers, ctx.head_v3); A.install(0, c1)
Bb = BR2.Slots(ctx, 2, tau, ctx.v2_layers, ctx.head_v3); Bb.install(0, c1); Bb.install(1, c2)
toks1 = [chat.T.TCO] + saved[k]["calls"][0]["ids"] + [chat.T.TCC]
toks2 = [chat.T.TCO] + saved[k2]["calls"][0]["ids"] + [chat.T.TCC]
exA = ctx.exs[0]; ex2 = ctx.exs[1]
# a second engine for the pair's row 0 is not needed: same tokens, same keep
pos1, pos2 = len(p1), len(p2)
found = None
n = min(len(toks1), len(toks2))
for t in range(n):
    keep1 = exA.step(ec.stream(toks1[t])).copy(); b1 = BR2.hc_bits(ec, toks1[t], keep1)
    keep2 = ex2.step(ec.stream(toks2[t])).copy(); b2 = BR2.hc_bits(ec, toks2[t], keep2)
    pa = chat.lm.rotary_emb(torch.from_numpy(b1).to("mps").view(torch.bfloat16).view(1, 1, -1), torch.full((3, 1, 1), pos1, device="mps", dtype=torch.long))
    h1 = torch.from_numpy(b1).to("mps").view(torch.bfloat16).view(1, 1, -1)
    hb = torch.from_numpy(np.stack([b1, b2])).to("mps").view(torch.bfloat16).unsqueeze(1)
    pb = chat.lm.rotary_emb(hb, torch.tensor([[pos1], [pos2]], device="mps").unsqueeze(0).expand(3, -1, -1))
    d = [int((TL.bits(u[0]) != TL.bits(v[0])).sum()) for u, v in zip(pa, pb)]
    if any(d) and found is None:
        print("rotary differs", t, d, flush=True)
    for lay, i in zip(ctx.v2_layers, range(chat.n_chip, len(chat.lm.layers))):
        if chat.model.config.layer_types[i] == "linear_attention":
            h1n = A._linear(lay, i, h1, None); hbn = Bb._linear(lay, i, hb, None)
        else:
            h1n = A._full(lay, i, h1, pa, [0]); hbn = Bb._full(lay, i, hb, pb, [0, 1])
        dd = int((TL.bits(h1n[0]) != TL.bits(hbn[0])).sum())
        if dd and found is None:
            found = (t, i, dd, chat.model.config.layer_types[i])
            print("first differ: step", t, "layer", i, "elems", dd, found[3], flush=True)
            # state compare
            if found[3] == "linear_attention":
                print("state elems differ", int((A.linear[i][1][0].cpu().numpy() != Bb.linear[i][1][0].cpu().numpy()).sum()), "conv", int((TL.bits(A.linear[i][0][0]) != TL.bits(Bb.linear[i][0][0])).sum()))
            print("input h differ", int((TL.bits(h1[0]) != TL.bits(hb[0])).sum()))
            print("h1", TL.bits(h1n[0]).shape)
            ddd = np.nonzero(TL.bits(h1n[0]) != TL.bits(hbn[0]))
            print("dims", ddd[1][:20].tolist() if len(ddd) > 1 else ddd[0][:20].tolist(), h1n[0, 0, ddd[1][:6]].tolist(), hbn[0, 0, ddd[1][:6]].tolist())
            # MLP alone on the same input
            lay2 = ctx.v2_layers[i - chat.n_chip]
            xx = h1  # input to this layer before attention
            n1 = lay2.input_layernorm(h1); n2 = lay2.input_layernorm(hb)
            print("input norm differ", int((TL.bits(n1[0]) != TL.bits(n2[0])).sum()))
            break
        h1, hb = h1n, hbn
    if found:
        break
    pos1 += 1; pos2 += 1
print("found", found, "steps", n)
