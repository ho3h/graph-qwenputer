import torch; torch.set_grad_enabled(False)
import importlib, json, os, time
import numpy as np
import torch.nn.functional as F
import batchrun as BR2
importlib.reload(BR2)
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
tau = chat.meta["tau_dim"]
head = ctx.head_v3
OUT = {"shared_gpu": True}
# (a) real normed vectors from one question's first 30 steps
saved = {}
for line in open(TL.CHAIN3):
    x = json.loads(line)
    if not x["verified_positions"]:
        saved[(x["graph"], x["id"])] = x
keys = list(saved)
vecs = []
for k in keys[:15]:
    g, q = TL.question(saved[k])
    p = TL.prompt_of(chat, g, q, tool)
    hc = BR2.prompt_hc(ctx, ctx.exp, p)
    nn, c = BR2.qwen_prefill_hc(ctx, hc)
    vecs.append(nn.detach())
    del c
V = torch.cat(vecs)
ref = [TL.bits(F.linear(V[j:j + 1][..., :tau + 1], head)[0, -1]) for j in range(len(V))]
out = {}
for B in (2, 4, 8, 12, 15):
    y = F.linear(V[:B][..., :tau + 1], head)
    out[B] = {"elems": sum(int((TL.bits(y[j, -1]) != ref[j]).sum()) for j in range(B))}
    s = time.perf_counter(); F.linear(V[:B][..., :tau + 1], head).argmax(-1).cpu(); out[B]["batched_s"] = round(time.perf_counter() - s, 4)
    s = time.perf_counter(); [F.linear(V[j:j + 1][..., :tau + 1], head).argmax(-1).cpu() for j in range(B)]; out[B]["rowwise_s"] = round(time.perf_counter() - s, 4)
OUT["head"] = out
print("head", json.dumps(out), flush=True)
# (b)
g = torch.Generator().manual_seed(7)
def bitsf(t):
    return t.detach().cpu().numpy().reshape(-1).copy()
q = torch.randn(300, 32, 128, generator=g).to("mps")
ref = np.concatenate([bitsf((q[i:i + 1] * q[i:i + 1]).sum(-1, keepdim=True)) for i in range(300)])
qq = torch.randn(300, 32, 128, generator=g).to("mps")
ref2 = np.concatenate([bitsf(qq[i:i + 1].reshape(-1, 128).pow(2).mean(-1, keepdim=True)) for i in range(300)])
sk = (torch.randn(120, 32, 128, 128, generator=g).to("mps") * (torch.rand(120, 32, 128, 1, generator=g).to("mps") < 0.1)).float() * torch.randn(120, 32, 128, 1, generator=g).to("mps")
ref3 = np.concatenate([bitsf(sk[i:i + 1].sum(-2)) for i in range(120)])
tab = {}
for B in (8, 9, 12, 15, 16):
    a = np.concatenate([bitsf((q[j:j + B] * q[j:j + B]).sum(-1, keepdim=True)) for j in range(0, 300 - 300 % B, B)])
    b = np.concatenate([bitsf(qq[j:j + B].reshape(-1, 128).pow(2).mean(-1, keepdim=True)) for j in range(0, 300 - 300 % B, B)])
    c_ = np.concatenate([bitsf(sk[j:j + B].sum(-2)) for j in range(0, 120 - 120 % B, B)])
    tab[B] = {"l2": int((a != ref[:len(a)]).sum()), "gated_mean": int((b != ref2[:len(b)]).sum()), "state_sum": int((c_ != ref3[:len(c_)]).sum())}
OUT["reductions"] = tab
print(json.dumps(tab), flush=True)
json.dump(OUT, open("results/s11_rows.json", "w"), indent=1)
