"""The merged checkpoint on MPS: teacher-forced checks and free decoding, on the vendored RvChat's stock-module path.

RvChat's chip layers run through the HF modules on MPS (its compaction and executor paths are CUDA-only). Each position:
a chip token runs the chip layers, a text token runs every layer; the circuit's token comes from the output code.

    python decode.py teacher --graph cities/c024 --n 3 --out results/m2_x.json   # from the vendored folder, memguarded
"""

import argparse
import copy
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import box as X  # noqa: E402

import torch  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core, hf  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402

CKPT = "/Volumes/LaCie/Models/x210-rvc"
DEV = os.path.join(X.X210, "data", "dev")
HT = X.HT
GIB = 2 ** 30


def mem():
    return {"mps_allocated_gib": round(torch.mps.current_allocated_memory() / GIB, 2),
            "mps_driver_gib": round(torch.mps.driver_allocated_memory() / GIB, 2)}


def load_chat(path=CKPT, device="mps", compact=False):
    """compact: the chip layers' linear maps reduced to their nonzero blocks (vendored fast.compact, qwen=False, the
    step RvChat itself takes on CUDA). Not stock modules: every use is labelled, and checked by the teacher run."""
    from chipformer.rv.chat import RvChat
    t0 = time.time()
    chat = RvChat(path, device=device, fast=False, executor=False)
    if compact:
        from chipformer.q35 import fast as F
        print(F.compact(chat.model, qwen=False, n_chip=chat.n_chip), flush=True)
        torch.mps.empty_cache()
    return chat, round(time.time() - t0, 1)


def graph_path(name):
    assert "heldout" not in name, name
    if name == "tiny":
        return os.path.join(X.X210, "host", "test", "tiny.graph.json"), os.path.join(X.X210, "host", "test", "tiny.questions.json")
    return os.path.join(DEV, name + ".graph.json"), os.path.join(DEV, name + ".questions.json")


def enc(T, fn, args):
    return T.encode(X.template_text(fn, args))


def parked_machine(g, T, setup=None):
    """The firmware parked with graph g in its DROM; `setup` calls already applied on the reference (host harness rule:
    a question's setup runs before the prompt). The state goes in as the snapshot."""
    m = X.machine_for(g)
    ses = BR.Session(T, m)
    for s in setup or []:
        ses.qwen([T.TCO] + enc(T, s["fn"], s["args"]) + [T.TCC])
    m.text = [bytes(S.TEXT_ROW)] * S.TEXT_ROWS
    return m


def to_model(chat, t):
    return chat.v0 + t if t < S.VOCAB else t - S.TEXT_TOKEN


@torch.no_grad()
def teacher(chat, prompt, machine, stream, own, hard_limit_s=None):
    """Prefill the prompt, inject the snapshot, feed `stream` (Session tokens). At every position: the circuit's token
    must equal the next stream token where the reference says the circuit owns it, and be None elsewhere. At an owned
    text position the stock head's argmax over the whole vocabulary must equal it too."""
    t00 = time.time()
    out = chat._prefill(prompt)
    cache = out.past_key_values
    prefill_s = time.time() - t00
    t0 = time.time()
    core.snapshot(chat.c, machine)
    hf.inject(chat.c, cache)
    snap_s = time.time() - t0
    pos = len(prompt)
    wrong, not_owned, head_bad = [], [], []
    owned_ok = n_chip = n_text = 0
    t_chip = t_text = 0.0
    done = 0
    for i, t in enumerate(stream):
        if hard_limit_s and time.time() - t00 > hard_limit_s:
            break
        mid = to_model(chat, t)
        chip_in = mid >= chat.v0
        ts = time.perf_counter()
        hc, logits = chat._layers(mid, cache, None if chip_in else pos)
        ct = chat.circuit_token(hc)
        q = None if chip_in else int(torch.argmax(logits))
        dt = time.perf_counter() - ts
        done = i + 1
        if chip_in:
            n_chip += 1
            t_chip += dt
        else:
            n_text += 1
            t_text += dt
            pos += 1
        if i + 1 == len(stream):
            break
        want = to_model(chat, stream[i + 1])
        if own[i]:
            if ct == want:
                owned_ok += 1
            else:
                wrong.append({"i": i, "got": ct, "want": want})
            if not chip_in and q != ct:
                head_bad.append({"i": i, "head": q, "circuit": ct})
        elif ct is not None:
            not_owned.append({"i": i, "got": ct})
    return {"positions": done, "stream": len(stream), "finished": done == len(stream), "owned_ok": owned_ok, "wrong": len(wrong), "first_wrong": wrong[:5],
            "not_owned_fired": len(not_owned), "first_not_owned": not_owned[:5], "head_mismatch": len(head_bad),
            "first_head": head_bad[:5], "chip_tokens": n_chip, "text_tokens": n_text, "chip_seconds": round(t_chip, 2),
            "text_seconds": round(t_text, 2), "prefill_seconds": round(prefill_s, 2), "snapshot_seconds": round(snap_s, 2),
            "prompt_tokens": len(prompt)}


