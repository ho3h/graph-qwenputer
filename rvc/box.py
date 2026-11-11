"""The C library as bridge firmware on the reference machine: ref.Machine + bridge.Session, one graph per snapshot.

    box = Box(graph_dict, text)          # text: bridge.Text; the graph goes into the DROM image, never into the ELF
    r = box.call(ids)                    # ids: the Qwen tokens between <tool_call> and </tool_call>
    r.result, r.chip, r.echo, r.records  # the printed result, chip tokens, echoed text tokens, instructions

Also: the Python side of the same call (host/tools.py parse_call + reflib through the capture rule), the template text
of a call, and the build. Run from the vendored folder so `chipformer` resolves to the vendored copy.
"""

import os
import subprocess
import sys
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
VENDOR = os.path.join(X210, "vendor", "qwenputer-riscv")
for p in (VENDOR, os.path.join(X210, "cop"), os.path.join(X210, "host"), os.path.join(X210, "lib"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import elf, ref  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402

import boot as B  # noqa: E402  (cop/boot.py, unchanged: the DROM image)
import tools as HT  # noqa: E402  (host/tools.py, unchanged: the call parser and the response bytes)

MODEL = ("/Volumes/LaCie/Models/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/"
         "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")
ENV = os.path.join(VENDOR, "chipformer", "rv", "env")
CLANG = "/opt/homebrew/opt/llvm/bin/clang"
LLD = "/opt/homebrew/opt/lld/bin/ld.lld"
SRC = [os.path.join(ENV, "crt0.S"), os.path.join(X210, "tools", "rt_mini.c"), os.path.join(HERE, "graphlib.c")]
ELF = os.path.join(HERE, "build", "graphlib-bridge.elf")
FLAGS = ["--target=riscv32-unknown-elf", "-march=rv32im_zba", "-mabi=ilp32", "-O2", "-ffreestanding", "-nostdlib",
         "-static", f"--ld-path={LLD}", "-DNO_GRAPH_OPS", "-DBRIDGE", "-I" + ENV, "-T", os.path.join(ENV, "rom.ld")]
CAP_ROWS = S.CAP_MAX
TOOLONG = "TOOLONG"


def build_elf() -> str:
    os.makedirs(os.path.dirname(ELF), exist_ok=True)
    if not os.path.exists(ELF) or max(os.path.getmtime(s) for s in SRC) > os.path.getmtime(ELF):
        tmp = f"{ELF}.{os.getpid()}"
        subprocess.run([CLANG, *FLAGS, *SRC, "-o", tmp], check=True, capture_output=True)
        os.replace(tmp, ELF)
    return ELF


def tokenizer_json() -> str:
    return os.path.join(MODEL, "tokenizer.json")


def template_text(fn: str, args: dict) -> str:
    """A call as Qwen's template writes it, between <tool_call> and </tool_call>."""
    s = f"\n<function={fn}>\n"
    for k, v in args.items():
        s += f"<parameter={k}>\n{v}\n</parameter>\n"
    return s + "</function>\n"


def machine_for(g, setup=None, text=None, parked=True) -> ref.Machine:
    """The parked machine for graph g (a dict): the firmware, with the graph in the DROM."""
    prog = elf.program(build_elf())
    _, drom = B.boot(g, prog.rodata, software=True)
    m = ref.Machine.from_program(prog)
    m.drom = drom
    BR.park(m)
    return m


class TrackedMachine(ref.Machine):
    """ref.Machine that keeps the lowest stack pointer seen (the RAM high-water check)."""

    min_sp: int = S.SP_INIT

    def record(self):
        toks = super().record()
        sp = self.x[2]
        if sp < self.min_sp:
            self.min_sp = sp
        return toks


@dataclass
class Result:
    result: str
    raw: bytes
    chip: int
    echo: int
    records: int
    ok_wrap: bool


class Box:
    def __init__(self, g, T: BR.Text, track: bool = False, max_records: int = 2_000_000):
        prog = elf.program(build_elf())
        _, drom = B.boot(g, prog.rodata, software=True)
        cls = TrackedMachine if track else ref.Machine
        m = cls.from_program(prog)
        m.drom = drom
        BR.park(m)
        self.T, self.m, self.max_records, self.drom_bytes = T, m, max_records, len(drom)
        self.ses = BR.Session(T, m)
        self.head = b"\n<tool_response>\n"
        self.tail = b"\n</tool_response>\n<think>\n\n</think>\n\n"

    def call(self, ids) -> Result:
        """One tool call: <tool_call> ids </tool_call>, then the machine's run."""
        s = self.ses
        k = len(s.toks)
        steps0 = self.m.steps
        s.qwen([self.T.TCO] + list(ids) + [self.T.TCC], max_records=self.max_records)
        run = s.toks[k + len(ids) + 2:]
        if self.m.fault is not None:
            raise RuntimeError(f"fault {S.FAULTS[self.m.fault[0]]} at {self.m.fault[1]:#x}")
        raw = self.T.decode_bytes(s.runs[-1])
        ok = raw.startswith(self.head) and raw.endswith(self.tail) and len(raw) >= len(self.head) + len(self.tail)
        body = raw[len(self.head):-len(self.tail)] if ok else raw
        chip = sum(not S.is_text(t) for t in run)
        return Result(body.decode("utf-8", "surrogateescape"), raw, chip, len(run) - chip, self.m.steps - steps0, ok)


def capture_rule(ids, T: BR.Text) -> bool:
    """True when the firmware must answer TOOLONG: what the 80 rows keep cannot be trusted. (The same rule as
    graphlib.c gather / call, on the Python side.) More than 80 tokens: rows 1..79, and row 80 holds the last token."""
    kept = list(ids) if len(ids) <= CAP_ROWS else list(ids[:CAP_ROWS - 1]) + [ids[-1]]
    if any(len(T.bytes[q]) >= S.TEXT_ROW for q in kept):
        return True
    return len(kept) == CAP_ROWS and b"</function>" not in b"".join(T.bytes[q] for q in kept)


def reference(graph, inner_text: str) -> str:
    """The host tool on the same call (host/tools.py, reflib): what the host baseline prints."""
    return HT.answer_call(graph, HT.parse_call(inner_text))
