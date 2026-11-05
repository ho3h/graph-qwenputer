import torch; torch.set_grad_enabled(False)
import json, time
import numpy as np, torch.nn.functional as F
import batchrun as BR2
from chipformer.rv import core
from transformers.models.qwen3_5 import modeling_qwen3_5 as M
from transformers.modeling_utils import ALL_ATTENTION_FUNCTIONS
C2, D, X = TL.C2, TL.D, TL.X
ec, chat, cx = ctx.ec, ctx.ec.chat, ctx.ec.cx
tool = C2.chase_tool("")
tau = chat.meta["tau_dim"]; nq = ctx.nq
saved = {}
for line in open(TL.CHAIN3):
    x = json.loads(line)
    if not x["verified_positions"]:
        saved[(x["graph"], x["id"])] = x
k = ("cities/c020", 230); k2 = ("random/r021", 22)
def setup(k, ex):
    g, q = TL.question(saved[k])
    prompt = TL.prompt_of(chat, g, q, tool)
    hc = BR2.prompt_hc(ctx, ctx.exp, prompt)
    nn, cache = BR2.qwen_prefill_hc(ctx, hc)
    m = D.parked_machine(g, chat.T, q.get("setup") or [])
    core.snapshot(chat.c, m); ex.p.flags = 0; ex.start([ec.stream(i) for i in prompt])
    return prompt, cache
p1, c1 = setup(k, ctx.exs[0]); p2, c2 = setup(k2, ctx.exs[1])
A = BR2.Slots(ctx, 1, tau, ctx.v2_layers, ctx.head_v3); A.install(0, c1)
Bb = BR2.Slots(ctx, 2, tau, ctx.v2_layers, ctx.head_v3); Bb.install(0, c1); Bb.install(1, c2)
t1, t2 = chat.T.TCO, chat.T.TCO
b1 = BR2.hc_bits(ec, t1, ctx.exs[0].step(ec.stream(t1)).copy()); b2 = BR2.hc_bits(ec, t2, ctx.exs[1].step(ec.stream(t2)).copy())
pos1, pos2 = len(p1), len(p2)
h1 = torch.from_numpy(b1).to("mps").view(torch.bfloat16).view(1, 1, -1)
hb = torch.from_numpy(np.stack([b1, b2])).to("mps").view(torch.bfloat16).unsqueeze(1)
pa = chat.lm.rotary_emb(h1, torch.full((3, 1, 1), pos1, device="mps", dtype=torch.long))
pb = chat.lm.rotary_emb(hb, torch.tensor([[pos1], [pos2]], device="mps").unsqueeze(0).expand(3, -1, -1))
def rows(t):
    t0 = t[0].detach().cpu()
    return t0.view(torch.uint16).numpy().copy() if t.dtype == torch.bfloat16 else t0.numpy().copy()
def eq(n, a, b, res):
    res[n] = int((rows(a) != rows(b)).sum())
res = {}
for lay, i in zip(ctx.v2_layers, range(chat.n_chip, len(chat.lm.layers))):
    if i == 22:
        break
    if chat.model.config.layer_types[i] == "linear_attention":
        h1 = A._linear(lay, i, h1, None); hb = Bb._linear(lay, i, hb, None)
    else:
        h1 = A._full(lay, i, h1, pa, [0]); hb = Bb._full(lay, i, hb, pb, [0, 1])
print("at layer 22 input differ", int((rows(h1) != rows(hb)).sum()), flush=True)
layer = ctx.v2_layers[22 - chat.n_chip]
a = layer.self_attn
attn = ALL_ATTENTION_FUNCTIONS.get_interface(a.config._attn_implementation, M.eager_attention_forward)
def parts(x, B, pe, rowsl, kvs):
    n = layer.input_layernorm(x)
    shape = (B, 1); hshape = (*shape, -1, a.head_dim)
    pq = a.q_proj(n)
    qs, gate = torch.chunk(pq.view(*shape, -1, a.head_dim * 2), 2, dim=-1)
    gate = gate.reshape(*shape, -1)
    qsn = a.q_norm(qs.view(hshape)).transpose(1, 2)
    pk = a.k_proj(n); pv = a.v_proj(n)
    ks = a.k_norm(pk.view(hshape)).transpose(1, 2)
    vs = pv.view(hshape).transpose(1, 2)
    qr, kr = M.apply_rotary_pos_emb(qsn, ks, pe[0], pe[1])
    outs = []
    for j in rowsl:
        keys = torch.cat([kvs[j][0], kr[j:j + 1]], dim=-2); vals = torch.cat([kvs[j][1], vs[j:j + 1]], dim=-2)
        oj, _ = attn(a, qr[j:j + 1], keys, vals, None, dropout=0.0, scaling=a.scaling)
        outs.append(oj.reshape(1, 1, -1).contiguous())
    o = torch.cat(outs) if B > 1 else outs[0]
    og = o * torch.sigmoid(gate)
    oo = a.o_proj(og)
    x2 = x + oo
    n2 = layer.post_attention_layernorm(x2)
    gt = layer.mlp.gate_proj(n2); up = layer.mlp.up_proj(n2)
    act = layer.mlp.act_fn(gt); pr = act * up
    dn = layer.mlp.down_proj(pr)
    return dict(n=n, pq=pq, gate=gate, qn=qsn, pk=pk, pv=pv, kn=ks, qr=qr, kr=kr, attn=o, gated=og, o_proj=oo, x2=x2, n2=n2, gt=gt, up=up, act=act, prod=pr, down=dn, out=x2 + dn)
P1 = parts(h1, 1, pa, [0], A.kv[22]); P2 = parts(hb, 2, pb, [0, 1], Bb.kv[22])
for nm in P1:
    eq(nm, P1[nm], P2[nm], res)
print(json.dumps(res), flush=True)
# Which row counts change the map on these inputs, for the tensor that differs first
for nm, fn, inp in (("down_block", layer.mlp.down_proj, P1["prod"]), ("gate_block", layer.mlp.gate_proj, P1["n2"]), ("up_block", layer.mlp.up_proj, P1["n2"]), ("o_block", a.o_proj, P1["gated"])):
    y1 = fn(inp)
    d = {}
    for B in (2, 3, 4, 8, 16):
        d[B] = int((rows(y1) != rows(fn(inp.repeat(B, 1, 1)))).sum())
    print(nm, d, flush=True)
    # the dense weight's map
print(D.mem())
