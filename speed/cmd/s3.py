import torch; torch.set_grad_enabled(False)
import copy, json, os, time
import numpy as np
import torch.nn.functional as F
from chipformer.rv import core
from transformers.models.qwen3_5 import modeling_qwen3_5 as M
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
TL.build_v2(ctx)
nq = ctx.nq
OUT = {"shared_gpu": True}
r = TL.sample(1)[0]
g, q = TL.question(r)
m = D.parked_machine(g, chat.T, q.get("setup") or [])
prompt = TL.prompt_of(chat, g, q, tool)
out = chat._prefill(prompt)
base = out.past_key_values
core.snapshot(chat.c, m)
cx.p.flags = 0
ec.start(prompt)
toks = [chat.T.TCO] + r["calls"][0]["ids"] + [chat.T.TCC]
pos0 = len(prompt)
hcs = []
for nxt in toks[:6]:
    keep = cx.step(ec.stream(nxt)).copy()
    hcs.append(ec.hc(nxt, keep))
types = chat.model.config.layer_types
layers = chat.lm.layers
# (a) Layer by layer: same input to each layer at batch 1 and batch 2, and each op
def rows(t):
    return t[0].detach().cpu().view(torch.uint16).numpy().copy() if t.dtype == torch.bfloat16 else t[0].detach().cpu().numpy().copy()
def eq(a, b, name, res):
    d = int((rows(a) != rows(b)).sum())
    res[name] = d
    return d
c1, c2 = TL.clone_cache(base), TL.repeat_cache(base, 2)
res_layers = {}
first = {"linear_attention": None, "full_attention": None}
h1 = hcs[0].view(1, 1, -1)
p1 = torch.full((4, 1, 1), pos0, device="mps", dtype=torch.long)
p2 = torch.full((4, 2, 1), pos0, device="mps", dtype=torch.long)
pe1 = chat.lm.rotary_emb(h1, p1[1:])
pe2 = chat.lm.rotary_emb(h1.repeat(2, 1, 1), p2[1:])
OUT["rotary_diff"] = [int((rows(a) != rows(b)).sum()) for a, b in zip(pe1, pe2)]
ops = {}
def diag_linear(i, x, c1, c2):
    la = layers[i].linear_attn; lay = layers[i]
    res = {}
    n1 = lay.input_layernorm(x); n2 = lay.input_layernorm(x.repeat(2, 1, 1))
    eq(n1, n2, "input_norm", res)
    q1, q2 = la.in_proj_qkv(n1), la.in_proj_qkv(n2)
    eq(q1, q2, "in_proj_qkv", res)
    z1, z2 = la.in_proj_z(n1), la.in_proj_z(n2); eq(z1, z2, "in_proj_z", res)
    b1, b2 = la.in_proj_b(n1), la.in_proj_b(n2); eq(b1, b2, "in_proj_b", res)
    a1, a2 = la.in_proj_a(n1), la.in_proj_a(n2); eq(a1, a2, "in_proj_a", res)
    cs1, cs2 = c1.layers[i].conv_states[0].clone(), c2.layers[i].conv_states[0].clone()
    m1 = M.causal_conv1d_update(q1.transpose(1, 2), cs1, la.conv1d.weight.squeeze(1), la.conv1d.bias, la.activation).transpose(1, 2)
    m2 = M.causal_conv1d_update(q2.transpose(1, 2), cs2, la.conv1d.weight.squeeze(1), la.conv1d.bias, la.activation).transpose(1, 2)
    eq(m1, m2, "conv", res)
    def split(m, B):
        qq, kk, vv = torch.split(m, [la.key_dim, la.key_dim, la.value_dim], dim=-1)
        qq = qq.reshape(B, 1, -1, la.head_k_dim).repeat_interleave(2, dim=2)
        kk = kk.reshape(B, 1, -1, la.head_k_dim).repeat_interleave(2, dim=2)
        vv = vv.reshape(B, 1, -1, la.head_v_dim)
        return qq, kk, vv
    S1 = split(m1, 1); S2 = split(m2, 2)
    g1 = -la.A_log.float().exp() * F.softplus(a1.float() + la.dt_bias)
    g2 = -la.A_log.float().exp() * F.softplus(a2.float() + la.dt_bias)
    eq(g1, g2, "decay_g", res)
    o1, st1 = M.torch_recurrent_gated_delta_rule(*S1, g=g1, beta=b1.sigmoid(), initial_state=c1.layers[i].recurrent_states[0], output_final_state=True, use_qk_l2norm_in_kernel=True)
    o2, st2 = M.torch_recurrent_gated_delta_rule(*S2, g=g2, beta=b2.sigmoid(), initial_state=c2.layers[i].recurrent_states[0], output_final_state=True, use_qk_l2norm_in_kernel=True)
    eq(o1, o2, "delta_out", res); eq(st1, st2, "delta_state", res)
    n1b = la.norm(o1.reshape(-1, la.head_v_dim), z1.reshape(-1, la.head_v_dim)).reshape(1, 1, -1)
    n2b = la.norm(o2.reshape(-1, la.head_v_dim), z2.reshape(-1, la.head_v_dim)).reshape(2, 1, -1)
    eq(n1b, n2b, "gated_norm", res)
    y1, y2 = la.out_proj(n1b), la.out_proj(n2b)
    eq(y1, y2, "out_proj", res)
    x1 = x + y1; x2 = x.repeat(2, 1, 1) + y2
    eq(x1, x2, "residual", res)
    return res
