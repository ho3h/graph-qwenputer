# S1(b), (c), (d): a text step: encode against wait, by layer; V0, V1, V2 alternating on chain3's tokens; batch scaling.
import torch; torch.set_grad_enabled(False)
import copy, json, os, time
import numpy as np, torch
from chipformer.rv import bridge as BR, core
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
t0 = time.time()
TL.build_v2(ctx)
print("build_v2", round(time.time() - t0, 1), "mem", D.mem(), flush=True)
OUT = {"shared_gpu": True, "questions": [], "mem": D.mem()}
nq = ctx.nq
VARS = ("V0", "V1", "V2")

def run_question(r, tokens, free_extra=0):
    g, q = TL.question(r)
    m = D.parked_machine(g, chat.T, q.get("setup") or [])
    prompt = TL.prompt_of(chat, g, q, tool)
    out = chat._prefill(prompt)
    base = out.past_key_values
    core.snapshot(chat.c, m)
    cx.p.flags = 0
    ec.start(prompt)
    first = int(torch.argmax(out.logits[0, -1, :nq]))
    caches = {v: TL.clone_cache(base) for v in VARS}
    del base, out
    pos = len(prompt)
    res = {"graph": r["graph"], "id": r["id"], "steps": 0, "wall": {v: 0.0 for v in VARS}, "encode": {v: 0.0 for v in VARS}, "cpu": {v: 0.0 for v in VARS}, "logit_elems_differ": {"V1": 0, "V2": 0}, "argmax_differ": {"V1": 0, "V2": 0}, "wrong_vs_chain3": 0, "first_vs_chain3": first == tokens[0]}
    nxt = first
    i = 0
    n_free = 0
    order = 0
    while True:
        st = ec.stream(nxt)
        keep = cx.step(st).copy()
        hc = ec.hc(nxt, keep)
        ct = ec.code_token(keep)
        lg = {}
        vs = VARS[order % 3:] + VARS[:order % 3]
        order += 1
        for v in vs:                                       # alternating which goes first; each synced whole
            c0 = time.process_time()
            s = time.perf_counter()
            y = TL.step(ctx, v, hc, caches[v], pos)
            e = time.perf_counter()
            am = int(torch.argmax(y))
            w = time.perf_counter()
            res["wall"][v] += w - s
            res["encode"][v] += e - s
            res["cpu"][v] += time.process_time() - c0
            lg[v] = (y, am)
        b0 = TL.bits(lg["V0"][0])
        for v in ("V1", "V2"):
            res["logit_elems_differ"][v] += int((b0 != TL.bits(lg[v][0])).sum())
            res["argmax_differ"][v] += int(lg[v][1] != lg["V0"][1])
        pos += 1
        i += 1
        res["steps"] += 1
        am = lg["V0"][1]
        nn = ct if ct is not None else am
        if i < len(tokens):
            if nn != tokens[i]:
                res["wrong_vs_chain3"] += 1
            nxt = tokens[i]
        elif free_extra and n_free < free_extra and nn != chat.T.TCC and nn not in (248044, 248046):
            n_free += 1
            nxt = nn
        else:
            break
    del caches, lg
    for k in ("wall", "encode", "cpu"):
        res[k] = {v: round(x / res["steps"], 4) for v, x in res[k].items()}
    torch.mps.empty_cache()
    return res

rows = TL.sample(12)
for r in rows:
    c = r["calls"][0]
    toks = [chat.T.TCO] + c["ids"] + [chat.T.TCC]
    x = run_question(r, toks)
    OUT["questions"].append(x)
    print(json.dumps(x), flush=True)
    json.dump(OUT, open("results/s1b_steps.json", "w"), indent=1)
# long context: free-running prose after the call, with the context grown by forcing the saved call then 200 free tokens from a question that wrote prose
pr = TL.sample(2, need=lambda r: r["status"] == "no_call" and r["qwen_tokens"] > 500)
for r in pr:
    c = r["calls"][0]
    toks = [chat.T.TCO] + c["ids"]            # stop before TCC: the machine does not run in this stretch
    x = run_question(r, toks, free_extra=200)
    x["free_long"] = True
    OUT["questions"].append(x)
    print(json.dumps(x), flush=True)
    json.dump(OUT, open("results/s1b_steps.json", "w"), indent=1)
print("mem", D.mem())
