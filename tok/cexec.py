"""The C engine from Python: build the library, hold the buffers, and offer what RvChat's executor row offers (start, step, plus free-running bursts).

    ex = CExec(c, T)        # c: core.build(..., T); T: bridge.Text
    core.snapshot(c, m)     # the machine's state in the graph's tables, as at a stock prefill
    ex.start(stream_prompt) # the prompt from zero states (the lag windows), then the snapshot
    keep = ex.step(token)   # the kept dims (code, tau, mu) in fp32, a view
    status, nxt, n = ex.burst(token, max_steps)
"""
import ctypes as ct
import hashlib
import os
import subprocess
import time

import numpy as np

from chipformer.q35 import ir as ir_mod
from chipformer.q35.ir import HD, Head
from chipformer.rv import core
from chipformer.rv import spec as S

import compile_ir as CI

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("CHIP_SRC") or os.path.join(HERE, "engine.c")
CC = os.environ.get("CHIP_CC") or "/opt/homebrew/opt/llvm/bin/clang"
CFLAGS = ["-O3", "-mcpu=native", "-ffp-contract=off", "-fno-fast-math", "-fPIC", "-shared", "-Wall", "-Wextra", "-Wno-unused-parameter"] + os.environ.get("CHIP_CFLAGS", "").split()
ST = {0: "text", 1: "owner_off", 2: "max", 3: "miss", 4: "decode"}
FLAGS = {1: "gate outside silu range", 2: "read not equal-valued k-hot, k<=2", 4: "key not one-hot", 8: "z outside silu range", 16: "channel outside silu range", 32: "decay selector not 0/110/238"}


def build_lib():
    h = hashlib.sha256(open(SRC, "rb").read() + " ".join(CFLAGS).encode()).hexdigest()[:12]
    out = os.path.join(HERE, "build", f"libchip-{h}.dylib")
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tmp = f"{out}.{os.getpid()}"
        subprocess.run([CC, *CFLAGS, SRC, "-o", tmp, "-lm"], check=True)
        os.replace(tmp, out)
    return out, h


class CProg(ct.Structure):
    I, F, U = ct.POINTER(ct.c_int32), ct.POINTER(ct.c_float), ct.POINTER(ct.c_uint16)
    _fields_ = [(n, ct.c_int32) for n in ("D", "n_mem", "V", "n_levels", "n_keep", "one", "nfam", "npay", "vocab", "text_token", "n_printable", "pad")] + \
               [("mem", F), ("y", F), ("S", F), ("val", F), ("aup", F)] + \
               [("levels", I), ("buckets", I), ("eptr", I), ("tix", U), ("tw", F), ("ec", F)] + \
               [("aexpr", I), ("gstart", I), ("ua", I), ("ucoef", F), ("uout", I), ("outs", I)] + \
               [("zexpr", I), ("lag_slot", I), ("lag_dim", I), ("fan_ptr", I), ("fan_h", I), ("fan_row", I)] + \
               [("h_v", I), ("h_always", I), ("vh_a", I), ("vh_beta", I), ("vh_S", I), ("vh_v", I), ("vh_z", I), ("v_col", I), ("v_expr", I), ("z_expr", I), ("z_o", I), ("o_col", I), ("o_dim", I), ("o_w", F)] + \
               [("keep", I), ("p_t", I), ("p_a", I), ("p_b", I), ("p_r", F), ("vh_nrows", I)] + \
               [("f_start", I), ("f_len", I), ("f_dim", U), ("f_val", F)] + \
               [("fam_kind", I), ("fam_base", I), ("fam_size", I), ("printable", I)] + \
               [("flags", ct.c_uint32), ("miss_token", ct.c_int32), ("steps", ct.c_int64), ("units_on", ct.c_int64), ("reads", ct.c_int64), ("writes", ct.c_int64)]


def _ip(a):
    return a.ctypes.data_as(CProg.I)


def _fp(a):
    return a.ctypes.data_as(CProg.F)