def diag_full(i, x, c1, c2):
    a = layers[i].self_attn; lay = layers[i]
    res = {}
    n1 = lay.input_layernorm(x); n2 = lay.input_layernorm(x.repeat(2, 1, 1))
    eq(n1, n2, "input_norm", res)
    def parts(n, B, pe, kv):
        shape = (B, 1)
        hshape = (*shape, -1, a.head_dim)
        qs, gate = torch.chunk(a.q_proj(n).view(*shape, -1, a.head_dim * 2), 2, dim=-1)
        gate = gate.reshape(*shape, -1)
        qs = a.q_norm(qs.view(hshape)).transpose(1, 2)
        ks = a.k_norm(a.k_proj(n).view(hshape)).transpose(1, 2)
        vs = a.v_proj(n).view(hshape).transpose(1, 2)
        qr, kr = M.apply_rotary_pos_emb(qs, ks, pe[0], pe[1])
        kk = torch.cat([kv.keys, kr], dim=-2); vv = torch.cat([kv.values, vs], dim=-2)
        return gate, qs, ks, vs, qr, kr, kk, vv
    P1 = parts(n1, 1, pe1, c1.layers[i]); P2 = parts(n2, 2, pe2, c2.layers[i])
    for nm, u, v in zip(("gate", "q", "k", "v", "qrot", "krot", "keys", "values"), P1, P2):
        eq(u, v, nm, res)
    def sd(qr, kk, vv):
        return F.scaled_dot_product_attention(qr, M.repeat_kv(kk, a.num_key_value_groups), M.repeat_kv(vv, a.num_key_value_groups), attn_mask=None, dropout_p=0.0, scale=a.scaling, is_causal=False)
    A1 = sd(P1[4], P1[6], P1[7]); A2 = sd(P2[4], P2[6], P2[7])
    eq(A1, A2, "sdpa", res)
    # sdpa with row-by-row
    A3 = torch.cat([sd(P2[4][j:j + 1], P2[6][j:j + 1], P2[7][j:j + 1]) for j in range(2)])
    eq(A1, A3, "sdpa_rowwise", res)
    return res
