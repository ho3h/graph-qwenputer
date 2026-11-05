"""The chip layers from the checkpoint's own tensors, on the CPU, in C (wexec.c). Interface as exec/cexec.py's CExec: start, step, run, burst, flags, clear.

Every number comes from the safetensors of the merged checkpoint, read here; core.build is used only for the snapshot (the machine's state, as hf.inject writes it for stock) and for the token-family tables used to decode the next token. This module does not read exec/'s compile_ir tables.

    ex = WExec(chat_or_lite.c, T, meta)
"""
import ctypes as ct
import hashlib
import json
import os
import subprocess
import time

import numpy as np
import torch
from safetensors import safe_open

from chipformer.q35.ir import Head
from chipformer.rv import core, hf
from chipformer.rv import spec as S

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "wexec.c")
CC = "/opt/homebrew/opt/llvm/bin/clang"
CFLAGS = ["-O3", "-mcpu=native", "-ffp-contract=off", "-fno-fast-math", "-fPIC", "-shared", "-Wall", "-Wextra", "-Wno-unused-parameter", "-Wno-unused-variable"] + os.environ.get("WEXEC_CFLAGS", "").split()
CKPT = "<drive>/Models/x210-rvc"
ST = {0: "text", 1: "owner_off", 2: "max", 3: "miss", 4: "decode"}
FLAGS = {1: "silu outside saturation", 2: "sigmoid outside saturation", 4: "decay not 1, 1/2 or 0", 8: "chip residue beyond the kept dims"}
HD, NK, NV, QKV = 128, 16, 32, 8192


def build_lib():
    SRC = os.environ.get("WEXEC_SRC") or globals()["SRC"]
    h = hashlib.sha256(open(SRC, "rb").read() + " ".join(CFLAGS).encode()).hexdigest()[:12]
    out = os.path.join(HERE, "build", f"libwexec-{h}.dylib")
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tmp = f"{out}.{os.getpid()}"
        subprocess.run([CC, *CFLAGS, SRC, "-o", tmp, "-lm"], check=True)
        os.replace(tmp, out)
    return out, h


I, F, U8, U16 = ct.POINTER(ct.c_int32), ct.POINTER(ct.c_float), ct.POINTER(ct.c_uint8), ct.POINTER(ct.c_uint16)


class WLayer(ct.Structure):
    _fields_ = [(n, t) for n, t in [("q_ptr", I), ("q_row", I), ("q_w", F), ("z_ptr", I), ("z_row", I), ("z_w", F), ("a_ptr", I), ("a_row", I), ("a_w", F), ("b_ptr", I), ("b_row", I), ("b_w", F),
                                    ("g_ptr", I), ("g_row", I), ("g_w", F), ("u_ptr", I), ("u_col", I), ("u_w", F), ("d_ptr", I), ("d_dim", I), ("d_w", F), ("o_ptr", I), ("o_dim", I), ("o_w", F),
                                    ("conv", F), ("n_lag", ct.c_int32), ("lag_row", I), ("hist", F), ("w_in", F), ("w_post", F), ("w_norm", F), ("A_exp", F), ("dt_bias", F), ("vh_active", I), ("S", F), ("vh_nrows", I),
                                    ("base_v", ct.c_float), ("base_nq", ct.c_int32), ("base_nz", ct.c_int32), ("base_ng", ct.c_int32), ("qb", F), ("zb", F), ("gb", F), ("ab", F), ("bb", F), ("qb_r", I), ("zb_r", I), ("gb_r", I)]]


class WProg(ct.Structure):
    _fields_ = [(n, ct.c_int32) for n in ("nL", "d0", "chip", "n_keep", "nfam", "npay", "vocab", "text_token", "n_printable", "hidden")] + \
               [("L", ct.POINTER(WLayer)), ("x", F), ("keep", I), ("f_start", I), ("f_len", I), ("f_dim", U16), ("f_val", F), ("f_qsum", F), ("fam_kind", I), ("fam_base", I), ("fam_size", I), ("printable", I),
                ("flags", ct.c_uint32), ("miss_token", ct.c_int32), ("steps", ct.c_int64), ("residue", ct.c_int64), ("not_saturated", ct.c_int64), ("heads_run", ct.c_int64), ("ballast", ct.c_int32)]


def _ip(a):
    return a.ctypes.data_as(I)


def _fp(a):
    return a.ctypes.data_as(F)


def by_col(M):
    """A float32 matrix (rows x cols) as (ptr, row, value), by column."""
    c, r = np.nonzero(M.T)
    v = M[r, c]
    ptr = np.zeros(M.shape[1] + 1, np.int32)
    ptr[1:] = np.cumsum(np.bincount(c, minlength=M.shape[1]))
    return ptr, r.astype(np.int32), v.astype(np.float32)


