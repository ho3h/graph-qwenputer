"""One firmware build on the reference machine, with a calling-context profile of machine tokens.

rvc/box.py is used read-only; this file points its build at fw/build, so rvc/build is never touched. ProfMachine counts
per (calling context, pc): tokens and records. A context is the chain of call-site pcs (tree id); tail calls are
tracked (the frame is popped with its caller's return). No output byte or token depends on any of this.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(X210, "rvc"))
sys.path.insert(0, HERE)
import box as X  # noqa: E402  (rvc/box.py, unchanged)

from chipformer.rv import bridge as BR  # noqa: E402,F401
from chipformer.rv import elf, ref  # noqa: E402,F401
from chipformer.rv import spec as S  # noqa: E402

import boot as B  # noqa: E402

BUILD = os.path.join(HERE, "build")
ENV = X.ENV
RAW_FLAGS = [f for f in X.FLAGS]


def set_firmware(name: str, src: str, extra=()) -> str:
    """Point rvc/box.py's build at fw/build/<name>.elf from `src`; builds if needed. rvc/ itself is never written."""
    elf_path = os.path.join(BUILD, name + ".elf")
    X.ELF = elf_path
    X.SRC = [os.path.join(ENV, "crt0.S"), os.path.join(X210, "tools", "rt_mini.c"), src]
    X.FLAGS = RAW_FLAGS + list(extra)
    return X.build_elf()


def build_g(src: str, name: str, extra=()) -> str:
    """The same build with -g, for symbolisation only (the code bytes are checked equal by the caller)."""
    out = os.path.join(BUILD, name + "-g.elf")
    subprocess.run([X.CLANG, *RAW_FLAGS, *extra, "-g", os.path.join(ENV, "crt0.S"),
                    os.path.join(X210, "tools", "rt_mini.c"), src, "-o", out], check=True, capture_output=True)
    return out


class ProfMachine(ref.Machine):
    """ref.Machine with a calling-context token count. Records and state are the parent's, untouched."""

    def prof_init(self, starts, sym):
        self.p_starts, self.p_sym = starts, sym
        self.p_tree = {}                 # (parent id, call-site pc) -> id
        self.p_parent = [(-1, 0, False)]  # id -> (parent, call-site pc, is_tail)
        self.p_ctx = 0
        self.p_tally = {}                # (ctx id, pc) -> [tokens, records]
        self.p_kind = {}

    def p_kind_of(self, pc):
        k = self.p_kind.get(pc)
        if k is None:
            ins = ref.decode(self.rom[(pc - S.ROM_BASE) >> 2])
            if ins.op in ("JAL", "JALR") and ins.rd in (1, 5):
                k = 1                    # call
            elif ins.op == "JALR" and ins.rd == 0 and ins.rs1 in (1, 5):
                k = 2                    # return
            else:
                k = 0
            self.p_kind[pc] = k
        return k

    def p_push(self, pc, tail):
        key = (self.p_ctx, pc)
        c = self.p_tree.get(key)
        if c is None:
            c = len(self.p_parent)
            self.p_tree[key] = c
            self.p_parent.append((self.p_ctx, pc, tail))
        self.p_ctx = c

    def record(self):
        pc = self.pc
        n0 = self.n
        toks = super().record()
        refresh = n0 == S.N_MAX           # an R refresh executes nothing: tokens to pc, no record
        key = (self.p_ctx, pc)
        t = self.p_tally.get(key)
        if t is None:
            t = self.p_tally[key] = [0, 0]
        t[0] += len(toks)
        t[1] += 0 if refresh else 1
        if not refresh and not self.halted:
            new = self.pc
            k = self.p_kind_of(pc)
            if k == 1:
                self.p_push(pc, False)
            elif k == 2:
                while self.p_parent[self.p_ctx][2]:   # tail frames return with the frame that called them
                    self.p_ctx = self.p_parent[self.p_ctx][0]
                if self.p_ctx:
                    self.p_ctx = self.p_parent[self.p_ctx][0]
            elif new in self.p_starts and self.p_sym.get(new) != self.p_sym.get(pc):
                self.p_push(pc, True)             # a jump to another function's entry: a tail call
            elif self.p_sym.get(new) != self.p_sym.get(pc):
                self.p_push(pc, True)             # any other jump out of the function (a shared tail)
        return toks

    def context(self, ctx):
        out = []
        while ctx:
            p, pc, _ = self.p_parent[ctx]
            out.append(pc)
            ctx = p
        return tuple(reversed(out))


class Box(X.Box):
    """rvc/box.py's Box, optionally with the profiling machine."""

    def __init__(self, g, T, attrib=None, max_records=4_000_000):
        prog = elf.program(X.build_elf())
        _, drom = B.boot(g, prog.rodata, software=True)
        m = (ProfMachine if attrib else ref.Machine).from_program(prog)
        if attrib:
            m.prof_init(attrib.starts, attrib.sym)
        m.drom = drom
        BR.park(m)
        if attrib:
            m.p_tally, m.p_ctx = {}, 0
        self.T, self.m, self.max_records, self.drom_bytes = T, m, max_records, len(drom)
        self.ses = BR.Session(T, m)
        self.head = b"\n<tool_response>\n"
        self.tail = b"\n</tool_response>\n<think>\n\n</think>\n\n"
