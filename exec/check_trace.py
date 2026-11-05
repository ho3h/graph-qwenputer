"""Criterion 1 and 2 of REGISTRATION.md: the residual leaving the executor against the saved stock residual, dim by dim, bit by bit, at every position of the saved traces. No model is loaded:
dims below chip_dims_offset are the embedding row, read from the checkpoint by mmap; the rest is the kept dims and zeros.

    python check_trace.py --trace results/trace --out results/check.json              # acceptance
    python check_trace.py --trace results/trace --job tiny-ten --mutate seed:0:40 --out results/negative.json   # the negative control
"""
import argparse
import hashlib
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import decode as D  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from safetensors import safe_open  # noqa: E402

from chipformer.rv import core  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402
from cexec import CExec  # noqa: E402


class Rows:
    """The merged embedding's rows, bit patterns of the first d0 dims, read lazily from the checkpoint."""

    def __init__(self, d0):
        idx = json.load(open(os.path.join(C.CKPT, "model.safetensors.index.json")))["weight_map"]
        self.f = safe_open(os.path.join(C.CKPT, idx["model.embed_tokens.weight"]), framework="pt")
        self.s = self.f.get_slice("model.embed_tokens.weight")
        self.d0 = d0
        self.cache = {}

    def digest(self, mid):
        if mid not in self.cache:
            t = self.s[mid: mid + 1, : self.d0]
            assert t.dtype == torch.bfloat16
            self.cache[mid] = int.from_bytes(hashlib.blake2b(t[0].view(torch.uint16).numpy().tobytes(), digest_size=8).digest(), "little")
        return self.cache[mid]


def bits_of(keep):
    """fp32 -> (bf16 bit patterns after rounding, whether each value was already exactly bf16)."""
    u = keep.view(np.uint32)
    r = (u + 0x7FFF + ((u >> 16) & 1)) & 0xFFFF0000
    return (r >> 16).astype(np.uint16), r == u


def job_stream(L, job):
    g = job["graph"] if isinstance(job["graph"], dict) else json.load(open(D.graph_path(job["graph"])[0]))
    calls = [tuple(x) for x in job["calls"]]
    prompt = D.prompt_for(L, g, job.get("text") or "Answer with the graph tools.")
    m0, stream, own, ses = D.session_for(L, g, prompt, calls, job.get("setup"), between=" ", tail="Done.")
    return prompt, m0, stream, own, ses


def compare(L, ex, rows, tr, prompt, stream, own, keep_cols, limit_first=8):
    """One job. Returns the tally; nothing is rounded: a position counts as exact only when every one of its 3,968 dims has the same bf16 bit pattern as stock."""
    meta = json.loads(str(tr["meta"]))
    n = meta["positions"]
    assert tr["tokens"].shape[0] == n
    mids = np.array([C.to_model(L.v0, t) for t in stream[:n]], np.int32)
    assert meta["prompt"] == prompt and (tr["tokens"] == mids).all(), "the trace is not this stream"
    ex.start([C.to_stream(L.v0, i) for i in prompt])
    t0 = time.perf_counter()
    keep = ex.run(stream[:n])
    run_s = time.perf_counter() - t0
    kb, exact = bits_of(keep)
    ptr, idx, bits, low = tr["ptr"], tr["idx"], tr["bits"], tr["low"]
    d0 = meta["d0"]
    out = {"job": meta["name"], "positions": n, "stream": meta["stream"], "finished": meta["finished"], "owned": int(np.sum(tr["own"])), "chip_tokens": int((mids >= L.v0).sum()), "text_tokens": int((mids < L.v0).sum()),
           "stock_wrong": meta.get("wrong"), "stock_not_owned_fired": meta.get("not_owned_fired"), "stock_head_mismatch": meta.get("head_mismatch"),
           "positions_all_bits_equal": 0, "positions_differing": 0, "dims_differing": 0, "only_sign_of_zero": 0, "low_differing": 0, "stock_residue_outside_keep": 0,
           "kept_fp32_not_exactly_bf16": int((~exact).sum()), "run_seconds": round(run_s, 3), "flags": ex.flags(), "first": []}
    keep_ix = {int(c): i for i, c in enumerate(keep_cols)}
    kc = np.array(keep_cols)
    for i in range(n):
        a, b = ptr[i], ptr[i + 1]
        stock = dict(zip(idx[a:b].tolist(), bits[a:b].tolist()))
        mine = {int(c): int(v) for c, v in zip(kc, kb[i]) if v}
        ok = stock == mine
        lowok = rows.digest(int(mids[i])) == int(low[i])
        if lowok:
            pass
        else:
            out["low_differing"] += 1
        if ok and lowok:
            out["positions_all_bits_equal"] += 1
        else:
            out["positions_differing"] += 1
            diff = sorted(d for d in set(stock) | set(mine) if stock.get(d, 0) != mine.get(d, 0))
            out["dims_differing"] += len(diff)
            if diff and all(stock.get(d, 0) & 0x7FFF == 0 and mine.get(d, 0) & 0x7FFF == 0 for d in diff):
                out["only_sign_of_zero"] += 1
            res = [d for d in diff if d not in keep_ix]
            out["stock_residue_outside_keep"] += len(res)
            if len(out["first"]) < limit_first:
                out["first"].append({"i": i, "mid": int(mids[i]), "own": bool(tr["own"][i]), "low_ok": lowok, "dims": [{"dim": d, "stock": hex(stock.get(d, 0)), "exec": hex(mine.get(d, 0))} for d in diff[:8]]})
    return out


