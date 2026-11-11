"""PC attribution for a firmware ELF: the symbol table (physical function) and DWARF inlining (what -O2 folded into it).

    A = Attrib(elf_with_g)      # A.chain[pc]: [(function, line), ...] outermost first; A.sym[pc]: the symtab symbol
    A.op[pc]: the instruction's name

The -g build must have the same code bytes as the build being profiled (checked by same_code).
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
LLVM = "/opt/homebrew/opt/llvm/bin"
VENDOR = os.path.join(X210, "vendor", "qwenputer-riscv")
if VENDOR not in sys.path:
    sys.path.insert(0, VENDOR)

from chipformer.rv import elf as E  # noqa: E402
from chipformer.rv import ref  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402


def same_code(a: str, b: str) -> bool:
    pa, pb = E.program(a), E.program(b)
    return pa.text == pb.text and pa.rodata == pb.rodata and pa.data == pb.data and pa.entry == pb.entry


class Attrib:
    def __init__(self, elf_g: str):
        prog = E.program(elf_g)
        self.words = {S.ROM_BASE + 4 * i: w for i, w in enumerate(prog.text)}
        self.op = {pc: ref.decode(w).op for pc, w in self.words.items()}
        nm = subprocess.run([f"{LLVM}/llvm-nm", "-n", elf_g], check=True, capture_output=True, text=True).stdout
        syms = []
        for ln in nm.splitlines():
            a, t, n = ln.split()
            a = int(a, 16)
            if t in "tT" and S.ROM_BASE <= a < S.ROM_BASE + 4 * S.ROM_WORDS:
                syms.append((a, n))
        self.starts = {a: n for a, n in syms}
        self.sym = {}
        k = 0
        for pc in sorted(self.words):
            while k + 1 < len(syms) and syms[k + 1][0] <= pc:
                k += 1
            self.sym[pc] = syms[k][1]
        pcs = sorted(self.words)
        inp = "\n".join(hex(p) for p in pcs) + "\n"
        out = subprocess.run([f"{LLVM}/llvm-symbolizer", f"--obj={elf_g}", "--inlining", "--output-style=JSON"],
                             input=inp, check=True, capture_output=True, text=True).stdout
        self.chain = {}
        for ln in out.splitlines():
            d = json.loads(ln)
            pc = int(d["Address"], 16)
            self.chain[pc] = [(s["FunctionName"], s["Line"]) for s in reversed(d["Symbol"])]  # outermost first
        assert len(self.chain) == len(pcs)
