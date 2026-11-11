"""speed/'s copies of the text path. Nothing under other folders is edited; rvc/, exec/ and the vendored code are imported read-only.

Paths:
    V0  chain3's: dense Qwen layers, full head, two argmaxes (rvc/chain2.py, exec/chat.py)
    V1  head cut to Qwen's rows
    V2  Qwen's linear maps as their nonzero blocks; head as Qwen's rows on dims 0-2559 + tau
"""
import copy
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(X210, "rvc"))
import box as X  # noqa: E402

FW = os.path.join(X210, "fw", "build", "fw.elf")
X.ELF = FW
X.build_elf = lambda: FW
sys.path.append(os.path.join(X210, "exec"))
import chain2 as C2  # noqa: E402
import decode as D  # noqa: E402
import reflib  # noqa: E402
import score as SC  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core  # noqa: E402
from chipformer.q35 import fast as QF  # noqa: E402

CHAIN3 = os.path.join(X210, "rvc", "results", "chain3", "all.jsonl")
GIB = 2 ** 30


class Ctx:
    pass


def load(compact_chip=True):
    from transformers import AutoTokenizer
    from chipformer.rv.chat import RvChat
    from cexec import CExec
    cx = Ctx()
    t = {}
    t0 = time.time()
    chat = RvChat.__new__(RvChat)
    from transformers import Qwen3_5ForCausalLM
    from pathlib import Path
    from chipformer.q35.ir import Target
    t["imports"] = time.time() - t0; t0 = time.time()
    chat.path = Path(D.CKPT)
    chat.meta = json.loads((chat.path / "chipformer.json").read_text())
    chat.dev = "mps"
    chat.model = Qwen3_5ForCausalLM.from_pretrained(chat.path, dtype=torch.bfloat16)
    t["from_pretrained"] = time.time() - t0; t0 = time.time()
    chat.n_chip, chat.v0 = chat.meta["chip_layers"], chat.meta["chip_token_offset"]
    if compact_chip:
        t["compact"] = QF.compact(chat.model, qwen=False, n_chip=chat.n_chip)
        t["compact_s"] = time.time() - t0; t0 = time.time()
    chat.model = chat.model.to("mps").eval()
    t["to_mps"] = time.time() - t0; t0 = time.time()
    chat.lm = chat.model.model
    chat.tok = AutoTokenizer.from_pretrained(chat.path)
    t["tokenizer"] = time.time() - t0; t0 = time.time()
    chat.T = BR.Text(chat.path / "tokenizer.json")
    t["bridge_text"] = time.time() - t0; t0 = time.time()
    cfg = chat.model.config
    chat.store_cfg = None
    chat.c = core.build(Target(cfg.linear_num_key_heads, cfg.linear_num_value_heads, cfg.intermediate_size), chat.T, None)
    t["core_build"] = time.time() - t0; t0 = time.time()
    chat.code_dims = torch.tensor(chat.meta["code_dims"], device=chat.dev)
    chat.id_dims = None
    chat.store_snap = None
    chat.eos = {248046, 248044}
    chat.fast = False
    chat.executor = False
    chat.verify = False
    cx.chat = chat
    from chat import ExecChat
    ec = ExecChat.__new__(ExecChat)
    ec.chat = chat
    ec.cx = CExec(chat.c, chat.T)
    t["cexec"] = time.time() - t0; t0 = time.time()
    ec.d0 = chat.meta["chip_dims_offset"]
    cols = chat.meta["code_dims"] + [chat.meta["tau_dim"], chat.meta["mu_dim"]]
    ec.keep_cols_np = np.array(cols)
    ec.keep_cols = torch.tensor(cols, device="mps")
    ec.hidden = chat.lm.embed_tokens.weight.shape[1]
    ec.n_code = len(chat.meta["code_dims"])
    ec.dev = "mps"
    ec.rows = {}
    cx.ec = ec
    cx.nq = len(AutoTokenizer.from_pretrained(X.MODEL))
    t["base_tokenizer"] = time.time() - t0
    cx.load_phases = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in t.items()}
    return cx


def sample(n=12, offset=0, need=None):
    """Executor questions of chain3's draw, in order."""
    out = []
    for line in open(CHAIN3):
        r = json.loads(line)
        if r["verified_positions"]:
            continue
        if need and not need(r):
            continue
        out.append(r)
    return out[offset:offset + n]


def question(r):
    gp, qp = D.graph_path(r["graph"])
    g = json.load(open(gp))
    q = {x["id"]: x for x in json.load(open(qp))["questions"]}[r["id"]]
    return g, q


def prompt_of(chat, g, q, tool):
    msgs = [{"role": "system", "content": X.HT.system_prompt(g) + C2.EXTRA + C2.TOLD}, {"role": "user", "content": q["text"]}]
    return chat.prompt_ids(msgs, tools=[tool])


def clone_cache(cache):
    c2 = copy.copy(cache)
    c2.layers = []
    for lay in cache.layers:
        l2 = copy.copy(lay)
        if hasattr(lay, "recurrent_states"):
            l2.conv_states = {k: (v.clone() if v is not None else None) for k, v in lay.conv_states.items()}
            l2.recurrent_states = {k: (v.clone() if v is not None else None) for k, v in lay.recurrent_states.items()}
            l2.has_previous_state = dict(lay.has_previous_state)
        elif getattr(lay, "keys", None) is not None:
            l2.keys = lay.keys.clone()
            l2.values = lay.values.clone()
        c2.layers.append(l2)
    return c2