class Tensors:
    def __init__(self, ckpt=CKPT):
        self.idx = json.load(open(os.path.join(ckpt, "model.safetensors.index.json")))["weight_map"]
        self.ckpt = ckpt
        self.files = {}

    def f(self, name):
        fn = self.idx[name]
        if fn not in self.files:
            self.files[fn] = safe_open(os.path.join(self.ckpt, fn), framework="pt")
        return self.files[fn]

    def get(self, name):
        t = self.f(name).get_tensor(name)
        assert t.dtype == torch.bfloat16, (name, t.dtype)
        return t

    def np32(self, name):
        return self.get(name).float().numpy()


def build_tables(T, meta, n_layers, d0, hidden, mutate=None):
    """Per layer, every nonzero of the chip layer's tensors. Returns (layers, stats)."""
    chip = hidden - d0
    layers = []
    total = 0
    for L in range(n_layers):
        p = f"model.layers.{L}."
        la = p + "linear_attn."
        A = {}
        def load(name):
            m = T.np32(name)
            if mutate:
                m = mutate(name, m)
            return m
        qkv = load(la + "in_proj_qkv.weight")
        z = load(la + "in_proj_z.weight")
        a = load(la + "in_proj_a.weight")
        b = load(la + "in_proj_b.weight")
        o = load(la + "out_proj.weight")
        conv = load(la + "conv1d.weight")
        gate = load(p + "mlp.gate_proj.weight")
        up = load(p + "mlp.up_proj.weight")
        down = load(p + "mlp.down_proj.weight")
        for name, m in (("qkv", qkv), ("z", z), ("a", a), ("b", b), ("gate", gate), ("up", up)):
            assert not m[:, :d0].any(), (L, name, "reads Qwen's dims")
        assert not o[:d0].any() and not down[:d0].any(), (L, "writes Qwen's dims")
        for name, m in (("q", qkv), ("z", z), ("a", a), ("b", b), ("g", gate)):
            A[name + "_ptr"], A[name + "_row"], A[name + "_w"] = by_col(m[:, d0:])
        r, c = np.nonzero(up[:, d0:])
        A["u_ptr"] = np.zeros(up.shape[0] + 1, np.int32)
        A["u_ptr"][1:] = np.cumsum(np.bincount(r, minlength=up.shape[0]))
        A["u_col"], A["u_w"] = c.astype(np.int32), up[r, c + d0].astype(np.float32)
        A["d_ptr"], A["d_dim"], A["d_w"] = by_col(down[d0:])
        A["o_ptr"], A["o_dim"], A["o_w"] = by_col(o[d0:])
        A["conv"] = conv.reshape(QKV, 4).astype(np.float32).copy()
        A["lag_row"] = np.nonzero(A["conv"][:, :3].any(1))[0].astype(np.int32)
        if not len(A["lag_row"]):
            A["lag_row"] = np.zeros(1, np.int32)
            n_lag = 0
        else:
            n_lag = len(A["lag_row"])
        A["hist"] = np.zeros((QKV, 3), np.float32)
        A["w_in"] = (1.0 + T.np32(p + "input_layernorm.weight")[d0:]).astype(np.float32)
        A["w_post"] = (1.0 + T.np32(p + "post_attention_layernorm.weight")[d0:]).astype(np.float32)
        A["w_norm"] = T.np32(la + "norm.weight").astype(np.float32).copy()
        A["A_exp"] = T.get(la + "A_log").float().exp().numpy().astype(np.float32).copy()
        A["dt_bias"] = T.np32(la + "dt_bias").astype(np.float32).copy()
        active = np.zeros(NV, np.int32)
        for vh in range(NV):
            active[vh] = int(z[vh * HD:(vh + 1) * HD].any() or a[vh].any() or b[vh].any() or o[:, vh * HD:(vh + 1) * HD].any() or qkv[2 * NK * HD + vh * HD:2 * NK * HD + (vh + 1) * HD].any())
        A["vh_active"] = active
        A["S"] = np.zeros((NV, HD, HD), np.float32)
        A["vh_nrows"] = np.zeros(NV, np.int32)
        A["n_lag"] = n_lag
        total += sum(len(A[k]) for k in ("q_w", "z_w", "a_w", "b_w", "g_w", "u_w", "d_w", "o_w")) + int((A["conv"] != 0).sum())
        layers.append(A)
    return layers, {"nonzeros": total}


