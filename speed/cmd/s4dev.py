REPLAY_KEYS=10; REPLAY_ROUNDS=[(1,9)]; REPLAY_OUT="results/s4_dev.jsonl"
import torch; torch.set_grad_enabled(False)
import copy, gc, importlib, json, os, time
import numpy as np
import torch.nn.functional as F
import sys
if "batchrun" in sys.modules:
    importlib.reload(TL); del sys.modules["batchrun"]
import batchrun as BR2
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
TL.build_v2(ctx)
tau = chat.meta["tau_dim"]
nq = ctx.nq
if not hasattr(ctx, "head_v3"):
    ctx.head_v3 = chat.model.lm_head.weight[:nq, :tau + 1].contiguous()
B = globals().get("REPLAY_B", 8)
ROWS = 8
if not hasattr(ctx, "exs"):
    ctx.exs = BR2.make_engines(ctx, 16)
    ctx.exp = BR2.make_engines(ctx, 1)[0]
def compare(saved, r):
    """Tokens against chain3's record."""
    d = {}
    a, b = saved["calls"], r["calls"]
    d["n_calls"] = len(a) == len(b)
    d["ids"] = all(x["ids"] == y["ids"] for x, y in zip(a, b))
    d["responses"] = all(x.get("response_ids") == y.get("response_ids") for x, y in zip(a, b))
    d["final"] = saved["final"] == r["final"]
    d["status"] = saved["status"] == r["status"]
    d["prose"] = saved["no_call_text"] == r["no_call_text"]
    d["chip"] = saved["chip_tokens"] == r["chip_tokens"]
    d["qwen"] = saved["qwen_tokens"] == r["qwen_tokens"]
    d["echo"] = saved["echo_tokens"] == r["echo_tokens"]
    d["correct"] = saved["correct"] == r["correct"]
    return d
saved = {}
for line in open(TL.CHAIN3):
    x = json.loads(line)
    if not x["verified_positions"]:
        saved[(x["graph"], x["id"])] = x
keys = list(saved)
LIMIT = globals().get("REPLAY_KEYS", None)
if LIMIT:
    keys = keys[:LIMIT]
OUTP = globals().get("REPLAY_OUT", "results/s4_replay.jsonl")
ROUNDS = globals().get("REPLAY_ROUNDS", [(6, 24), (6, 24), (6, 24), (0, 99)])
out = open(OUTP, "a", buffering=1)
meta = {"rounds": [], "shared_gpu": True, "B": B}
i = 0
for ns, nf in ROUNDS:
    slow = keys[i:i + ns]; i += ns
    fast = keys[i:i + nf]; i += nf
    rnd = {}
    # slow path
    t0 = time.time(); toks = 0
    for k in slow:
        g, q = TL.question(saved[k])
        r = C2.run_question(ec, g, q, nq, 1800, tool, verify=False, question_handles=False, told=True, rule=False)
        d = compare(saved[k], r)
        toks += r["qwen_tokens"] + r["echo_tokens"]
        out.write(json.dumps({"key": k, "path": "slow", "same": d, "seconds": r["seconds"], "qwen": r["qwen_tokens"], "echo": r["echo_tokens"], "status": r["status"], "lock": r["lock_error"]}) + "\n")
        print("slow", k, all(d.values()), r["seconds"], flush=True)
        torch.mps.empty_cache()
    rnd["slow"] = {"n": len(slow), "s": round(time.time() - t0, 1), "tokens": toks}
    # batched path
    items = []
    for k in fast:
        g, q = TL.question(saved[k])
        items.append((g, q, k))
    res = []
    def done(tag, r):
        d = compare(saved[tag], r)
        res.append(r)
        out.write(json.dumps({"key": tag, "path": "batched", "same": d, "seconds": r["seconds"], "qwen": r["qwen_tokens"], "echo": r["echo_tokens"], "status": r["status"], "lock": r["lock_error"], "gpu_text_steps": r["gpu_text_steps"], "prefill_seconds": r["prefill_seconds"], "first_bad": None if all(d.values()) else [c["ids"][:60] for c in r["calls"]]}) + "\n")
        print("batched", tag, all(d.values()), r["seconds"], {k_: v for k_, v in d.items() if not v}, flush=True)
    t0 = time.time()
    st = BR2.drive(ctx, items, B, tool, ctx.v2_layers, ctx.head_v3, tau, done, ctx.exs, ctx.exp) if items else {}
    rnd["batched"] = {"n": len(items), "s": round(time.time() - t0, 1), "tokens": sum(r["qwen_tokens"] + r["echo_tokens"] for r in res), "stats": st}
    meta["rounds"].append(rnd)
    print(json.dumps(rnd), flush=True)
    json.dump(meta, open(OUTP.replace(".jsonl", ".json"), "w"), indent=1)
    torch.mps.empty_cache()
    if i >= len(keys):
        break
print(D.mem())
