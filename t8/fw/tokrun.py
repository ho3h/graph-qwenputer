#!/usr/bin/env python3
"""Run one of tok/'s scripts unchanged on the cleaner firmware: patched boot (t8/fw/overlay.py), tok's overlay, the noun on every graph that boots and in reflib, CHIP_FIRMWARE = clean.elf.

    python t8/fw/tokrun.py stock_trace.py --plan ... --outdir ...
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import overlay as OV  # noqa: E402  (first)
import noun as N  # noqa: E402

sys.modules["overlay"] = OV.O
ELF = os.path.join(HERE, "build_r6", "writes.elf") if os.environ.get("T8_R6") == "1" else os.path.join(HERE, "build_r5", "writes.elf") if os.environ.get("T8_R5") == "1" else os.path.join(HERE, "build_r4", "writes.elf") if os.environ.get("T8_R4") == "1" else os.path.join(HERE, "build_r3", "writes.elf") if os.environ.get("T8_R3") == "1" else os.path.join(HERE, "build_r2", "writes.elf") if os.environ.get("T8_R2") == "1" else os.path.join(HERE, "build_r1", "writes.elf") if os.environ.get("T8_R1") == "1" else os.path.join(HERE, "build_writes", "writes.elf") if os.environ.get("T8_WRITES") == "1" else os.path.join(HERE, "build", "clean.elf")
os.environ["CHIP_FIRMWARE"] = ELF
os.environ.setdefault("TOK_CKPT", os.path.expanduser("~/Models/x210/x210-tok"))
import boot as B  # noqa: E402
import reflib  # noqa: E402

_boot = OV._mod.boot


def boot(g, *a, **k):
    return _boot(N.with_noun(B.load(g)), *a, **k)


B.boot = boot
_G = reflib.Graph


class G(_G):
    def __init__(self, g):
        super().__init__(N.with_noun(g) if "noun" not in g else g)


reflib.Graph = G
if __name__ == "__main__":
    script = os.path.join(OV.TOK, sys.argv[1])
    sys.argv = [script] + sys.argv[2:]
    sys.path.insert(0, OV.TOK)
    runpy.run_path(script, run_name="__main__")