def repeat_cache(cache, B):
    """A batch of B copies of a one-row cache, Qwen's layers only."""
    c2 = copy.copy(cache)
    c2.layers = []
    for lay in cache.layers:
        l2 = copy.copy(lay)
        if hasattr(lay, "recurrent_states"):
            l2.conv_states = {k: (v.repeat(B, *([1] * (v.dim() - 1))) if v is not None else None) for k, v in lay.conv_states.items()}
            l2.recurrent_states = {k: (v.repeat(B, *([1] * (v.dim() - 1))) if v is not None else None) for k, v in lay.recurrent_states.items()}
            l2.has_previous_state = dict(lay.has_previous_state)
        elif getattr(lay, "keys", None) is not None:
            l2.keys = lay.keys.repeat(B, 1, 1, 1)
            l2.values = lay.values.repeat(B, 1, 1, 1)
        c2.layers.append(l2)
    return c2


def state_bits(cache, first):
    """A digest of every Qwen state, for equality."""
    import hashlib
    h = hashlib.blake2b(digest_size=12)
    per = []
    for i, lay in enumerate(cache.layers):
        if i < first:
            continue
        hh = hashlib.blake2b(digest_size=8)
        if hasattr(lay, "recurrent_states"):
            for t in (lay.conv_states[0], lay.recurrent_states[0]):
                hh.update(t.detach().cpu().numpy().tobytes() if t.dtype != torch.bfloat16 else t.detach().cpu().view(torch.uint16).numpy().tobytes())
        else:
            for t in (lay.keys, lay.values):
                hh.update(t.detach().cpu().numpy().tobytes() if t.dtype != torch.bfloat16 else t.detach().cpu().view(torch.uint16).numpy().tobytes())
        per.append(hh.hexdigest())
    return per


def bits(t):
    return t.detach().cpu().view(torch.uint16).numpy().copy()


class Head:
    def __init__(self, ctx, kind):
        chat = ctx.ec.chat
        self.kind = kind
        self.nq = ctx.nq
        W = chat.model.lm_head.weight
        self.norm = chat.lm.norm
        if kind == "full":
            self.W = W
            self.cols = None
        elif kind == "rows":
            self.W = W[:ctx.nq]
            self.cols = None
        else:                                              # Qwen's rows on Qwen's dims + tau
            tau = chat.meta["tau_dim"]
            d0 = chat.meta["chip_dims_offset"]
            cols = torch.tensor(list(range(d0)) + [tau], device="mps")
            self.W = W[:ctx.nq].index_select(1, cols).contiguous()
            self.cols = cols


def clone_compact(layer):
    """The layer with every linear map as its nonzero block (vendored SparseLinear), weights copied; the other modules shared."""
    L = copy.copy(layer)
    L._modules = dict(layer._modules)
    for name in ("linear_attn", "self_attn", "mlp"):
        if name in L._modules and L._modules[name] is not None:
            m = copy.copy(L._modules[name])
            m._modules = dict(m._modules)
            for cname, child in list(m._modules.items()):
                if isinstance(child, torch.nn.Linear):
                    m._modules[cname] = QF.SparseLinear(child.weight)
            L._modules[name] = m
    return L


@torch.no_grad()
def build_v2(ctx):
    chat = ctx.ec.chat
    if not hasattr(ctx, "v2_layers"):
        ctx.v2_layers = [clone_compact(chat.lm.layers[i]) for i in range(chat.n_chip, len(chat.lm.layers))]
        ctx.head_v1 = Head(ctx, "rows")
        ctx.head_v2 = Head(ctx, "block")
        ctx.head_v0 = Head(ctx, "full")
    return ctx.v2_layers


@torch.no_grad()
def qwen_body(ctx, layers, hc, cache, pos):
    chat = ctx.ec.chat
    h = hc.view(1, 1, -1) if hc.dim() == 1 else hc
    p4 = torch.full((4, h.shape[0], 1), pos, device="mps", dtype=torch.long)
    pe = chat.lm.rotary_emb(h, p4[1:])
    for lay in layers:
        h = lay(h, position_embeddings=pe, attention_mask=None, position_ids=p4[0], past_key_values=cache)
    return chat.lm.norm(h)


@torch.no_grad()
def step(ctx, variant, hc, cache, pos):
    """Logits over Qwen's rows, one row, for variant V0, V1 or V2. Not synced."""
    chat = ctx.ec.chat
    if variant == "V0":
        n = qwen_body(ctx, chat.lm.layers[chat.n_chip:], hc, cache, pos)
        return chat.model.lm_head(n)[0, -1][:ctx.nq]
    if variant == "V1":
        n = qwen_body(ctx, chat.lm.layers[chat.n_chip:], hc, cache, pos)
        return F.linear(n, ctx.head_v1.W)[0, -1]
    n = qwen_body(ctx, ctx.v2_layers, hc, cache, pos)
    return F.linear(n.index_select(-1, ctx.head_v2.cols), ctx.head_v2.W)[0, -1]