class WExec:
    FEAT_CAP = 40_000_000

    def __init__(self, c, T, meta, tables=None, mutate=None, share=None):
        """share: another WExec whose weights and token rows this one uses; this one gets its own state."""
        self.c, self.T, self.meta = c, T, meta
        if share is not None:
            tables = []
            for A in share.tables:
                B = dict(A)
                B["S"], B["hist"], B["vh_nrows"] = np.zeros_like(A["S"]), np.zeros_like(A["hist"]), np.zeros_like(A["vh_nrows"])
                tables.append(B)
        self.d0, self.hidden = meta["chip_dims_offset"], meta["hidden"]
        self.chip = self.hidden - self.d0
        self.v0 = meta["chip_token_offset"]
        self.nL = meta["chip_layers"]
        path, self.lib_hash = build_lib()
        self.lib = ct.CDLL(path)
        self.lib.w_step.argtypes = [ct.POINTER(WProg), ct.c_int32]
        self.lib.w_step.restype = ct.c_int
        self.lib.w_burst.argtypes = [ct.POINTER(WProg), ct.c_int32, ct.c_int64, ct.POINTER(ct.c_int32), ct.POINTER(ct.c_int64), I]
        self.lib.w_burst.restype = ct.c_int
        self.lib.w_run.argtypes = [ct.POINTER(WProg), I, ct.c_int64, F, U8]
        self.lib.w_run.restype = ct.c_int64
        self.lib.w_check_residue.argtypes = [ct.POINTER(WProg), U8]
        self.lib.w_check_residue.restype = ct.c_int64
        self.tensors = Tensors()
        t0 = time.time()
        if tables is None:
            tables, self.stats = build_tables(self.tensors, meta, self.nL, self.d0, self.hidden, mutate)
        self.build_s = time.time() - t0
        self.tables = tables
        self.CL = (WLayer * self.nL)()
        for i, A in enumerate(tables):
            W = self.CL[i]
            for k in ("q_ptr", "q_row", "z_ptr", "z_row", "a_ptr", "a_row", "b_ptr", "b_row", "g_ptr", "g_row", "u_ptr", "u_col", "d_ptr", "d_dim", "o_ptr", "o_dim", "lag_row", "vh_active", "vh_nrows"):
                setattr(W, k, _ip(A[k]))
            for k in ("q_w", "z_w", "a_w", "b_w", "g_w", "u_w", "d_w", "o_w", "conv", "hist", "w_in", "w_post", "w_norm", "A_exp", "dt_bias", "S"):
                setattr(W, k, _fp(A[k]))
            W.n_lag = A["n_lag"]
            M = self.memo = getattr(self, "memo", [])
            mm = {"qb": np.zeros(QKV, np.float32), "zb": np.zeros(NV * HD, np.float32), "gb": np.zeros(9216, np.float32), "ab": np.zeros(NV, np.float32), "bb": np.zeros(NV, np.float32), "qb_r": np.zeros(QKV, np.int32), "zb_r": np.zeros(NV * HD, np.int32), "gb_r": np.zeros(9216, np.int32)}
            M.append(mm)
            for k in ("qb", "zb", "gb", "ab", "bb"):
                setattr(W, k, _fp(mm[k]))
            for k in ("qb_r", "zb_r", "gb_r"):
                setattr(W, k, _ip(mm[k]))
            W.base_v = 0.0
        keep = [d - self.d0 for d in meta["code_dims"] + [meta["tau_dim"], meta["mu_dim"]]]
        self.keep = np.array(keep, np.int32)
        self.is_keep = np.zeros(self.chip, np.uint8)
        self.is_keep[self.keep] = 1
        self.n_keep = len(keep)
        self.x = np.zeros(self.chip, np.float32)
        self.n_text_ids = 1 << 19
        n_ix = S.VOCAB + self.n_text_ids
        self.f_start = np.full(n_ix, -1, np.int32)
        self.f_len = np.zeros(n_ix, np.int32)
        self.f_qsum = np.zeros(n_ix, np.float32)
        self.f_dim = np.empty(self.FEAT_CAP, np.uint16)
        self.f_val = np.empty(self.FEAT_CAP, np.float32)
        self.f_used = 0
        kind, base, size = np.zeros(1 << core.NFAM, np.int32), np.zeros(1 << core.NFAM, np.int32), np.zeros(1 << core.NFAM, np.int32)
        for fid, nm in enumerate(core.OUT_NAMES):
            if nm == "Q":
                kind[fid] = 3
            elif nm in S.CONTROLS:
                kind[fid], base[fid] = 1, S.tok(nm)
            elif nm in S.FAMILIES:
                kind[fid], base[fid], size[fid] = 2, S.tok(nm, 0), S.FAMILIES[nm][1]
        self.fam_kind, self.fam_base, self.fam_size = kind, base, size
        self.printable = np.array([-1 if q is None else q for q in T.printable], np.int32)
        p = self.p = WProg()
        p.nL, p.d0, p.chip, p.n_keep, p.nfam, p.npay, p.vocab, p.text_token, p.n_printable, p.hidden = self.nL, self.d0, self.chip, self.n_keep, core.NFAM, core.NPAY, S.VOCAB, S.TEXT_TOKEN, len(self.printable), self.hidden
        p.ballast = meta["ballast_dims"]
        p.L = ct.cast(self.CL, ct.POINTER(WLayer))
        p.x, p.keep = _fp(self.x), _ip(self.keep)
        p.f_start, p.f_len = _ip(self.f_start), _ip(self.f_len)
        p.f_dim = self.f_dim.ctypes.data_as(U16)
        p.f_val, p.f_qsum = _fp(self.f_val), _fp(self.f_qsum)
        p.fam_kind, p.fam_base, p.fam_size, p.printable = _ip(kind), _ip(base), _ip(size), _ip(self.printable)
        self.slots = {id(c.nodes[ni]): s for ni, s in hf.head_slots(c).items()}
        self.heads = [n for n in c.nodes if isinstance(n, Head)]
        self.r = c.target.value_heads // c.target.key_heads
        self.emb = self.tensors.f("model.embed_tokens.weight").get_slice("model.embed_tokens.weight")
        self.rec = None
        if share is not None:
            self.f_start, self.f_len, self.f_qsum, self.f_dim, self.f_val = share.f_start, share.f_len, share.f_qsum, share.f_dim, share.f_val
            p.f_start, p.f_len, p.f_dim, p.f_val, p.f_qsum = share.p.f_start, share.p.f_len, share.p.f_dim, share.p.f_val, share.p.f_qsum
            self.fill = share.fill

    def _ix(self, t):
        return t if t < S.VOCAB else S.VOCAB + (t - S.TEXT_TOKEN)

    def _mid(self, t):
        return self.v0 + t if t < S.VOCAB else t - S.TEXT_TOKEN

    def fill(self, t):
        """The token's row, read from the checkpoint's embedding."""
        ix = self._ix(t)
        if self.f_start[ix] >= 0:
            return
        mid = self._mid(t)
        row = self.emb[mid:mid + 1, :][0].float().numpy()
        low = row[: self.d0]
        s = np.float32(0.0)
        for v in low[low != 0]:
            s = np.float32(s + np.float32(v) * np.float32(v))
        ch = row[self.d0:]
        nz = np.nonzero(ch)[0]
        a = self.f_used
        assert a + len(nz) <= self.FEAT_CAP
        self.f_dim[a:a + len(nz)] = nz
        self.f_val[a:a + len(nz)] = ch[nz]
        self.f_used = a + len(nz)
        self.f_len[ix] = len(nz)
        self.f_qsum[ix] = s
        self.f_start[ix] = a

    def clear(self):
        for A in self.tables:
            A["S"][:] = 0
            A["hist"][:] = 0
            A["vh_nrows"][:] = 0

    def load_init(self):
        """hf.inject's rule: every value head zero, then the snapshot; lag windows stay."""
        for A in self.tables:
            A["S"][:] = 0
            A["vh_nrows"][:] = 0
        for n in self.heads:
            L, j = self.slots[id(n)]
            A = self.tables[L]
            init = n.init or []
            for x in range(len(n.vheads())):
                vh = j * self.r + x
                for row, vec in (init[x] if x < len(init) else {}).items():
                    A["S"][vh, row] = np.asarray(vec, np.float32)
                    if row + 1 > A["vh_nrows"][vh]:
                        A["vh_nrows"][vh] = row + 1

    def start(self, prompt_stream):
        self.clear()
        self.run(prompt_stream, keep=False)
        self.load_init()

    def step(self, t):
        if self.lib.w_step(ct.byref(self.p), t):
            self.fill(t)
            assert self.lib.w_step(ct.byref(self.p), t) == 0
        return self.x[self.keep]

    def run(self, toks, keep=True):
        arr = np.asarray(toks, np.int32)
        for t in np.unique(arr):
            self.fill(int(t))
        out = np.empty((len(arr), self.n_keep), np.float32) if keep else None
        n = self.lib.w_run(ct.byref(self.p), _ip(arr), len(arr), _fp(out) if keep else None, self.is_keep.ctypes.data_as(U8) if keep else None)
        assert n == len(arr)
        return out

    def burst(self, t, max_steps, record=False):
        o, n = ct.c_int32(), ct.c_int64()
        total = 0
        buf = None
        if record:
            if self.rec is None or len(self.rec) < max_steps:
                self.rec = np.empty(max_steps, np.int32)
            buf = self.rec
        while True:
            ptr = _ip(buf[total:]) if record else None
            st = self.lib.w_burst(ct.byref(self.p), t, max_steps - total, ct.byref(o), ct.byref(n), ptr)
            total += n.value
            if st != 3:
                return ST[st], o.value, total, (buf[:total] if record else None)
            self.fill(o.value)
            t = o.value

    def flags(self):
        f = self.p.flags
        return [v for k, v in FLAGS.items() if f & k]
