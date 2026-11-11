"""Verify windows deep inside a long stream without running stock through everything before them. The executor runs to the window's start; its state is transplanted into the stock chip layers' cache (every head's state, and the conv windows of every channel with a lag tap, computed from the executor's lag slots); then both run the window, teacher-forced, compared bit by bit over all 3,968 dims, and every head's state is compared at the window's end. Positions are fixed by the seed before any of them runs.

    python window.py --job lim-hub --windows 8 --length 1500 --seed 11 --out results/windows_hub.json

A transplant checks the window, not the road to it: an error earlier in the executor's state is inherited by stock. It shows up only if it reaches a residual or a compared state inside the window, and the reference lock covers the road's tokens.
Only the chip layers run on stock here, also on text tokens. Any mismatch stops the run: exit code 3.
"""
import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import decode as D  # noqa: E402
from chat import ExecChat  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

from chipformer.q35.ir import HD, Head  # noqa: E402
from chipformer.rv import core, hf  # noqa: E402


def lag_tables(ex):
    """(level, dim) -> first lag slot, from the compiled tables."""
    out = {}
    for L in ex.A["levels"]:
        if L[0] == 1:
            for i in range(L[6], L[7]):
                out[(int(L[12]), int(ex.A["lag_dim"][i]))] = int(ex.A["lag_slot"][i])
    return out


