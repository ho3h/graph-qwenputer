"""Boot a graph and run calls of the C library on the traced machine (ref.Machine + the graph coprocessor).

    r = Runner(graph, build="gop")        # or build="sw" (NO_GRAPH_OPS); index=False forces path's cursor search
    text, tokens, instructions = r.call("path", {"from": "@3", "to": "@9"})

A Runner keeps one parked machine, so RAM and coprocessor state persist between calls (close / reopen sequences).
Tokens count the run from GO to its HALT (the park), inclusive; instructions count records without R refreshes.
Arguments must be NFC already (SPEC 4's NFC step is not in the C library: see DEVLOG.md).
"""

import os
import subprocess
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
VENDOR = os.path.join(X210, "vendor", "qwenputer-riscv")
for p in (VENDOR, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from chipformer.rv import elf, spec as S  # noqa: E402

import boot as B  # noqa: E402
from cop_ref import CopMachine, is_gop  # noqa: E402

CLANG = "/opt/homebrew/opt/llvm/bin/clang"
LLD = "/opt/homebrew/opt/lld/bin/ld.lld"
ENV = os.path.join(VENDOR, "chipformer", "rv", "env")
SRC = [os.path.join(ENV, "crt0.S"), os.path.join(X210, "tools", "rt_mini.c"), os.path.join(HERE, "graphlib.c")]
BUILD = os.path.join(HERE, "build")
FLAGS = ["--target=riscv32-unknown-elf", "-march=rv32im_zba", "-mabi=ilp32", "-O2", "-ffreestanding", "-nostdlib",
         "-static", f"--ld-path={LLD}", "-Wall", "-Wextra", "-I" + ENV, "-T", os.path.join(ENV, "rom.ld")]
R_BASE, R_SIZE = S.FAMILIES["R"]


def build_elf(variant: str) -> str:
    """The ELF of one build ('gop' or 'sw'), rebuilt when a source is newer."""
    os.makedirs(BUILD, exist_ok=True)
    out = os.path.join(BUILD, f"graphlib-{variant}.elf")
    if not os.path.exists(out) or max(os.path.getmtime(s) for s in SRC) > os.path.getmtime(out):
        extra = ["-DNO_GRAPH_OPS"] if variant == "sw" else []
        tmp = f"{out}.{os.getpid()}"
        subprocess.run([CLANG, *FLAGS, *extra, *SRC, "-o", tmp], check=True, capture_output=True)
        os.replace(tmp, out)
    return out


def encode_call(fn: str, args: dict) -> bytes:
    b = fn.encode() + b"\0"
    for k, v in args.items():
        k, v = str(k), str(v)
        assert k and "\0" not in k + v
        assert unicodedata.normalize("NFC", v) == v, f"argument not NFC: {v!r}"
        b += k.encode() + b"\0" + v.encode() + b"\0"
    b += b"\0"
    assert len(b) <= S.TEXT_ROW * S.TEXT_ROWS, "call longer than the text buffer"
    return b


class Runner:
    def __init__(self, graph, build: str = "gop", index: bool = True, max_records: int = 50_000_000):
        self.variant, self.max_records = build, max_records
        prog = elf.program(build_elf(build))
        self.cop, drom = B.boot(graph, prog.rodata, software=build == "sw", index=index)
        self.m = CopMachine.make(prog, self.cop, drom)
        self.m.text = [bytes(S.TEXT_ROW)] * S.TEXT_ROWS
        text, _, _ = self._run()
        assert text == "", f"boot printed {text!r}"

    def _run(self):
        m = self.m
        m.halted = False
        o0, toks, instr = len(m.out), 1, 0  # GO
        self.search_tokens = None  # tokens before the first output byte (the answer is printed after the search)
        while not m.halted:
            rec = m.record()
            toks += len(rec)
            if self.search_tokens is None and len(m.out) > o0:
                self.search_tokens = toks
            if not (len(rec) == 1 and R_BASE <= rec[0] < R_BASE + R_SIZE and not is_gop(rec[0])):
                instr += 1
            if instr > self.max_records:
                raise RuntimeError("run did not park")
        if m.fault is not None:
            raise RuntimeError(f"fault {S.FAULTS[m.fault[0]]} at {m.fault[1]:#x}; out {bytes(m.out[o0:])!r}")
        return bytes(m.out[o0:]).decode("utf-8", "replace"), toks, instr

    def call(self, fn: str, args: dict):
        b = encode_call(fn, args)
        b = b.ljust(S.TEXT_ROW * S.TEXT_ROWS, b"\0")
        self.m.text = [b[i:i + S.TEXT_ROW] for i in range(0, len(b), S.TEXT_ROW)]
        return self._run()


if __name__ == "__main__":
    import json
    g, fn, args = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
    for v in ("gop", "sw"):
        print(v, Runner(g, v).call(fn, args))
