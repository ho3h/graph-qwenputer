"""Baseline for the design note: the vendored fastexec.Executor (the IR's arithmetic in fp32, sparse=True) on CPU or MPS, per token, on a
real tiny stream. Nothing here is an acceptance figure.

    python bench_torch.py --device cpu --n 300 --out results/bench_torch_cpu.json
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import decode as D  # noqa: E402

import torch  # noqa: E402

from chipformer.rv import core, fastexec  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--device", default="cpu")
ap.add_argument("--n", type=int, default=300)
ap.add_argument("--out")
a = ap.parse_args()
torch.set_num_threads(1)
L = C.Lite()
g = json.load(open(os.path.join(C.X210, "host", "test", "tiny.graph.json")))
prompt = D.prompt_for(L, g, "Answer with the graph tools.")
m0, stream, own, ses = D.session_for(L, g, prompt, [("find", {"name": "Eastgate"})])
core.snapshot(L.c, m0)
t0 = time.time()
ex = fastexec.Executor(L.c, a.device, 1, sparse=True)
build = time.time() - t0
ex.load_init()
emb = ex.embed(stream[:a.n + 50])
t = []
sync = (lambda: torch.mps.synchronize()) if a.device == "mps" else (lambda: None)
for i in range(min(a.n + 50, len(stream))):
    t0 = time.perf_counter()
    out = ex.step(emb[i:i + 1])
    v = float(out[0, 1])  # force the step to finish
    t.append(time.perf_counter() - t0)
t = sorted(t[50:])
r = {"device": a.device, "threads": torch.get_num_threads(), "build_s": round(build, 1), "tokens": len(t), "median_ms": round(1e3 * t[len(t) // 2], 3),
     "mean_ms": round(1e3 * sum(t) / len(t), 3), "chip_tok_per_s_at_mean": round(len(t) / sum(t), 1)}
print(json.dumps(r), flush=True)
if a.out:
    json.dump(r, open(a.out, "w"), indent=1)
