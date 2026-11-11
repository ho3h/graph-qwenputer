import torch; torch.set_grad_enabled(False)
import importlib, json, sys, time
import numpy as np, torch.nn.functional as F
import batchrun as BR2
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
TL.build_v2(ctx)
tau = chat.meta["tau_dim"]
nq = ctx.nq
if not hasattr(ctx, "head_v3"):
    ctx.head_v3 = chat.model.lm_head.weight[:nq, :tau + 1].contiguous()
if not hasattr(ctx, "exp"):
    ctx.exp = BR2.make_engines(ctx, 1)[0]
from transformers import DynamicCache
def pre(layers, hc):
    n = hc.shape[1]
    cache = DynamicCache(config=chat.model.config)
    tp = torch.arange(n, device="mps").view(1, -1)
    pe = chat.lm.rotary_emb(hc, tp.view(1, 1, -1).expand(3, 1, -1))
    mask = torch.ones(n, n, dtype=torch.bool, device="mps").tril(0)[None, None]
    h = hc
    for lay, i in zip(layers, range(chat.n_chip, len(chat.lm.layers))):
        ty = chat.model.config.layer_types[i]
        h = lay(h, position_embeddings=pe, attention_mask=mask if ty == "full_attention" else None, position_ids=tp, past_key_values=cache)
    return chat.lm.norm(h)[:, -1:, :], cache
rows = TL.sample(4)
out = []
for r in rows:
    g, q = TL.question(r)
    prompt = TL.prompt_of(chat, g, q, tool)
    hc = BR2.prompt_hc(ctx, ctx.exp, prompt)
    hc[0, 0, 0].item()
    t = {"graph": r["graph"], "id": r["id"]}
    s = time.perf_counter(); n0, c0 = pre(chat.lm.layers[chat.n_chip:], hc); y0 = chat.model.lm_head(n0)[0, -1][:nq]; b0 = TL.bits(y0); t["dense_s"] = round(time.perf_counter() - s, 3)
    s = time.perf_counter(); n1, c1 = pre(ctx.v2_layers, hc); y1 = F.linear(n1[..., :tau + 1], ctx.head_v3)[0, -1]; b1 = TL.bits(y1); t["block_s"] = round(time.perf_counter() - s, 3)
    t["logit_elems_differ"] = int((b0 != b1).sum()); t["argmax_same"] = bool(y0.argmax() == y1.argmax())
    a, b = TL.state_bits(c0, chat.n_chip), TL.state_bits(c1, chat.n_chip)
    t["states_differ"] = sum(x != y for x, y in zip(a, b))
    print(json.dumps(t), flush=True)
    out.append(t)
    del c0, c1
json.dump(out, open("results/s4a_prefill.json", "w"), indent=1)