class CExec:
    FEAT_CAP = 40_000_000

    def __init__(self, c, T, corrupt=None):
        self.c, self.T = c, T
        t0 = time.time()
        P = CI.cached(c, [core.__file__, ir_mod.__file__, S.__file__])
        self.compile_s = time.time() - t0
        A = self.A = {k: np.array(v) for k, v in P["arrays"].items()}      # writable copies
        self.cse_stats = P["stats"]
        if corrupt:
            corrupt(A)
        self.D, self.V = P["D"], P["V"]
        path, self.lib_hash = build_lib()
        self.lib = ct.CDLL(path)
        self.lib.chip_step.argtypes = [ct.POINTER(CProg), ct.c_int32]
        self.lib.chip_step.restype = ct.c_int
        self.lib.chip_burst.argtypes = [ct.POINTER(CProg), ct.c_int32, ct.c_int64, ct.POINTER(ct.c_int32), ct.POINTER(ct.c_int64), CProg.I]
        self.lib.chip_burst.restype = ct.c_int
        self.lib.chip_run.argtypes = [ct.POINTER(CProg), CProg.I, ct.c_int64, CProg.F]
        self.lib.chip_run.restype = ct.c_int64
        self.mem = np.zeros(P["n_mem"], np.float32)
        self.y = np.zeros(self.D, np.float32)
        self.S = np.zeros((self.V, HD, HD), np.float32)
        self.val = np.zeros(len(A["ec"]) + 4, np.float32)
        self.aup = np.zeros(max(1, len(A["aexpr"])), np.float32)
        self.n_text_ids = 1 << 19
        n_ix = S.VOCAB + self.n_text_ids
        self.f_start = np.full(n_ix, -1, np.int32)
        self.f_len = np.zeros(n_ix, np.int32)
        self.f_dim = np.empty(self.FEAT_CAP, np.uint16)        # untouched pages stay virtual
        self.f_val = np.empty(self.FEAT_CAP, np.float32)
        self.f_used = 0
        self.feat_ids = np.array(sorted(c.token_fns), np.int64)
        kind, base, size = np.zeros(1 << core.NFAM, np.int32), np.zeros(1 << core.NFAM, np.int32), np.zeros(1 << core.NFAM, np.int32)
        for fid, nm in enumerate(core.OUT_NAMES):
            if nm == "Q":
                kind[fid] = 3
            elif nm in ("T0", "T1", "T2", "T3"):               # tok/: a token by its id: base holds bits 17..16, size bounds the payload
                k = int(nm[1])
                kind[fid], base[fid], size[fid] = 4, k, min(65536, max(0, 248070 - (k << 16)))
            elif nm in S.CONTROLS:
                kind[fid], base[fid] = 1, S.tok(nm)
            elif nm in S.FAMILIES:
                kind[fid], base[fid], size[fid] = 2, S.tok(nm, 0), S.FAMILIES[nm][1]
        self.fam_kind, self.fam_base, self.fam_size = kind, base, size
        self.printable = np.array([-1 if q is None else q for q in T.printable], np.int32)
        p = self.p = CProg()
        p.D, p.n_mem, p.V, p.n_levels, p.n_keep, p.one = self.D, P["n_mem"], self.V, len(A["levels"]), len(A["keep"]), P["one"]
        p.nfam, p.npay, p.vocab, p.text_token, p.n_printable = core.NFAM, core.NPAY, S.VOCAB, S.TEXT_TOKEN, len(self.printable)
        p.mem, p.y, p.S, p.val, p.aup = _fp(self.mem), _fp(self.y), _fp(self.S), _fp(self.val), _fp(self.aup)
        for k in ("levels", "buckets", "eptr", "aexpr", "gstart", "ua", "uout", "outs", "zexpr", "lag_slot", "lag_dim", "fan_ptr", "fan_h", "fan_row", "h_v", "h_always",
                  "vh_a", "vh_beta", "vh_S", "vh_v", "vh_z", "v_col", "v_expr", "z_expr", "z_o", "o_col", "o_dim", "keep", "p_t", "p_a", "p_b", "vh_nrows"):
            setattr(p, k, _ip(A[k]))
        p.tix = A["tix"].ctypes.data_as(CProg.U)
        for k in ("tw", "ec", "ucoef", "o_w", "p_r"):
            setattr(p, k, _fp(A[k]))
        p.f_start, p.f_len = _ip(self.f_start), _ip(self.f_len)
        p.f_dim = self.f_dim.ctypes.data_as(CProg.U)
        p.f_val = _fp(self.f_val)
        p.fam_kind, p.fam_base, p.fam_size, p.printable = _ip(kind), _ip(base), _ip(size), _ip(self.printable)
        self.heads = [n for n in c.nodes if isinstance(n, Head)]
        self.heads.sort(key=lambda n: n.level)           # stable: the level's node order, as compile_ir
        self.rec = None
        nmax = max(int(np.sum(np.diff(A["gstart"])[lv[3]:lv[3] + lv[5]])) if lv[0] == 0 else int(np.sum(A["z_o"][1:] - A["z_o"][:-1])) for lv in A["levels"])
        assert nmax <= 16384, nmax                       # engine.c MAX_TOUCH
        self.n_keep = len(A["keep"])

    # --- token features ------------------------------------------------------------------
    def _ix(self, t):
        return t if t < S.VOCAB else S.VOCAB + (t - S.TEXT_TOKEN)

    def fill(self, t):
        """Compute and store token t's features (549 Python calls; each token once)."""
        ix = self._ix(t)
        if self.f_start[ix] >= 0:
            return
        fv = self.c.feature_value
        nz = [(d, float(fv(int(d), t))) for d in self.feat_ids]
        nz = [(d, v) for d, v in nz if v]
        n = len(nz)
        assert self.f_used + n <= self.FEAT_CAP
        a = self.f_used
        for j, (d, v) in enumerate(nz):
            assert float(np.float32(v)) == v
            self.f_dim[a + j] = d
            self.f_val[a + j] = v
        self.f_used += n
        self.f_len[ix] = n
        self.f_start[ix] = a

    # --- states --------------------------------------------------------------------------
    def clear(self):
        self.S[:] = 0
        self.mem[:] = 0

    def load_init(self):
        """Every value head's state from the graph's init (hf.inject's rule: zero, then the snapshot); the lag windows stay."""
        self.S[:] = 0
        j = 0
        for n in self.heads:
            init = n.init or []
            for x in range(len(n.vheads())):
                for r, vec in (init[x] if x < len(init) else {}).items():
                    self.S[j, r] = np.asarray(vec, np.float32)
                    if r + 1 > self.A["vh_nrows"][j]:
                        self.A["vh_nrows"][j] = r + 1
                j += 1
        assert j == self.V

    def start(self, prompt_stream):
        """As the HF path: the prompt through the circuit from zero states, then the snapshot; lag windows kept."""
        self.clear()
        self.run(prompt_stream, keep=False)
        self.load_init()

    def save(self):
        return self.S.copy(), self.mem.copy()

    def restore(self, st):
        self.S[:], self.mem[:] = st

    # --- running -------------------------------------------------------------------------
    def step(self, t):
        if self.lib.chip_step(ct.byref(self.p), t):
            self.fill(t)
            r = self.lib.chip_step(ct.byref(self.p), t)
            assert r == 0
        return self.mem[self.A["keep"]]

    def run(self, toks, keep=True):
        """A teacher-forced stretch; returns [n, n_keep] fp32 or None."""
        arr = np.asarray(toks, np.int32)
        for t in np.unique(arr):
            self.fill(int(t))
        out = np.empty((len(arr), self.n_keep), np.float32) if keep else None
        n = self.lib.chip_run(ct.byref(self.p), _ip(arr), len(arr), _fp(out) if keep else None)
        assert n == len(arr)
        return out

    def burst(self, t, max_steps, record=False):
        """Run from token t until text / owner off / bad code / max_steps. Returns (status name, token to feed next or -1/-2, steps, tokens or None): tokens[i] is the next token after step i."""
        o, n = ct.c_int32(), ct.c_int64()
        total = 0
        buf = None
        if record:
            if self.rec is None or len(self.rec) < max_steps:
                self.rec = np.empty(max_steps, np.int32)
            buf = self.rec
        while True:
            ptr = _ip(buf[total:]) if record else None
            st = self.lib.chip_burst(ct.byref(self.p), t, max_steps - total, ct.byref(o), ct.byref(n), ptr)
            total += n.value
            if st != 3:
                return ST[st], o.value, total, (buf[:total] if record else None)
            self.fill(o.value)
            t = o.value

    def x(self):
        return self.mem[: self.D]

    def flags(self):
        f = self.p.flags
        return [v for k, v in FLAGS.items() if f & k]