@torch.no_grad()
def transplant(ec, cache, slots_lag, blank_lags=False):
    """The executor's states and lag windows into the stock chip layers' cache. blank_lags (a control): every lag window zero instead."""
    chat, cx = ec.chat, ec.cx
    c = chat.c
    r_ = c.target.value_heads // c.target.key_heads
    nk = c.target.key_heads
    slots = {id(c.nodes[ni]): s for ni, s in hf.head_slots(c).items()}
    by_layer = {}
    j = 0
    for n in cx.heads:
        L, h = slots[id(n)]
        st = by_layer.setdefault(L, np.zeros((c.target.value_heads, HD, HD), np.float32))
        for x in range(len(n.vheads())):
            st[h * r_ + x] = cx.S[j]
            j += 1
    for L, arr in by_layer.items():
        lay = cache.layers[L]
        lay.recurrent_states[0].copy_(torch.from_numpy(arr)[None].to(lay.recurrent_states[0].device).to(lay.recurrent_states[0].dtype))
        conv = lay.conv_states[0]
        cw = conv.detach().cpu().to(torch.float32).numpy().copy()
        lv = 2 * L + 1
        for n in cx.heads:
            if n.level != lv:
                continue
            _, h = slots[id(n)]

            def fill(base, chans):
                for i, ch in chans.items():
                    if not any(ch.taps[1:]):
                        continue
                    for lag in (1, 2, 3):             # every lag, not only those with a tap: a window shifts, so a tap at lag 2 reads next token what is at lag 1 now
                        v = sum(float(cf) * float(cx.mem[slots_lag[(lv, d)] + lag - 1]) for d, cf in ch.expr.terms.items())
                        cw[0, base + i, -lag] = 0.0 if blank_lags else v
            fill(h * HD, n.q)
            fill(nk * HD + h * HD, n.k)
            for x, vd in enumerate(n.vheads()):
                fill(2 * nk * HD + (h * r_ + x) * HD, vd.v)
        conv.copy_(torch.from_numpy(cw).to(conv.device).to(conv.dtype))


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=os.path.join(HERE, "plan_fw.json"))
    ap.add_argument("--job", required=True)
    ap.add_argument("--windows", type=int, default=8)
    ap.add_argument("--length", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--hours", type=float, default=1.0)
    ap.add_argument("--negative", action="store_true", help="first, one window with a wrong bit in the transplanted lag window of a channel the stream uses, and one with a corrupted engine weight; both must be caught")
    ap.add_argument("--range", default=None, help="a:b, fractions of the stream the windows are drawn from")
    ap.add_argument("--blank-control", action="store_true", help="first, one window with every transplanted lag window zero")
    ap.add_argument("--blank-points", type=int, default=0, help="only a control: at this many seeded points, transplant with every lag window zero and run 6 positions; then the same point with the true windows. A blank lag window lasts 3 tokens, so one point says little. Exit after.")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    deadline = time.time() + a.hours * 3600
    job = next(j for j in json.load(open(a.plan)) if j["name"] == a.job)
    t0 = time.time()
    ec = ExecChat(C.CKPT)
    chat, cx = ec.chat, ec.cx
    print(f"loaded {time.time() - t0:.0f}s {D.mem()}", flush=True)
    g = job["graph"] if isinstance(job["graph"], dict) else json.load(open(D.graph_path(job["graph"])[0]))
    prompt = D.prompt_for(chat, g, "Answer with the graph tools.")
    m0, stream, own, ses = D.session_for(chat, g, prompt, [tuple(x) for x in job["calls"]], job.get("setup"), between=" ", tail="Done.")
    n = len(stream)
    rng = random.Random(a.seed)
    lo, hi = n // 20, n - a.length - 1
    if a.range:
        fa, fb = a.range.split(":")
        lo, hi = int(float(fa) * n), min(hi, int(float(fb) * n))
    starts = sorted(rng.randrange(lo, hi) for _ in range(a.windows))
    res = {"job": a.job, "stream": n, "seed": a.seed, "length": a.length, "starts": starts, "firmware": C.X.build_elf(), "windows": [], "engine": cx.lib_hash}
    json.dump(res, open(a.out, "w"), indent=1)                    # the choice is saved first
    print(f"stream {n}, starts {starts}", flush=True)
    out = chat._prefill(prompt)
    cache = out.past_key_values
    core.snapshot(chat.c, m0)
    hf.inject(chat.c, cache)
    slots_lag = lag_tables(cx)
    pt = [C.to_stream(chat.v0, i) for i in prompt]

    def window(p, length, label):
        transplant(ec, cache, slots_lag)
        ts = time.perf_counter()
        pos_ok = owned = 0
        for i in range(p, p + length):
            t = stream[i]
            mid = D.to_model(chat, t)
            hc, _ = chat._layers(mid, cache, None)
            hcu = hc.detach().cpu().view(torch.uint16).numpy()
            keep = cx.step(t).copy()
            bits, exact = ec.exec_bits(mid, keep)
            if not exact or not np.array_equal(hcu, bits):
                dd = np.nonzero(hcu != bits)[0]
                return {"label": label, "start": p, "length": length, "positions_ok": pos_ok, "owned": owned, "mismatch_at": i, "n_dims": int(len(dd)), "dims": [{"dim": int(d), "stock": hex(int(hcu[d])), "exec": hex(int(bits[d]))} for d in dd[:8]], "exact": exact, "seconds": round(time.perf_counter() - ts, 1)}
            pos_ok += 1
            owned += bool(own[i])
        return {"label": label, "start": p, "length": length, "positions_ok": pos_ok, "owned": owned, "mismatch_at": None, "end_state": ec.state_diff(cache), "seconds": round(time.perf_counter() - ts, 1)}

    if a.negative:
        # one wrong bit in a transplanted lag window: the first window's channels must notice, or be recorded as not noticing
        cx.start(pt)
        cx.run(stream[: starts[0]], keep=False)
        lag_idx = [int(s) for s in cx.A["lag_slot"]]
        hit = None
        for s in lag_idx:
            if cx.mem[s] != 0:
                hit = s
                break
        if hit is not None:
            old = float(cx.mem[hit])
            cx.mem[hit] = 0.0
            transplant(ec, cache, slots_lag)
            cx.mem[hit] = old
            # the executor keeps its true windows; stock has the wrong one for this window's first tokens
            ts = time.perf_counter()
            bad = None
            for i in range(starts[0], starts[0] + min(a.length, 200)):
                t = stream[i]
                mid = D.to_model(chat, t)
                hc, _ = chat._layers(mid, cache, None)
                bits, _ = ec.exec_bits(mid, cx.step(t).copy())
                if not np.array_equal(hc.detach().cpu().view(torch.uint16).numpy(), bits):
                    bad = i
                    break
            res["negative_lag_slot"] = {"slot": hit, "was": old, "set_to": 0.0, "first_mismatch": bad, "window_start": starts[0]}
            print("negative lag slot", res["negative_lag_slot"], flush=True)
        good = ec.cx
        from cexec import CExec
        mut = {"table": "tw", "u": 0.8988382879679935}
        def corrupt(A):
            i = int(mut["u"] * len(A["tw"]))
            mut["index"], mut["old"] = i, float(A["tw"][i])
            A["tw"][i] = mut["old"] * (1 + 1 / 128)
        bad_cx = CExec(chat.c, chat.T, corrupt=corrupt)
        ec.cx = bad_cx
        bad_cx.start(pt)
        bad_cx.run(stream[: starts[0]], keep=False)
        r = window(starts[0], min(a.length, 300), "negative corrupted engine")
        res["negative_engine"] = {"mutation": mut, **{k: r.get(k) for k in ("mismatch_at", "n_dims", "positions_ok", "end_state")}}
        print("negative engine", res["negative_engine"], flush=True)
        ec.cx = cx = good
        json.dump(res, open(a.out, "w"), indent=1)
    if a.blank_points:
        pts = sorted(rng.randrange(lo, hi) for _ in range(a.blank_points))
        res["blank_points"] = []
        cx.start(pt)
        at = 0
        for p in pts:
            cx.run(stream[at:p], keep=False)
            at = p
            saved = cx.save()
            row = {"start": p}
            for label, blank in (("blank", True), ("true", False)):
                cx.restore(saved)
                transplant(ec, cache, slots_lag, blank_lags=blank)
                bad = None
                w0 = cx.p.writes
                for i in range(p, p + 6):
                    t = stream[i]
                    mid = D.to_model(chat, t)
                    hc, _ = chat._layers(mid, cache, None)
                    bits, _ = ec.exec_bits(mid, cx.step(t).copy())
                    if bad is None and not np.array_equal(hc.detach().cpu().view(torch.uint16).numpy(), bits):
                        bad = i - p
                sd = ec.state_diff(cache)
                row[label] = {"first_residual_mismatch": bad, "state_big": sd["big"], "state_small": sd["small"], "writes_in_6": int(cx.p.writes - w0)}
            cx.restore(saved)
            res["blank_points"].append(row)
            print(json.dumps(row), flush=True)
            json.dump(res, open(a.out, "w"), indent=1)
        caught = [r for r in res["blank_points"] if r["blank"]["first_residual_mismatch"] is not None or r["blank"]["state_big"]]
        wrong_true = [r for r in res["blank_points"] if r["true"]["first_residual_mismatch"] is not None or r["true"]["state_big"]]
        res["blank_caught"], res["true_failed"], res["points"] = len(caught), len(wrong_true), len(pts)
        json.dump(res, open(a.out, "w"), indent=1)
        print(f"blank windows caught at {len(caught)} of {len(pts)} points; true windows failed at {len(wrong_true)}", flush=True)
        return
    if a.blank_control:
        cx.start(pt)
        cx.run(stream[: starts[0]], keep=False)
        saved = cx.save()
        transplant(ec, cache, slots_lag, blank_lags=True)
        bad = None
        m = min(a.length, 300)
        for i in range(starts[0], starts[0] + m):
            t = stream[i]
            mid = D.to_model(chat, t)
            hc, _ = chat._layers(mid, cache, None)
            bits, _ = ec.exec_bits(mid, cx.step(t).copy())
            if not np.array_equal(hc.detach().cpu().view(torch.uint16).numpy(), bits):
                bad = i
                break
        res["blank_control"] = {"window_start": starts[0], "positions": m, "first_mismatch": bad, "end_state": ec.state_diff(cache) if bad is None else None, "caught": bad is not None}
        print("blank control", res["blank_control"], flush=True)
        cx.restore(saved)
        json.dump(res, open(a.out, "w"), indent=1)
    cx.start(pt)
    at = 0
    code = 0
    for k, p in enumerate(starts):
        if time.time() > deadline:
            res["stopped_at_deadline"] = k
            break
        if p < at:                                                # overlapping draws: the later one starts where the earlier ended
            p = at
        cx.p.flags = 0
        ts = time.perf_counter()
        cx.run(stream[at:p], keep=False)
        road_s = time.perf_counter() - ts
        r = window(p, a.length, f"w{k}")
        r["road_seconds"] = round(road_s, 2)
        r["flags"] = cx.flags()
        res["windows"].append(r)
        at = p + a.length
        print(json.dumps({x: r[x] for x in ("label", "start", "positions_ok", "owned", "mismatch_at", "seconds")}), r.get("end_state"), flush=True)
        json.dump(res, open(a.out, "w"), indent=1)
        if r["mismatch_at"] is not None or (r.get("end_state") or {}).get("big") or r["flags"]:
            print("STOP: mismatch", flush=True)
            code = 3
            break
    res["positions_verified"] = sum(w["positions_ok"] for w in res["windows"])
    res["owned_verified"] = sum(w["owned"] for w in res["windows"])
    json.dump(res, open(a.out, "w"), indent=1)
    print(f"verified {res['positions_verified']} positions, {res['owned_verified']} owned", flush=True)
    sys.exit(code)


if __name__ == "__main__":
    main()
