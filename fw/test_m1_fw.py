"""rvc/test_m1.py's byte comparison against lib/reflib.py on a fw/ build. The test is imported unchanged; only the ELF it
builds and the folder it writes are redirected, so nothing under rvc/ is written.

    python fw/test_m1_fw.py --firmware fw/graphlib.c --tag fw [--define FW_NO_PARSE ...] [--workers 4] [--quick] [--parts ...]
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
X210 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(X210, "rvc"))
import fwbox as F  # noqa: E402
import test_m1 as M  # noqa: E402

_init = M.init_worker
CFG = os.environ.get("FW_TEST_CFG", "")


def adapter_init():
    name, src, extra, out = CFG.split("|")
    F.set_firmware(name, src, [e for e in extra.split(",") if e])
    M.OUT = out
    _init()


def main():
    global CFG
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--firmware", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--define", action="append", default=[])
    a, rest = ap.parse_known_args()
    src = os.path.abspath(a.firmware)
    out = os.path.join(HERE, "results", f"m1_{a.tag}")
    os.makedirs(out, exist_ok=True)
    extra = [f"-D{d}" for d in a.define]
    CFG = f"{a.tag}|{src}|{','.join(extra)}|{out}"
    os.environ["FW_TEST_CFG"] = CFG
    F.set_firmware(a.tag, src, extra)
    M.OUT = out
    M.init_worker = adapter_init
    sys.argv = [sys.argv[0], *rest]
    M.main()


if __name__ == "__main__":
    main()