def corruptions(seed, n):
    """Wrong executors: each changes one number in the tables, chosen by the seed, or one structural rule."""
    rng = random.Random(seed)
    out = []
    for k in range(n):
        tab = rng.choice(("tw", "tw", "tw", "ec", "ucoef", "o_w", "p_r", "uout", "fan_row"))
        out.append({"table": tab, "u": rng.random(), "how": rng.choice(("double", "negate", "plus_bit")) if tab not in ("uout", "fan_row") else "shift"})
    return out


def apply_corruption(A, m):
    a = A[m["table"]]
    i = int(m["u"] * len(a))
    old = a[i].item()
    if m["how"] == "double":
        a[i] = old * 2 if old else 1.0
    elif m["how"] == "negate":
        a[i] = -old if old else 1.0
    elif m["how"] == "plus_bit":
        a[i] = old * (1 + 1 / 128) if old else 2.0**-14
    else:
        a[i] = (old ^ 1)
    m["index"], m["old"], m["new"] = i, old, a[i].item()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--plan", default=os.path.join(HERE, "plan_accept.json"))
    ap.add_argument("--job", default=None, help="comma-separated; default every saved trace")
    ap.add_argument("--max-positions", type=int, default=None)
    ap.add_argument("--mutate", default=None, help="seed:S:N  table corruptions, one at a time; each is a fresh executor run against the trace")
    ap.add_argument("--flip-trace", default=None, help="seed:S:N  flip one bit of the saved stock data (a kept dim, or the low digest); the unchanged executor must then fail at exactly that position")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    L = C.Lite()
    d0 = L.meta["chip_dims_offset"]
    keep_cols = L.meta["code_dims"] + [L.meta["tau_dim"], L.meta["mu_dim"]]
    assert len(keep_cols) == len(L.c.keep)
    rows = Rows(d0)
    plan = {j["name"]: j for j in json.load(open(a.plan))}
    names = a.job.split(",") if a.job else [n for n in plan if os.path.exists(os.path.join(a.trace, n + ".npz"))]
    res = {"engine": None, "elf_sha256": hashlib.sha256(open(C.X.build_elf(), "rb").read()).hexdigest(), "jobs": []}
    if a.mutate:
        _, sd, nn = a.mutate.split(":")
        res["mutations"] = []
        name = names[0]
        tr = dict(np.load(os.path.join(a.trace, name + ".npz")))
        prompt, m0, stream, own, ses = job_stream(L, plan[name])
        core.snapshot(L.c, m0)
        for m in corruptions(int(sd), int(nn)):
            ex = CExec(L.c, L.T, corrupt=lambda A, m=m: apply_corruption(A, m))
            r = compare(L, ex, rows, _limit(tr, a.max_positions), prompt, stream, own, keep_cols, limit_first=1)
            r.pop("flags"), r.pop("job")
            res["mutations"].append({**m, "caught": r["positions_differing"] > 0, "positions_differing": r["positions_differing"], "first_i": r["first"][0]["i"] if r["first"] else None,
                                     "first": r["first"][:1], "positions": r["positions"], "flags": ex.flags()})
            print(json.dumps(res["mutations"][-1])[:240], flush=True)
            json.dump(res, open(a.out, "w"), indent=1)
        res["caught"] = sum(m["caught"] for m in res["mutations"])
        res["tried"] = len(res["mutations"])
        print("caught", res["caught"], "of", res["tried"], flush=True)
        json.dump(res, open(a.out, "w"), indent=1)
        return
    if a.flip_trace:
        _, sd, nn = a.flip_trace.split(":")
        rng = random.Random(int(sd))
        name = names[0]
        tr0 = dict(np.load(os.path.join(a.trace, name + ".npz")))
        prompt, m0, stream, own, ses = job_stream(L, plan[name])
        core.snapshot(L.c, m0)
        ex = CExec(L.c, L.T)
        res["engine"] = ex.lib_hash
        res["flips"] = []
        n = json.loads(str(tr0["meta"]))["positions"]
        if a.max_positions:
            n = min(n, a.max_positions)
        for k in range(int(nn)):
            tr = _limit(dict(tr0), n)
            tr["bits"], tr["low"] = tr["bits"].copy(), tr["low"].copy()
            i = rng.randrange(n)
            bit = rng.randrange(16)
            if rng.random() < 0.5:
                j = int(tr["ptr"][i] + rng.randrange(max(1, int(tr["ptr"][i + 1] - tr["ptr"][i]))))
                if tr["ptr"][i + 1] > tr["ptr"][i]:
                    tr["bits"][j] ^= 1 << bit
                what = "kept"
            else:
                tr["low"][i] ^= 1 << bit
                what = "low digest"
            ex.p.flags = 0
            r = compare(L, ex, rows, tr, prompt, stream, own, keep_cols, limit_first=1)
            caught_here = bool(r["first"]) and r["first"][0]["i"] == i and r["positions_differing"] == 1
            res["flips"].append({"position": i, "what": what, "bit": bit, "positions_differing": r["positions_differing"], "first_i": r["first"][0]["i"] if r["first"] else None, "caught_exactly_there": caught_here})
            print(json.dumps(res["flips"][-1]), flush=True)
        res["caught"] = sum(f["caught_exactly_there"] for f in res["flips"])
        json.dump(res, open(a.out, "w"), indent=1)
        return
    ex = None
    for name in names:
        tr = dict(np.load(os.path.join(a.trace, name + ".npz")))
        prompt, m0, stream, own, ses = job_stream(L, plan[name])
        core.snapshot(L.c, m0)
        if ex is None:
            ex = CExec(L.c, L.T)
            res["engine"] = ex.lib_hash
        ex.p.flags = 0
        r = compare(L, ex, rows, _limit(tr, a.max_positions), prompt, stream, own, keep_cols)
        res["jobs"].append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "first"}), flush=True)
        if r["first"]:
            print(json.dumps(r["first"][:3])[:600], flush=True)
        json.dump(res, open(a.out, "w"), indent=1)
    res["totals"] = {k: sum(j[k] for j in res["jobs"]) for k in ("positions", "owned", "chip_tokens", "text_tokens", "positions_all_bits_equal", "positions_differing", "dims_differing", "only_sign_of_zero", "low_differing", "stock_residue_outside_keep", "kept_fp32_not_exactly_bf16")}
    print(json.dumps(res["totals"]), flush=True)
    json.dump(res, open(a.out, "w"), indent=1)


def _limit(tr, n):
    if not n:
        return tr
    meta = json.loads(str(tr["meta"]))
    n = min(n, meta["positions"])
    meta["positions"] = n
    out = dict(tr)
    out["meta"] = json.dumps(meta)
    out["tokens"], out["own"], out["low"], out["head"] = tr["tokens"][:n], tr["own"][:n], tr["low"][:n], tr["head"][:n]
    return out


main()
