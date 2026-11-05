"""The reference for acceptance: the residual leaving the stock chip layers, saved at every position of the plan's teacher-forced streams.

    python stock_trace.py --plan ../../exec/plan_accept.json --outdir ../../exec/results/trace  # from the vendored folder, memguarded (32)

Stock means RvChat(fast=False, executor=False): HF modules on MPS in bf16, sdpa; nothing compacted. Every position saves the bf16 bit patterns of the
whole 3968-dim residual: dims >= chip_dims_offset as (index, bits) of the nonzero bit patterns, dims below it as a digest (they should be the embedding
row, checked offline against the checkpoint). A text position also saves the stock head's argmax. Partial results are flushed every --flush positions,
so a killed run still leaves what it measured.
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import decode as D  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

from chipformer.rv import core, hf  # noqa: E402


def save(path, rec, meta):
    tmp = path + ".tmp.npz"
    np.savez_compressed(tmp, tokens=np.array(rec["mid"], np.int32), own=np.array(rec["own"], bool), ptr=np.array(rec["ptr"], np.int64),
                        idx=np.array(rec["idx"], np.uint16), bits=np.array(rec["bits"], np.uint16), low=np.array(rec["low"], np.uint64),
                        head=np.array(rec["head"], np.int32), meta=np.array(json.dumps(meta)))
    os.replace(tmp, path)


@torch.no_grad()
def run_job(chat, job, outdir, flush, deadline):
    g = job["graph"] if isinstance(job["graph"], dict) else json.load(open(D.graph_path(job["graph"])[0]))
    calls = [tuple(x) for x in job["calls"]]
    prompt = D.prompt_for(chat, g, job.get("text") or "Answer with the graph tools.")
    m0, stream, own, ses = D.session_for(chat, g, prompt, calls, job.get("setup"), between=" ", tail="Done.")
    path = os.path.join(outdir, job["name"] + ".npz")
    if os.path.exists(path):
        old = np.load(path)
        if json.loads(str(old["meta"]))["finished"]:
            print("already done", job["name"], flush=True)
            return
    d0 = chat.meta["chip_dims_offset"]
    meta = {"name": job["name"], "calls": [f"{f} {json.dumps(a, ensure_ascii=False)}" for f, a in calls], "prompt": prompt, "stream": len(stream), "d0": d0,
            "elf_sha256": hashlib.sha256(open(C.X.build_elf(), "rb").read()).hexdigest(), "finished": False, "positions": 0, "ckpt": C.CKPT,
            "attn": chat.model.config._attn_implementation, "dtype": "bf16", "device": "mps", "results": [chat.T.decode_bytes(e).decode("utf-8", "replace") for e in ses.runs],
            "graph": job["graph"] if not isinstance(job["graph"], dict) else "inline:" + job["name"], "has_setup": bool(job.get("setup"))}
    out = chat._prefill(prompt)
    cache = out.past_key_values
    core.snapshot(chat.c, m0)
    hf.inject(chat.c, cache)
    pos = len(prompt)
    rec = {"mid": [], "own": [], "ptr": [0], "idx": [], "bits": [], "low": [], "head": []}
    t_chip = t_text = 0.0
    n_chip = n_text = wrong = fired = head_bad = 0
    t0 = time.time()
    for i, t in enumerate(stream):
        if time.time() > deadline:
            print("deadline", flush=True)
            break
        mid = D.to_model(chat, t)
        chip_in = mid >= chat.v0
        ts = time.perf_counter()
        hc, logits = chat._layers(mid, cache, None if chip_in else pos)
        hcu = hc.detach().cpu().view(torch.uint16).numpy()     # forces the step; bit patterns of the bf16 residual
        q = -1 if chip_in else int(torch.argmax(logits))
        dt = time.perf_counter() - ts
        ct = chat.circuit_token(hc)
        hi = np.nonzero(hcu[d0:])[0]
        rec["mid"].append(mid)
        rec["own"].append(bool(own[i]))
        rec["idx"].extend((hi + d0).tolist())
        rec["bits"].extend(hcu[d0:][hi].tolist())
        rec["ptr"].append(len(rec["idx"]))
        rec["low"].append(int.from_bytes(hashlib.blake2b(hcu[:d0].tobytes(), digest_size=8).digest(), "little"))
        rec["head"].append(q)
        if chip_in:
            n_chip += 1
            t_chip += dt
        else:
            n_text += 1
            t_text += dt
            pos += 1
        if i + 1 < len(stream):
            want = D.to_model(chat, stream[i + 1])
            if own[i]:
                wrong += ct != want
                head_bad += (not chip_in) and q != ct
            else:
                fired += ct is not None
        if (i + 1) % flush == 0:
            meta.update(positions=i + 1, wrong=wrong, not_owned_fired=fired, head_mismatch=head_bad, chip_tokens=n_chip, text_tokens=n_text,
                        chip_seconds=round(t_chip, 1), text_seconds=round(t_text, 1))
            save(path, rec, meta)
            print(f"{job['name']} {i + 1}/{len(stream)} wrong={wrong} fired={fired} head={head_bad} chip/s={n_chip / max(t_chip, 1e-9):.1f} text/s={n_text / max(t_text, 1e-9):.2f} {time.time() - t0:.0f}s", flush=True)
    done = len(rec["mid"]) == len(stream)
    meta.update(positions=len(rec["mid"]), finished=done, wrong=wrong, not_owned_fired=fired, head_mismatch=head_bad, chip_tokens=n_chip, text_tokens=n_text,
                chip_seconds=round(t_chip, 1), text_seconds=round(t_text, 1), mem=D.mem())
    save(path, rec, meta)
    print(json.dumps({k: meta[k] for k in ("name", "positions", "stream", "finished", "wrong", "not_owned_fired", "head_mismatch", "chip_tokens", "text_tokens", "chip_seconds", "text_seconds")}), flush=True)
    del cache
    torch.mps.empty_cache()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--only", default=None)
    ap.add_argument("--flush", type=int, default=5000)
    ap.add_argument("--hours", type=float, default=3.5)
    a = ap.parse_args()
    deadline = time.time() + a.hours * 3600
    os.makedirs(a.outdir, exist_ok=True)
    plan = json.load(open(a.plan))
    if a.only:
        keep = a.only.split(",")
        plan = sorted((j for j in plan if j["name"] in keep), key=lambda j: keep.index(j["name"]))     # in the order asked for
    chat, load_s = D.load_chat(C.CKPT)
    print(f"loaded {load_s}s {D.mem()} attn {chat.model.config._attn_implementation}", flush=True)
    for job in plan:
        run_job(chat, job, a.outdir, a.flush, deadline)
        if time.time() > deadline:
            break


main()
