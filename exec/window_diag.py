"""The two points where a 6-position window with true lag windows ended with a state difference (results/windows_blank_control.json: 93100, 415264). Is it the transplant, or stock against the executor? Transplant earlier by LEAD positions and run through the same end: a difference that goes away with a lead comes from the transplant's first tokens; one that stays is stock against the executor. Each token's state differences are listed.

    python window_diag.py --points 93100,415264 --out results/windows_diag.json
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
from chat import ExecChat  # noqa: E402
from window import transplant, lag_tables  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

from chipformer.q35.ir import HD  # noqa: E402
from chipformer.rv import core, hf  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402


def details(ec, cache, limit=24):
    chat, cx = ec.chat, ec.cx
    c = chat.c
    r_ = c.target.value_heads // c.target.key_heads
    slots = {id(c.nodes[ni]): s for ni, s in hf.head_slots(c).items()}
    out, j, n_all = [], 0, 0
    for n in cx.heads:
        L, h = slots[id(n)]
        st = cache.layers[L].recurrent_states[0]
        for x in range(len(n.vheads())):
            a = st[0, h * r_ + x].detach().to(torch.float32).cpu().numpy()
            ro, co = np.nonzero(a != cx.S[j])
            n_all += len(ro)
            for r, k in zip(ro.tolist(), co.tolist()):
                if len(out) < limit:
                    out.append({"head": n.name, "x": x, "row": r, "col": k, "stock": float(a[r, k]), "exec": float(cx.S[j][r, k])})
            j += 1
    return n_all, out


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=os.path.join(HERE, "plan_fw.json"))
    ap.add_argument("--job", default="lim-hub")
    ap.add_argument("--points", default="93100,415264")
    ap.add_argument("--leads", default="0,3,12,60")
    ap.add_argument("--after", type=int, default=6)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    job = next(j for j in json.load(open(a.plan)) if j["name"] == a.job)
    ec = ExecChat(C.CKPT)
    chat, cx = ec.chat, ec.cx
    g = job["graph"]
    prompt = D.prompt_for(chat, g, "Answer with the graph tools.")
    m0, stream, own, ses = D.session_for(chat, g, prompt, [tuple(x) for x in job["calls"]], job.get("setup"), between=" ", tail="Done.")
    out = chat._prefill(prompt)
    cache = out.past_key_values
    core.snapshot(chat.c, m0)
    hf.inject(chat.c, cache)
    sl = lag_tables(cx)
    res = {"points": []}
    pts = sorted(int(x) for x in a.points.split(","))
    leads = sorted(int(x) for x in a.leads.split(","))
    cx.start([C.to_stream(chat.v0, i) for i in prompt])
    at = 0
    for p in pts:
        first = p - leads[-1]
        cx.run(stream[at:first], keep=False)
        base = cx.save()
        row = {"point": p, "tokens": [S.name(stream[i]) if stream[i] < S.VOCAB else "text" for i in range(p - 2, p + a.after)], "runs": []}
        for lead in leads:
            cx.restore(base)
            if lead < leads[-1]:
                cx.run(stream[first:p - lead], keep=False)
            transplant(ec, cache, sl)
            n0, d0 = details(ec, cache)
            steps = []
            bad = None
            for i in range(p - lead, p + a.after):
                t = stream[i]
                mid = D.to_model(chat, t)
                w0 = cx.p.writes
                hc, _ = chat._layers(mid, cache, None)
                bits, _ = ec.exec_bits(mid, cx.step(t).copy())
                if bad is None and not np.array_equal(hc.detach().cpu().view(torch.uint16).numpy(), bits):
                    bad = i
                nd, dd = details(ec, cache, limit=8)
                steps.append({"i": i, "tok": S.name(t) if t < S.VOCAB else "text", "state_diffs": nd, "first": dd[:4], "writes": int(cx.p.writes - w0)})
            row["runs"].append({"lead": lead, "right_after_transplant": n0, "first_after_transplant": d0[:4], "first_residual_mismatch": bad, "steps": steps})
            print(p, "lead", lead, "after transplant", n0, "per token", [s["state_diffs"] for s in steps], "residual", bad, flush=True)
            print("   first", next((s["first"] for s in steps if s["state_diffs"]), None), flush=True)
        at = first
        cx.restore(base)
        res["points"].append(row)
        json.dump(res, open(a.out, "w"), indent=1)
    json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
