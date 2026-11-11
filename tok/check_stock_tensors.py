"""Round 17: Qwen's 32 layers in the published checkpoint (x210-tok) against the stock Qwen3.5-4B release, bit for bit, in Qwen's own dimensions.

The merged model is wider (3968 against 2560), so each tensor is compared on its first 2560 entries along every widened axis.
Also the embedding's first 248,320 rows and the final norm, same slice. Reads with safetensors, one tensor at a time. No GPU.

    python tok/check_stock_tensors.py --out tok/results/r17_stock_tensors.json
"""
import argparse
import json
import os
import time

import torch
from safetensors import safe_open

STOCK = os.path.expanduser("~/Models/x210/Qwen3.5-4B")
OURS = os.path.expanduser("~/Models/x210/x210-tok")


def bits(t):
    """The tensor's raw bits, so the comparison is bit for bit for every dtype."""
    t = t.contiguous().view(-1)
    return t.view({torch.bfloat16: torch.int16, torch.float16: torch.int16, torch.float32: torch.int32, torch.float64: torch.int64}.get(t.dtype, t.dtype))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    ws = json.load(open(os.path.join(STOCK, "model.safetensors.index.json")))["weight_map"]
    wo = json.load(open(os.path.join(OURS, "model.safetensors.index.json")))["weight_map"]
    meta = json.load(open(os.path.join(OURS, "chipformer.json")))
    n_chip, d0, hid, v0 = meta["chip_layers"], meta["chip_dims_offset"], meta["hidden"], meta["chip_token_offset"]
    pairs = []
    for k in sorted(wo):
        if k.startswith("model.layers."):
            p = k.split(".")
            i = int(p[2])
            if i < n_chip:
                continue
            pairs.append((k, "model.language_model.layers.%d.%s" % (i - n_chip, ".".join(p[3:]))))
        else:
            pairs.append((k, k.replace("model.", "model.language_model.", 1)))
    files = {}

    def get(root, wm, k):
        f = os.path.join(root, wm[k])
        if f not in files:
            files[f] = safe_open(f, "pt")
        return files[f].get_tensor(k)

    res = {"stock": STOCK, "ours": OURS, "qwen_width": d0, "merged_width": hid, "pairs": len(pairs), "same": 0, "different": [], "missing_in_stock": [],
           "widened": 0, "same_shape": 0, "outside_block_nonzero": [], "dtype_differs": [], "dtypes": {}}
    scale = (d0 / hid) ** 0.5   # Qwenputer's widen(): a norm gain w becomes (1 + w) * scale - 1 (chipformer/q35/merge.py)
    rescale = {"scale": scale, "norms_differ": 0, "norms_equal_qwenputer_rescale_bf16": 0, "not_exact": []}
    for ko, ks in pairs:
        if ks not in ws:
            res["missing_in_stock"].append(ko)
            continue
        x, y = get(OURS, wo, ko), get(STOCK, ws, ks)
        if x.dtype != y.dtype:
            res["dtype_differs"].append([ko, str(x.dtype), str(y.dtype)])
        sl, ok, wide = [], x.dim() == y.dim(), False
        if ok:
            for ax, (m, n) in enumerate(zip(x.shape, y.shape)):
                if m == n:
                    sl.append(slice(None))
                elif ko == "model.embed_tokens.weight" and ax == 0 and n == v0:
                    sl.append(slice(0, n))
                elif m == hid and n == d0:
                    sl.append(slice(0, n))
                    wide = True
                else:
                    ok = False
        if not ok:
            res["different"].append([ko, list(x.shape), list(y.shape), "shape"])
            continue
        blk = x[tuple(sl)]
        res["dtypes"][str(x.dtype)] = res["dtypes"].get(str(x.dtype), 0) + 1
        if x.dtype == y.dtype and bool((bits(blk) == bits(y)).all()):
            res["same"] += 1
        else:
            res["different"].append([ko, list(x.shape), list(y.shape), "values"])
            if ko.endswith("norm.weight") and x.dim() == 1:
                want = ((1.0 + y.float()) * scale - 1.0).to(y.dtype)
                rescale["norms_differ"] += 1
                if bool((bits(want) == bits(blk)).all()):
                    rescale["norms_equal_qwenputer_rescale_bf16"] += 1
                else:
                    rescale["not_exact"].append(ko)
        if wide:
            res["widened"] += 1
            if ko != "model.embed_tokens.weight":
                rest = x.clone().float()
                rest[tuple(sl)] = 0
                nz = int((rest != 0).sum())
                if nz:
                    res["outside_block_nonzero"].append([ko, nz])
        else:
            res["same_shape"] += 1
        del x, y
    by = {}
    for k, nz in res["outside_block_nonzero"]:
        kind = ".".join(k.split(".")[3:]) if k.startswith("model.layers.") else k
        by.setdefault(kind, [0, 0])
        by[kind][0] += 1
        by[kind][1] += nz
    res["norm_rescale_check"], res["outside_block_by_kind"] = rescale, by
    res["layer_tensors_same"] = res["same"] - sum(1 for k, _ in pairs if not k.startswith("model.layers.") and k not in [d[0] for d in res["different"]])
    res["seconds"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(res, open(a.out, "w"), indent=1)
    print({k: (v if not isinstance(v, list) else len(v)) for k, v in res.items()})
    for r in res["different"][:10]:
        print("DIFF", r)
    for r in res["outside_block_nonzero"][:10]:
        print("OUTSIDE", r)


if __name__ == "__main__":
    main()
