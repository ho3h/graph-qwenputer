"""Import this first. Inside this process only, it makes `chipformer.rv.core` the tok/ copy, adds the id rule to bridge.Text, teaches bridge.Session the id print and
HALT's echo, and points cop/boot.py's boot at tok/boot_tok.py. Nothing on disk under vendor/, cop/, rvc/, fw/ or exec/ changes.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
for p in (HERE, os.path.join(X210, "cop"), os.path.join(X210, "host"), os.path.join(X210, "lib"), os.path.join(X210, "vendor", "qwenputer-riscv")):
    if p not in sys.path:
        sys.path.insert(0, p)
import chipformer.rv  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402
from chipformer.rv import ref  # noqa: E402

_spec = importlib.util.spec_from_file_location("chipformer.rv.core", os.path.join(HERE, "core.py"))
core = importlib.util.module_from_spec(_spec)
sys.modules["chipformer.rv.core"] = core
_spec.loader.exec_module(core)
chipformer.rv.core = core

from chipformer.rv import bridge as BR  # noqa: E402

N_TOKENS = 248070  # Qwen3.5's vocabulary with its added tokens; the merged tokenizer adds reserved and chip names after these


def id_ok(self, q):
    """A token the machine may print by id: in Qwen's vocabulary, not a tool-call token."""
    return 0 <= q < N_TOKENS and q != self.TCO and q != self.TCC and self.pindex.get(q) is None


BR.Text.id_ok = id_ok


def run(self, max_records=10**6):
    """bridge.Session.run with: BYTE(511) echoes the token whose id the next instruction reads; HALT echoes \\n\\n."""
    m, echo = self.m, []
    self._push(S.tok("GO"), True)
    m.halted = False
    n = 0
    while n < max_records:
        rec = m.record()
        n += 1
        for t in rec:
            self._push(t, True)
            fam, p = S.family(t)
            if fam == "BYTE":
                if p == core.PRINT_ID:
                    ins = ref.decode(m.rom[(m.pc - S.ROM_BASE) >> 2])
                    assert ins.op == "ADDI" and ins.rd == 0 and ins.imm == 0, ins
                    q = m.x[ins.rs1]
                    assert self.T.id_ok(q), q
                else:
                    q = self.T.printable[p] if p < len(self.T.printable) else self.T.NL
                echo.append(q)
                self._push(BR.text_token(q), True)
        if rec[-1] == S.tok("HALT"):
            echo.append(core.NN)
            self._push(BR.text_token(core.NN), False)
            break
    else:
        raise RuntimeError("the run did not halt")
    if m.fault is None:
        m.halted = False
    self.runs.append(echo)
    return echo


BR.Session.run = run

import boot as _B  # noqa: E402  (cop/boot.py, in memory only)
import boot_tok as BT  # noqa: E402

_B.boot = BT.boot
_B.HDR_WORDS = BT.HDR_WORDS


def set_text(T):
    BT.TEXT = T
