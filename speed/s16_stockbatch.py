"""S16: stock HF chip-layer modules on MPS, the blocks of their linear maps only, B independent rows at once: chip tokens/s, and each row's bits against a saved stock trace.

    python s16_stockbatch.py --job c024-chase --steps 2000 --out results/s16_stockbatch.json
"""
import argparse, json, os, sys, time, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(X210, "exec"))
os.environ.setdefault("CHIP_FIRMWARE", os.path.join(X210, "fw", "build", "fw.elf"))
import common as C
import decode as D
import numpy as np
import torch
torch.set_grad_enabled(False)
from chipformer.q35 import fast as QF
from chipformer.rv import core, hf
from transformers import AutoConfig, DynamicCache, Qwen3_5ForCausalLM
import textlib as TL
ap = argparse.ArgumentParser()
ap.add_argument("--job", default="c024-chase")
ap.add_argument("--steps", type=int, default=2000)
ap.add_argument("--rows", default="1,2,4,8,15")
ap.add_argument("--dense", action="store_true")
ap.add_argument("--out", required=True)
a = ap.parse_args()
L = C.Lite()
t0 = time.time()
model = Qwen3_5ForCausalLM.from_pretrained(C.CKPT, dtype=torch.bfloat16)
n_chip = L.meta["chip_layers"]
d0 = L.meta["chip_dims_offset"]
chip_layers = [model.model.layers[i] for i in range(n_chip)]
if not a.dense:
    chip_layers = [TL.clone_compact(x) for x in chip_layers]
chip_layers = torch.nn.ModuleList(chip_layers).to("mps").eval()
emb_cpu = model.model.embed_tokens.weight.data
del model.model.layers
load_s = round(time.time() - t0, 1)
print("loaded", load_s, TL.D.mem(), flush=True)
plan = {j["name"]: j for j in json.load(open(os.path.join(X210, "exec", "plan_fw.json")))}
job = plan[a.job]
tr = dict(np.load(os.path.join(X210, "exec", "results", "trace_fw", a.job + ".npz")))
g = job["graph"] if isinstance(job["graph"], dict) else json.load(open(D.graph_path(job["graph"])[0]))
calls = [tuple(x) for x in job["calls"]]
prompt = D.prompt_for(L, g, job.get("text") or "Answer with the graph tools.")
m0, stream, own, ses = D.session_for(L, g, prompt, calls, job.get("setup"), between=" ", tail="Done.")
core.snapshot(L.c, m0)
cfg = model.config
rows_cache = {}
def row(mid):
    if mid not in rows_cache:
        rows_cache[mid] = emb_cpu[mid].to("mps")
    return rows_cache[mid]
def run_b(B, steps):
    cache = DynamicCache(config=cfg)
    x = torch.stack([row(i) for i in prompt]).unsqueeze(0)
    h = x
    for l in chip_layers:
        h = l(h, position_embeddings=None, attention_mask=None, position_ids=None, past_key_values=cache)
    hf.inject(L.c, cache)
    for i in range(n_chip):
        lay = cache.layers[i]
        lay.conv_states[0] = lay.conv_states[0].repeat(B, 1, 1)
        lay.recurrent_states[0] = lay.recurrent_states[0].repeat(B, 1, 1, 1)
    ptr, idx, bits, mids = tr["ptr"], tr["idx"], tr["bits"], tr["tokens"]
    n = min(steps, len(mids))
    diff = 0; diffrows = 0
    t = time.perf_counter(); tw = 0.0
    for p in range(n):
        xb = row(int(mids[p])).view(1, 1, -1).repeat(B, 1, 1)
        h = xb
        for l in chip_layers:
            h = l(h, position_embeddings=None, attention_mask=None, position_ids=None, past_key_values=cache)
        sel = torch.from_numpy(idx[ptr[p]:ptr[p + 1]].astype(np.int64)).to("mps")
        s = time.perf_counter()
        got = h[:, 0, sel].cpu().view(torch.uint16).numpy() if len(sel) else None
        nnz = int((h[:, 0, d0:] != 0).sum().item())
        tw += time.perf_counter() - s
        if got is not None:
            bad = (got != bits[ptr[p]:ptr[p + 1]])
            diff += int(bad.sum())
            diffrows += int(bad.any(1).sum())
        # every other chip dim must be zero: nonzero count equals the trace's kept nonzeros × B
        want = int((bits[ptr[p]:ptr[p + 1]] & 0x7FFF != 0).sum()) * B
        if nnz != want:
            diff += abs(nnz - want)
    wall = time.perf_counter() - t
    return {"rows": B, "steps": n, "seconds": round(wall, 1), "steps_per_s": round(n / wall, 2), "row_tokens_per_s": round(B * n / wall, 1), "wait_s": round(tw, 1), "elements_differ": diff, "rows_differ": diffrows, "mem": TL.D.mem()}
res = {"job": a.job, "dense": a.dense, "load_s": load_s, "runs": [], "shared_gpu": True, "note": "HF modules on MPS; linear maps cropped to nonzero blocks unless dense; heads not pruned; teacher-forced on the trace's tokens; same stream on every row"}
for B in map(int, a.rows.split(",")):
    r = run_b(B, a.steps)
    res["runs"].append(r)
    print(json.dumps(r), flush=True)
    json.dump(res, open(a.out, "w"), indent=1)
    torch.mps.empty_cache()
