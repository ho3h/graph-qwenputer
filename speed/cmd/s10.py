import torch; torch.set_grad_enabled(False)
import json, time
C2, D, X = TL.C2, TL.D, TL.X
chat = ctx.ec.chat
# Weights already in memory as CPU copies of real tensors: alternate blocking and non-blocking copies to MPS, on the same list
from safetensors import safe_open
import os, glob
idx = json.load(open(os.path.join(D.CKPT, "model.safetensors.index.json")))["weight_map"]
names = [k for k in idx if ".mlp.up_proj" in k and not any(f".layers.{i}." in k for i in range(11))][:12]
files = {}
cpu = []
for n in names:
    fn = idx[n]
    f = files.setdefault(fn, safe_open(os.path.join(D.CKPT, fn), framework="pt"))
    cpu.append(f.get_tensor(n))
gb = sum(t.numel() * 2 for t in cpu) / 2**30
res = {"tensors": len(cpu), "gib": round(gb, 2), "rounds": [], "shared_gpu": True}
for r in range(3):
    s = time.perf_counter(); a = [t.to("mps") for t in cpu]; ta = time.perf_counter() - s
    del a; torch.mps.empty_cache()
    s = time.perf_counter(); b = [t.to("mps", non_blocking=True) for t in cpu]; te = time.perf_counter() - s; torch.mps.synchronize(); tb = time.perf_counter() - s
    same = all(bool((x.cpu().view(torch.uint16) == y.view(torch.uint16)).all()) for x, y in zip(b[:2], cpu[:2]))
    del b; torch.mps.empty_cache()
    res["rounds"].append({"blocking_s": round(ta, 2), "non_blocking_encode_s": round(te, 2), "non_blocking_s": round(tb, 2), "bytes_same_on_2": same})
    print(json.dumps(res["rounds"][-1]), flush=True)
json.dump(res, open("results/s10_copy.json", "w"), indent=1)
