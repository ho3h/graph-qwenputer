"""S14: free-running chip tokens/s on c024's chases, wexec or exec/'s engine, one process. A second driver runs several at once."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(X210, "exec")); sys.path.insert(0, HERE)
import common as C
import decode as D
import numpy as np
from chipformer.rv import core
from chipformer.rv import spec as S
kind, out = sys.argv[1], sys.argv[2]
L = C.Lite()
plan = {j["name"]: j for j in json.load(open(os.path.join(X210, "exec", "plan_fw.json")))}
job = plan["c024-chase"]
g = json.load(open(D.graph_path(job["graph"])[0]))
calls = [tuple(x) for x in job["calls"]]
prompt = D.prompt_for(L, g, job.get("text") or "Answer with the graph tools.")
m0, stream, own, ses = D.session_for(L, g, prompt, calls, job.get("setup"), between=" ", tail="Done.")
core.snapshot(L.c, m0)
if kind == "wexec":
    from wexec import WExec
    ex = WExec(L.c, L.T, L.meta)
else:
    from cexec import CExec
    ex = CExec(L.c, L.T)
p = [C.to_stream(L.v0, i) for i in prompt]
rates = []
wrong = 0
for rep in range(int(os.environ.get("REPS", "5"))):
    ex.start(p)
    i, n_chip = 0, 0
    t0 = time.perf_counter()
    n = len(stream)
    while i < n:
        t = stream[i]
        if t < S.VOCAB:
            end = i
            while end < n and stream[end] < S.VOCAB:
                end += 1
            st, nxt, k, rec = ex.burst(t, end - i, record=True)
            n_chip += k
            wrong += int(rec[:k].tolist() != stream[i + 1:i + k + 1])
            i += k
        else:
            ex.step(t)
            i += 1
    rates.append(n_chip / (time.perf_counter() - t0))
json.dump({"kind": kind, "chip_tokens": n_chip, "rates": [round(r, 1) for r in rates], "median": round(float(np.median(rates)), 1), "wrong_bursts": wrong, "flags": ex.flags(), "engine": ex.lib_hash}, open(out, "w"))
