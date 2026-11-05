import torch; torch.set_grad_enabled(False)
import json, time
import numpy as np
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
g = torch.Generator().manual_seed(20261102)
emb = chat.lm.embed_tokens.weight
ids = torch.randint(0, 20000, (2000,), generator=g).to("mps")
d0 = 2560
base = torch.zeros(2000, 3968, dtype=torch.float32, device="mps")
base[:, :d0] = emb[ids, :d0].float() * 3.0 + torch.randn(2000, d0, generator=g).to("mps") * 0.7
base = base.to(torch.bfloat16).to(torch.float32)   # as a bf16 residual in fp32
res = {}
def bitsf(t):
    return t.detach().cpu().numpy().copy()
def test(name, x_rows, fn_row, shapes):
    """x_rows: tensor [N, ...], fn_row: f(batch tensor) -> [B, ...]. Row-alone first."""
    N = x_rows.shape[0]
    ref = np.concatenate([bitsf(fn_row(x_rows[i:i + 1])) for i in range(N)])
    out = {}
    for B in shapes:
        ys = np.concatenate([bitsf(fn_row(x_rows[a:a + B])) for a in range(0, N - N % B, B)])
        out[B] = int((ys != ref[:len(ys)]).sum())
    out["elems"] = int(ref.size)
    res[name] = out
    print(name, json.dumps(out), flush=True)
S = (2, 4, 8, 16)
test("mean3968 (B,1,D)", base.unsqueeze(1), lambda x: x.pow(2).mean(-1, keepdim=True), S)
test("sum3968 (B,1,D)", base.unsqueeze(1), lambda x: x.pow(2).sum(-1, keepdim=True), S)
test("mean3968 (B,D)", base, lambda x: x.pow(2).mean(-1, keepdim=True), S)
test("sum via matmul", base, lambda x: (x.unsqueeze(1) @ x.unsqueeze(2)).squeeze(1), S)
h256 = base[:, :2560].reshape(-1, 10, 256).float()[:, :10]
test("mean256 (B,1,10,256)", h256[:400].unsqueeze(1), lambda x: x.pow(2).mean(-1, keepdim=True), S)
h128 = base[:, :2560].reshape(-1, 20, 128).float()
test("mean128 (B*20,128) rows of 20", h128[:400], lambda x: x.reshape(-1, 128).pow(2).mean(-1, keepdim=True).reshape(x.shape[0], 20, 1), S)
test("sum128 k (B,20,1,128)", h128[:400].unsqueeze(2), lambda x: (x * x).sum(-1, keepdim=True), S)
st = torch.randn(400, 32, 128, 128, generator=g).to("mps") * (torch.rand(400, 32, 128, 1, generator=g).to("mps") < 0.1)
ku = torch.randn(400, 32, 128, 1, generator=g).to("mps")
idx = torch.arange(400, device="mps")
test("sum(-2) state (B,32,128,128)", st[:200], lambda x: (x * ku[:x.shape[0]]).sum(-2), (2, 4, 8))
json.dump(res, open("results/s5_reduce.json", "w"), indent=1)