x = h1
stream_first = {}
for i in range(chat.n_chip, len(layers)):
    y1 = layers[i](x, position_embeddings=pe1, attention_mask=None, position_ids=p1[0], past_key_values=TL.clone_cache(c1))
    y2 = layers[i](x.repeat(2, 1, 1), position_embeddings=pe2, attention_mask=None, position_ids=p2[0], past_key_values=TL.clone_cache(c2))
    d = int((rows(y1) != rows(y2)).sum())
    res_layers[i] = d
    ty = types[i]
    if d and first[ty] is None:
        first[ty] = i
        ops[ty] = (diag_linear if ty == "linear_attention" else diag_full)(i, x, c1, c2)
        print(ty, i, json.dumps(ops[ty]), flush=True)
    x = y1
    torch.mps.empty_cache() if i % 8 == 0 else None
OUT["per_layer_elems_differ"] = res_layers
OUT["first_differing"] = first
OUT["ops"] = ops
print(json.dumps(res_layers), flush=True)
# MLP alone with the norm's output
lay = layers[chat.n_chip]
n = lay.post_attention_layernorm(h1)
OUT["mlp_alone_diff"] = int((rows(lay.mlp(n)) != rows(lay.mlp(n.repeat(2, 1, 1)))).sum())
print("mlp", OUT["mlp_alone_diff"], flush=True)
# (b) head by position, on dims 0..tau inclusive
tau = chat.meta["tau_dim"]
if not hasattr(ctx, "head_v3"):
    ctx.head_v3 = chat.model.lm_head.weight[:nq, :tau + 1].contiguous()
    torch.mps.empty_cache()
def v3(hc, cache, pos):
    n = TL.qwen_body(ctx, ctx.v2_layers, hc, cache, pos)
    return F.linear(n[..., :tau + 1], ctx.head_v3)[0, -1]
ca, cb = TL.clone_cache(base), TL.clone_cache(base)
d_body, d_head = 0, 0
rr = []
tok = chat.tok
pr = TL.sample(2, need=lambda r: r["status"] == "no_call" and r["qwen_tokens"] > 500)
for r2 in pr:
    g2, q2 = TL.question(r2)
    m2 = D.parked_machine(g2, chat.T, q2.get("setup") or [])
    p = TL.prompt_of(chat, g2, q2, tool)
    o = chat._prefill(p)
    bb = o.past_key_values
    core.snapshot(chat.c, m2); cx.p.flags = 0; ec.start(p)
    ids = tok(r2["no_call_text"], add_special_tokens=False)["input_ids"][:200]
    ca, cb = TL.clone_cache(bb), TL.clone_cache(bb)
    t = {"graph": r2["graph"], "id": r2["id"], "steps": 0, "elems_differ": 0, "argmax_differ": 0, "wall_V0": 0.0, "wall_V3": 0.0, "owned": 0}
    pos = len(p)
    for k, nxt in enumerate(ids):
        keep = cx.step(ec.stream(nxt)).copy()
        hc = ec.hc(nxt, keep)
        if ec.code_token(keep) is not None:
            t["owned"] += 1
        order = (("V0", ca), ("V3", cb)) if k % 2 == 0 else (("V3", cb), ("V0", ca))
        res = {}
        for name, cc in order:
            s = time.perf_counter()
            y = TL.step(ctx, "V0", hc, cc, pos) if name == "V0" else v3(hc, cc, pos)
            am = int(torch.argmax(y))
            t["wall_" + name] += time.perf_counter() - s
            res[name] = (TL.bits(y), am)
        t["elems_differ"] += int((res["V0"][0] != res["V3"][0]).sum())
        t["argmax_differ"] += int(res["V0"][1] != res["V3"][1])
        t["steps"] += 1
        pos += 1
    t["wall_V0"] = round(t["wall_V0"] / t["steps"], 4); t["wall_V3"] = round(t["wall_V3"] / t["steps"], 4)
    rr.append(t)
    print(json.dumps(t), flush=True)
    del ca, cb, bb
OUT["long"] = rr
json.dump(OUT, open("results/s3_batchdiag.json", "w"), indent=1, default=str)
print(D.mem())
