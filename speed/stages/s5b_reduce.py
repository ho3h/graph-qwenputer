import torch; torch.set_grad_enabled(False)
import json, time
import numpy as np
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
g = torch.Generator().manual_seed(20261102)
emb = chat.lm.embed_tokens.weight
N = 1024
ids = torch.randint(0, 20000, (N,), generator=g).to("mps")
d0 = 2560
base = torch.zeros(N, 3968, dtype=torch.float32, device="mps")
base[:, :d0] = emb[ids, :d0].float() * 3.0 + torch.randn(N, d0, generator=g).to("mps") * 0.7
base = base.to(torch.bfloat16).to(torch.float32)
res = {}
def bitsf(t):
    return t.detach().cpu().numpy().reshape(-1).copy()
# reference: row alone, exactly as RMSNorm does at batch 1
ref = np.concatenate([bitsf(base[i:i + 1].unsqueeze(1).pow(2).mean(-1, keepdim=True)) for i in range(N)])
forms = {
 "mean(-1) on (B,1,D)": lambda x: x.unsqueeze(1).pow(2).mean(-1, keepdim=True),
 "transposed: mean(0) on (D,B)": lambda x: x.pow(2).t().mean(0),
 "sum(0)/D on (D,B)": lambda x: x.pow(2).t().sum(0) / x.shape[1],
 "flat cumsum at ends": lambda x: (x.pow(2).sum(1)) / x.shape[1],
 "row-by-row, sq shared": lambda x: torch.cat([s.mean(-1) for s in x.pow(2).unsqueeze(1).split(1)]),
 "row-by-row, 1-D": lambda x: torch.stack([s.pow(2).mean() for s in x]),
 "(B,D) row-by-row keepdim": lambda x: torch.cat([x[i:i+1].pow(2).mean(-1) for i in range(x.shape[0])]),
}
for nm, fn in forms.items():
    out = {}
    for B in (2, 4, 8, 16):
        t0 = time.perf_counter()
        ys = np.concatenate([bitsf(fn(base[a:a + B])) for a in range(0, N, B)])
        out[B] = int((ys != ref[:len(ys)]).sum())
    out["s_last"] = round(time.perf_counter() - t0, 3)
    res[nm] = out
    print(nm, json.dumps(out), flush=True)
# state sums: pairs carried in one tensor
sk = (torch.randn(200, 32, 128, 128, generator=g).to("mps") * (torch.rand(200, 32, 128, 1, generator=g).to("mps") < 0.1)).float()
kk = torch.randn(200, 32, 128, 1, generator=g).to("mps").float()
pr = sk * kk
rs = np.concatenate([bitsf(pr[i:i + 1].sum(-2)) for i in range(200)])
out = {}
for B in (2, 4, 8, 16):
    ys = np.concatenate([bitsf(pr[a:a + B].sum(-2)) for a in range(0, 200 - 200 % B, B)])
    out[B] = int((ys != rs[:len(ys)]).sum())
res["sum(-2) state"] = out
print("sum(-2) state", out, "elems", rs.size, flush=True)
q = torch.randn(400, 32, 128, generator=g).to("mps")
rs = np.concatenate([bitsf((q[i:i + 1] * q[i:i + 1]).sum(-1, keepdim=True)) for i in range(400)])
out = {}
for B in (2, 4, 8, 16):
    ys = np.concatenate([bitsf((q[a:a + B] * q[a:a + B]).sum(-1, keepdim=True)) for a in range(0, 400 - 400 % B, B)])
    out[B] = int((ys != rs[:len(ys)]).sum())
res["l2 sum (B,32,128)"] = out
print("l2", out, flush=True)
json.dump(res, open("results/s5b_reduce.json", "w"), indent=1)
