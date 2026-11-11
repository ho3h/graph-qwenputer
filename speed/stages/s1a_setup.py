# S1(a): load phases and per-question set-up, in chain2.run_question's order, with the chain3 tool. Also S1(e), S1(f) on the same prefills.
import torch; torch.set_grad_enabled(False)
import copy, json, os, time
import numpy as np, torch
from transformers import DynamicCache
from chipformer.rv import bridge as BR, core
from transformers.masking_utils import create_causal_mask
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
OUT = {"load_phases": ctx.load_phases, "t_import": t_import, "shared_gpu": True, "questions": []}
print(json.dumps(ctx.load_phases, default=str)[:800])
print("mem", D.mem())
n_chip = chat.n_chip
stops = {}

def timed(t, k, f):
    s = time.perf_counter(); r = f(); t[k] = round(time.perf_counter() - s, 4); return r

def qwen_prefill(hc, cache=None, first_pos=0):
    """Qwen's layers on a run of residuals (1, n, 3968), as Qwen3_5TextModel.forward does it after the chip layers."""
    n = hc.shape[1]
    if cache is None:
        cache = DynamicCache(config=chat.model.config)
    tp = (torch.arange(n, device="mps") + first_pos).view(1, -1)
    pos = tp.view(1, 1, -1).expand(3, 1, -1)
    pe = chat.lm.rotary_emb(hc, pos)
    # Causal mask over keys seen so far + new. Whole prompt: same as stock's create_causal_mask.
    p = first_pos
    mask = torch.ones(n, p + n, dtype=torch.bool, device="mps").tril(p)[None, None]
    h = hc
    for i in range(n_chip, len(chat.lm.layers)):
        ty = chat.model.config.layer_types[i]
        h = chat.lm.layers[i](h, position_embeddings=pe, attention_mask=mask if ty == "full_attention" else None, position_ids=tp, past_key_values=cache)
    logits = chat.model.lm_head(chat.lm.norm(h)[:, -1:, :])
    return logits[0, -1], cache

rows = TL.sample(12)
common_all = None
prompts = []
for r in rows:
    g, q = TL.question(r)
    t = {"graph": r["graph"], "id": r["id"], "chain3_seconds_overhead": round(r["seconds"] - r["text_seconds"] - r["chip_seconds"], 2)}
    graph = TL.reflib.Graph(g)
    setup = q.get("setup") or []
    for s in setup:
        graph.call(s["fn"], s["args"])
    m = timed(t, "parked_machine", lambda: D.parked_machine(g, chat.T, setup))
    prompt = timed(t, "prompt_ids", lambda: TL.prompt_of(chat, g, q, tool))
    assert len(prompt) == r["prompt_tokens"], (len(prompt), r["prompt_tokens"])
    def mk():
        lk = BR.Session(chat.T, copy.deepcopy(m)); lk.history(prompt); return lk
    lock = timed(t, "lock", mk)
    out = timed(t, "prefill_stock", lambda: (lambda o: (o, o.logits[0, -1].cpu()))(chat._prefill(prompt)))
    out, lg = out
    cache = out.past_key_values
    timed(t, "snapshot", lambda: core.snapshot(chat.c, m))
    cx.p.flags = 0
    stream = [ec.stream(i) for i in prompt]
    timed(t, "engine_start", lambda: ec.start(prompt))
    # S1(e): prefill from the engine's residual
    capt = {}
    h_ = chat.lm.layers[n_chip - 1].register_forward_hook(lambda mod, inp, o: capt.__setitem__("hc", (o[0] if isinstance(o, tuple) else o).detach()))
    timed(t, "prefill_stock_again", lambda: chat._prefill(prompt))
    h_.remove()
    stock_hc = TL.bits(capt["hc"][0])
    cx.clear()
    keep = cx.run(stream, keep=True).copy()
    u = keep.view(np.uint32)
    rr = (u + 0x7FFF + ((u >> 16) & 1)) & 0xFFFF0000
    hcb = np.zeros((len(prompt), ec.hidden), np.uint16)
    emb = chat.lm.embed_tokens.weight
    ids = torch.tensor(prompt, device="mps")
    hcb[:, :ec.d0] = TL.bits(emb[ids, :ec.d0])
    hcb[:, ec.keep_cols_np] = (rr >> 16).astype(np.uint16)
    t["hc_dims_differ"] = int((hcb != stock_hc).sum())
    t["hc_positions_differ"] = int((hcb != stock_hc).any(1).sum())
    hc = torch.from_numpy(hcb).to("mps").view(torch.bfloat16).unsqueeze(0)
    s = time.perf_counter()
    lg2, cache2 = qwen_prefill(hc)
    lg2c = lg2.cpu()
    t["prefill_engine_hc"] = round(time.perf_counter() - s, 4)
    t["hc_prefill_logit_elems_differ"] = int((TL.bits(lg) != TL.bits(lg2c)).sum())
    a, b = TL.state_bits(cache, n_chip), TL.state_bits(cache2, n_chip)
    t["hc_prefill_states_differ"] = sum(x != y for x, y in zip(a, b))
    # S1(f): split prefill
    prompts.append(prompt)
    ct = 0
    if len(prompts) > 1:
        p0 = prompts[0]
        while ct < min(len(p0), len(prompt)) and p0[ct] == prompt[ct]:
            ct += 1
    t["common_with_first"] = ct
    t["prompt_tokens"] = len(prompt)
    for name, cut in (("at_common_" , None), ("at_64", None)):
        pass
    # shared prefix: longest prefix with the prompt of the same run's first question when there is one; else first 256
    cuts = {"c256": 256, "c320": 320, "c301": 301}
    for name, c in cuts.items():
        s = time.perf_counter()
        _, ca = qwen_prefill(hc[:, :c])
        tp1 = time.perf_counter() - s
        s = time.perf_counter()
        lg3, ca = qwen_prefill(hc[:, c:], ca, first_pos=c)
        lg3c = lg3.cpu()
        t[f"split_{name}_suffix_s"] = round(time.perf_counter() - s, 4)
        t[f"split_{name}_prefix_s"] = round(tp1, 4)
        t[f"split_{name}_logit_elems_differ"] = int((TL.bits(lg) != TL.bits(lg3c)).sum())
        t[f"split_{name}_argmax_same"] = bool(lg[:ctx.nq].argmax() == lg3c[:ctx.nq].argmax())
        t[f"split_{name}_states_differ"] = sum(x != y for x, y in zip(a, TL.state_bits(ca, n_chip)))
        del ca
    timed(t, "empty_cache", torch.mps.empty_cache)
    OUT["questions"].append(t)
    print(json.dumps(t))
    del out, cache, cache2
json.dump(OUT, open("results/s1a_setup.json", "w"), indent=1, default=str)
print("mem", D.mem())
