"""T4: every tensor outside the chip layers, embedding and final norm of x210-tok against x210-rvc, bit for bit; and Qwen's dims of the embedding and final norm.

    python tok/check_qwen_tensors.py --out tok/results/t4_qwen_tensors.json
"""
import argparse
import json
import os
import sys
import time

import torch
from safetensors import safe_open

A = os.path.expanduser("~/Models/x210/x210-rvc")
B = os.path.expanduser("~/Models/x210/x210-tok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    ia = json.load(open(os.path.join(A, "model.safetensors.index.json")))["weight_map"]
    ib = json.load(open(os.path.join(B, "model.safetensors.index.json")))["weight_map"]
    assert ia == ib
    meta = json.load(open(os.path.join(B, "chipformer.json")))
    n_chip, d0 = meta["chip_layers"], meta["chip_dims_offset"]
    res = {"same": 0, "different": [], "chip_layers_differ": 0, "chip_layers_same": 0, "qwen_dims": {}}
    for sh in sorted(set(ia.values())):
        with safe_open(os.path.join(A, sh), "pt") as fa, safe_open(os.path.join(B, sh), "pt") as fb:
            assert set(fa.keys()) == set(fb.keys()), sh
            for k in fa.keys():  # noqa: SIM118
                x, y = fa.get_tensor(k), fb.get_tensor(k)
                u, v = x.view(-1).view(torch.uint16) if x.dtype == torch.bfloat16 else x.view(-1), y.view(-1).view(torch.uint16) if y.dtype == torch.bfloat16 else y.view(-1)
                eq = x.shape == y.shape and x.dtype == y.dtype and bool((u == v).all())
                if k.startswith("model.layers.") and int(k.split(".")[2]) < n_chip:
                    res["chip_layers_same" if eq else "chip_layers_differ"] += 1
                elif k in ("model.embed_tokens.weight", "model.norm.weight"):
                    low = bool((x[..., :d0].view(torch.uint16) == y[..., :d0].view(torch.uint16)).all())
                    res["qwen_dims"][k] = low
                    if k == "model.embed_tokens.weight":
                        high = (x[:, d0:].view(torch.uint16) != y[:, d0:].view(torch.uint16))
                        res["embedding_rows_differing_chip_dims"] = int(high.any(1).sum())
                elif eq:
                    res["same"] += 1
                else:
                    res["different"].append(k)
                del x, y
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(a.out, "w"), indent=1)
    print(res)


if __name__ == "__main__":
    main()
