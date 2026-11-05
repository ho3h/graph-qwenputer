"""RvChat-style decoding with the chip layers on the C engine and Qwen's layers on MPS.

ExecChat wraps the vendored RvChat (stock modules, loaded as ever). A chip token runs on the engine alone. A text token runs on the engine, and its residual, the embedding row below chip_dims_offset plus the kept dims and zeros, goes to Qwen's stock layers through RvChat._qwen_step.

The prompt's prefill still runs the whole stock model (chip layers included): only decode positions move to the engine. So every result from this path is "executor", not stock.
"""
import hashlib
import json
import os
import sys

import numpy as np
import torch

from chipformer.rv import bridge as BR
from chipformer.rv import spec as S

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import overlay as O  # noqa: E402
from cexec import CExec  # noqa: E402


class ExecChat:
    def __init__(self, path, device="mps"):
        from chipformer.rv.chat import RvChat
        self.chat = RvChat(path, device=device, fast=False, executor=False)
        c = self.chat
        O.set_text(c.T)
        self.cx = CExec(c.c, c.T)
        self.d0 = c.meta["chip_dims_offset"]
        cols = c.meta["code_dims"] + [c.meta["tau_dim"], c.meta["mu_dim"]]
        assert len(cols) == len(c.c.keep)
        self.keep_cols_np = np.array(cols)
        self.keep_cols = torch.tensor(cols, device=device)
        self.hidden = c.lm.embed_tokens.weight.shape[1]
        self.n_code = len(c.meta["code_dims"])
        self.dev = device
        self.rows = {}

    def stream(self, mid):
        return self.chat.v0 and (mid - self.chat.v0 if mid >= self.chat.v0 else BR.text_token(mid))

    def to_model(self, t):
        return self.chat.v0 + t if t < S.VOCAB else t - S.TEXT_TOKEN

    def start(self, prompt_ids):
        self.cx.start([self.stream(i) for i in prompt_ids])

    def hc(self, mid, keep):
        """A text token's residual after the chip layers: as _exec_hc upstream."""
        h = torch.zeros(self.hidden, dtype=torch.bfloat16, device=self.dev)
        h[: self.d0] = self.chat.lm.embed_tokens.weight[mid, : self.d0]
        h[self.keep_cols] = torch.from_numpy(keep.copy()).to(self.dev).to(torch.bfloat16)
        return h

    def code_token(self, keep):
        return self.chat.code_token(torch.from_numpy(keep[: self.n_code].copy()))

    def low_bits(self, mid):
        """The embedding row's bit patterns below chip_dims_offset."""
        if mid not in self.rows:
            self.rows[mid] = self.chat.lm.embed_tokens.weight[mid, : self.d0].detach().cpu().view(torch.uint16).numpy().copy()
        return self.rows[mid]

    def exec_bits(self, mid, keep):
        """The executor's residual as stock would hold it: 3,968 bf16 bit patterns. Also says whether every kept fp32 value was exactly a bf16 value."""
        u = keep.view(np.uint32)
        r = (u + 0x7FFF + ((u >> 16) & 1)) & 0xFFFF0000
        out = np.zeros(self.hidden, np.uint16)
        out[: self.d0] = self.low_bits(mid)
        out[self.keep_cols_np] = (r >> 16).astype(np.uint16)
        return out, bool((r == u).all())


    def state_diff(self, cache):
        """Every value head's state, stock against the executor, at the end of a verified conversation. Differences at or below 2^-60 (counters past their tiny bound) are counted apart."""
        from chipformer.rv import hf
        c = self.chat.c
        r_ = c.target.value_heads // c.target.key_heads
        slots = {id(c.nodes[ni]): s for ni, s in hf.head_slots(c).items()}
        j = 0
        small = big = 0
        first = None
        for n in self.cx.heads:
            L, h = slots[id(n)]
            st = cache.layers[L].recurrent_states[0]
            for x in range(len(n.vheads())):
                a = st[0, h * r_ + x].detach().to(torch.float32).cpu().numpy()
                d = np.nonzero(a != self.cx.S[j])
                if len(d[0]):
                    gap = np.abs(a[d].astype(np.float64) - self.cx.S[j][d].astype(np.float64))
                    small += int((gap <= 2.0**-60).sum())
                    big += int((gap > 2.0**-60).sum())
                    if first is None and (gap > 2.0**-60).any():
                        k = int(np.argmax(gap))
                        first = {"head": n.name, "x": x, "row": int(d[0][k]), "col": int(d[1][k]), "stock": float(a[d][k]), "exec": float(self.cx.S[j][d][k])}
                j += 1
        return {"small": small, "big": big, "first": first}


def seeded_order(ids, seed):
    import random
    o = list(ids)
    random.Random(seed).shuffle(o)
    return o