def session_for(chat, g, prompt, calls, setup=None, between="", tail=""):
    """The reference's token stream after the prompt: Qwen's calls (teacher-forced), each with the machine's run."""
    T = chat.T
    m = parked_machine(g, T, setup)
    m0 = copy.deepcopy(m)
    ses = BR.Session(T, m)
    ses.history(prompt)
    k = len(ses.toks)
    for j, (fn, args) in enumerate(calls):
        if j and between:
            ses.qwen(T.encode(between))
        ses.qwen([T.TCO] + enc(T, fn, args) + [T.TCC])
    if tail:
        ses.qwen(T.encode(tail))
    return m0, ses.toks[k:], ses.own[k:], ses


def prompt_for(chat, g, text):
    msgs = [{"role": "system", "content": HT.system_prompt(g)}, {"role": "user", "content": text}]
    return chat.prompt_ids(msgs, tools=HT.TOOLS)


def teacher_job(chat, name, calls, setup=None, text=None, hard_limit_s=None):
    gp, qp = graph_path(name)
    g = json.load(open(gp))
    prompt = prompt_for(chat, g, text or "Answer with the graph tools.")
    m0, stream, own, ses = session_for(chat, g, prompt, calls, setup, between=" ", tail="Done.")
    r = teacher(chat, prompt, m0, stream, own, hard_limit_s=hard_limit_s)
    r.update(graph=name, calls=[f"{f} {a}" for f, a in calls], results=[chat.T.decode_bytes(e).decode("utf-8", "replace") for e in ses.runs])
    r["chip_per_s"] = round(r["chip_tokens"] / max(r["chip_seconds"], 1e-9), 2)
    r["text_per_s"] = round(r["text_tokens"] / max(r["text_seconds"], 1e-9), 2)
    r.update(mem())
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="JSON file: a list of {graph, calls: [[fn, args]..], setup?, text?}")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit-s", type=float, default=None, help="per job wall limit")
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--compact", action="store_true")
    a = ap.parse_args()
    chat, load_s = load_chat(a.ckpt, compact=a.compact)
    print(f"loaded in {load_s}s {mem()}, attn {chat.model.config._attn_implementation}", flush=True)
    res = {"ckpt": a.ckpt, "compact": a.compact, "load_seconds": load_s, "attn": chat.model.config._attn_implementation,
           "env": {k: os.environ.get(k) for k in ("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "PYTORCH_MPS_LOW_WATERMARK_RATIO")},
           "elf_sha256": __import__("hashlib").sha256(open(X.build_elf(), "rb").read()).hexdigest(), "jobs": []}
    for job in json.load(open(a.plan)):
        r = teacher_job(chat, job["graph"], [tuple(c) for c in job["calls"]], job.get("setup"), job.get("text"), a.limit_s)
        res["jobs"].append(r)
        print({k: r[k] for k in ("graph", "positions", "stream", "owned_ok", "wrong", "not_owned_fired", "head_mismatch", "chip_tokens", "text_tokens", "chip_per_s", "text_per_s", "mps_driver_gib")}, flush=True)
        json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
    json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
