"""The machine exams' engine pair on writes.elf: the executor free-running, with coverage logged, and the reference machine beside it, every call, tokens compared. Copy of edits2/machine.py's call loop on tok's tables. Run through t8/fw/tokrun.py with T8_WRITES=1, which sets the firmware, the noun and reflib.

    pair = Pair(graph_dict, prompt_ids)
    pair.fresh()
    r = pair.call(ids)   # {"body", "status", "wrap", "chip", "echo", "digest", "flags", "ref_body", "ref_digest", "same"}
"""
import ctypes as ct
import hashlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(X210, "rvc"))
sys.path.insert(0, os.path.join(X210, "t8", "fw"))
import cov as CV  # noqa: E402  (exec/covdiff on tok's tables: the engine with coverage stores)
import fragments as FR  # noqa: E402

C, D, core, BR, CExec, X = CV.C, CV.D, CV.core, CV.BR, CV.CExec, CV.X
from cexec import CProg  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402

MAX_CALL = 4_000_000
HEAD, TAIL = FR.HEAD.encode(), FR.TAIL.encode()


class Pair:
    def __init__(self, g, prompt_ids, between_ids=(), coverage=True):
        self.L = C.Lite(tokenizer=False)
        L = self.L
        self.T = L.T
        self.g = g
        m = D.parked_machine(g, L.T, None)
        core.snapshot(L.c, m)
        self.ex = CExec(L.c, L.T)
        self.ex.lib.chip_next.argtypes = [ct.POINTER(CProg)]
        self.ex.lib.chip_next.restype = ct.c_int32
        self.cov = CV.ns["Cov"](self.ex, "exam") if coverage else None
        self.ex.p.flags = 0
        self.ex.start([BR.text_token(i) if i < L.v0 else i - L.v0 for i in prompt_ids])
        self.st0 = self.ex.save()
        self.between = list(between_ids)
        self.fresh()

    def fresh(self):
        self.ex.restore(self.st0)
        self.first = True
        self.box = X.Box(self.g, self.T, max_records=MAX_CALL)
        if self.cov is not None:
            self.cov.reset()

    def _ref(self, ids, first):
        s, T = self.box.ses, self.T
        s.toks.clear()
        s.own.clear()
        if not first:
            s.qwen(self.between)
        s.qwen([T.TCO] + list(ids) + [T.TCC], max_records=MAX_CALL)
        go = S.tok("GO")
        run = s.toks
        i = next(j for j, t in enumerate(run) if t == go)
        tail = np.array(run[i:], np.int32)
        raw = T.decode_bytes(s.runs[-1])
        s.runs.clear()
        ok = raw.startswith(HEAD) and raw.endswith(TAIL) and len(raw) >= len(HEAD) + len(TAIL)
        body = raw[len(HEAD):-len(TAIL)] if ok else raw
        return body.decode("utf-8", "surrogateescape"), hashlib.blake2b(tail.tobytes(), digest_size=8).hexdigest()

    def call(self, ids):
        ex, T = self.ex, self.T
        first = self.first
        h = hashlib.blake2b(digest_size=8)
        stream = ([] if first else [BR.text_token(i) for i in self.between]) + [BR.text_token(T.TCO)] + [BR.text_token(i) for i in ids] + [BR.text_token(T.TCC)]
        self.first = False
        ex.run(stream, keep=False)
        t = ex.lib.chip_next(ct.byref(ex.p))
        echo, chip, spent, status = [], 0, 0, None
        while status is None:
            if t == -1:
                status = "ok" if echo else "no_run"
            elif t == -2:
                status = "decode"
            elif spent >= MAX_CALL:
                status = "max"
            elif t < S.VOCAB:
                st, o, n, rec = ex.burst(t, MAX_CALL - spent, record=True)
                chip += n
                spent += n
                h.update(np.array([t], np.int32).tobytes())
                h.update(rec[: n - 1].tobytes())
                t = o if st != "max" else -3
                if st in ("max", "decode"):
                    status = st
            else:
                h.update(np.array([t], np.int32).tobytes())
                ex.step(t)
                echo.append(t - S.TEXT_TOKEN)
                spent += 1
                t = ex.lib.chip_next(ct.byref(ex.p))
        raw = T.decode_bytes(echo)
        ok = status == "ok" and raw.startswith(HEAD) and raw.endswith(TAIL) and len(raw) >= len(HEAD) + len(TAIL)
        body = (raw[len(HEAD):-len(TAIL)] if ok else raw).decode("utf-8", "surrogateescape")
        d = h.hexdigest()
        ref_body, ref_d = self._ref(ids, first)
        return {"body": body, "status": status, "wrap": ok, "chip": chip, "echo": len(echo), "digest": d, "flags": ex.flags(), "ref_body": ref_body, "ref_digest": ref_d, "same": body == ref_body and d == ref_d}
