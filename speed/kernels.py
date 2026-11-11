"""S0: do linear maps give the same bits on MPS when zero rows or columns are dropped, or inputs batched? Real tensors from the merged checkpoint.

    python kernels.py --out results/s0_kernels.json
"""
import argparse
import json
import os
import time

import numpy as np
import torch
import torch.nn.functional as F
from safetensors import safe_open

CKPT = "<drive>/Models/x210-rvc"
D0, NQ = 2560, 248320
idx = json.load(open(os.path.join(CKPT, "model.safetensors.index.json")))["weight_map"]


def get(name):
    with safe_open(os.path.join(CKPT, idx[name]), framework="pt") as f:
        return f.get_tensor(name)


def bits(t):
    return t.detach().cpu().view(torch.uint16).numpy().copy()


def sync(t):
    return t.detach().cpu()


def hull(w):
    nz = (w != 0)
    r = nz.any(1).nonzero().flatten()
    c = nz.any(0).nonzero().flatten()
    return int(r[0]), int(r[-1]) + 1, int(c[0]), int(c[-1]) + 1, int(nz.sum()), w.numel()


def pad_rows(y, r0, r1, n):
    return F.pad(y, (r0, n - r1))


def compare(name, w, xs, dev, res):
    r0, r1, c0, c1, nnz, numel = hull(w)
    W = w.to(dev)
    block = w[r0:r1, c0:c1].contiguous().to(dev)
    rows = w[r0:r1].contiguous().to(dev)
    n = len(xs)
    X = xs.to(dev)
    t = {"dense": 0.0, "rows": 0.0, "block": 0.0, "batch": 0.0}
    dense, rws, blk = [], [], []
    for i in range(n):                                     # A/B alternating, one at a time
        x = X[i:i + 1].unsqueeze(1)
        s = time.perf_counter(); y = sync(F.linear(x, W)); t["dense"] += time.perf_counter() - s
        dense.append(y.view(torch.uint16).numpy().copy())
        s = time.perf_counter(); y = sync(pad_rows(F.linear(x, rows), r0, r1, w.shape[0])); t["rows"] += time.perf_counter() - s
        rws.append(y.view(torch.uint16).numpy().copy())
        s = time.perf_counter(); y = sync(pad_rows(F.linear(x[..., c0:c1], block), r0, r1, w.shape[0])); t["block"] += time.perf_counter() - s
        blk.append(y.view(torch.uint16).numpy().copy())
    dense, rws, blk = np.concatenate(dense), np.concatenate(rws), np.concatenate(blk)
    out = {"shape": list(w.shape), "rows": [r0, r1], "cols": [c0, c1], "nonzero_frac": round(nnz / numel, 4), "rows_diff_elems": int((dense != rws).sum()), "block_diff_elems": int((dense != blk).sum()), "elems": int(dense.size)}
    for B in (2, 8, 16, 32, 64):
        B = min(B, n)
        t0 = time.perf_counter()
        ys = []
        for a in range(0, n, B):
            ys.append(sync(F.linear(X[a:a + B].unsqueeze(1), W)).view(torch.uint16).numpy())
        dt = time.perf_counter() - t0
        out[f"batch{B}_diff_elems"] = int((np.concatenate(ys) != dense).sum())
        out[f"batch{B}_s_per_row"] = round(dt / n, 5)
    out.update({f"{k}_s_per_row": round(v / n, 5) for k, v in t.items() if k != "batch"})
    res[name] = out
    print(name, json.dumps(out), flush=True)
    del W, block, rows
    torch.mps.empty_cache()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    dev = "mps"
    t00 = time.time()
    emb = get("model.embed_tokens.weight")
    print("emb", emb.shape, emb.dtype, round(time.time() - t00, 1), flush=True)
    g = torch.Generator().manual_seed(20261102)
    ids = torch.randint(0, 20000, (64,), generator=g)
    xs = torch.zeros(64, emb.shape[1], dtype=torch.bfloat16)
    xs[:, :D0] = (emb[ids, :D0].float() + 0.3 * torch.randn(64, D0, generator=g)).to(torch.bfloat16)
    res = {"dtype": str(emb.dtype), "n_inputs": 64, "shared_gpu": True}
    for name in ["model.layers.11.mlp.gate_proj.weight", "model.layers.11.mlp.down_proj.weight", "model.layers.11.linear_attn.in_proj_qkv.weight", "model.layers.11.linear_attn.out_proj.weight",
                 "model.layers.14.self_attn.q_proj.weight", "model.layers.14.self_attn.o_proj.weight"]:
        w = get(name)
        if w.shape[1] != xs.shape[1]:                      # maps from the 9,216 or head-sized space
            gg = torch.Generator().manual_seed(1)
            x2 = torch.randn(64, w.shape[1], generator=gg).to(torch.bfloat16)
        else:
            x2 = xs
        compare(name.replace("model.layers.", "L").replace(".weight", ""), w, x2, dev, res)
    # the head: tied to the embedding
    W = emb.to(dev)
    Wq = emb[:NQ].contiguous().to(dev)
    Wc = emb[:NQ, :D0].contiguous().to(dev)
    X = xs.to(dev)
    t = {"full": 0.0, "rows": 0.0, "rows_cols": 0.0}
    d = {"rows": 0, "rows_cols": 0}
    argm = {"rows": 0, "rows_cols": 0}
    hq = get("model.norm.weight")
    print("norm weight nonzero above d0", int((hq[D0:] != 0).sum()), flush=True)
    for i in range(16):
        x = X[i:i + 1].unsqueeze(1)
        s = time.perf_counter(); y0 = sync(F.linear(x, W)[0, 0]); t["full"] += time.perf_counter() - s
        s = time.perf_counter(); y1 = sync(F.linear(x, Wq)[0, 0]); t["rows"] += time.perf_counter() - s
        s = time.perf_counter(); y2 = sync(F.linear(x[..., :D0], Wc)[0, 0]); t["rows_cols"] += time.perf_counter() - s
        b0 = y0[:NQ].view(torch.uint16).numpy()
        d["rows"] += int((b0 != y1.view(torch.uint16).numpy()).sum())
        d["rows_cols"] += int((b0 != y2.view(torch.uint16).numpy()).sum())
        argm["rows"] += int(y0[:NQ].argmax() != y1.argmax())
        argm["rows_cols"] += int(y0[:NQ].argmax() != y2.argmax())
    res["head"] = {"s_per_token": {k: round(v / 16, 4) for k, v in t.items()}, "diff_elems": d, "argmax_diff": argm, "rows": NQ, "n": 16}
    print(json.dumps(res["head"]), flush=True)
    res["seconds"] = round(time.time() - t00, 1)
    json.dump(res, open(a.out, "w"), indent=1)
    print("seconds", res["seconds"], flush=True)


if __name__ == "__main__":
    main()
