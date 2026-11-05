"""T8: test_ref_m1.py's test on the piece-table firmware. See REGISTRATION.md.

    python tok/test_pieces.py --workers 4
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import overlay as O  # noqa: E402
import boot_tok as BT  # noqa: E402
import pieces as P  # noqa: E402
import test_ref_m1 as R  # noqa: E402

BT.HDR_WORDS = 30
O._B.HDR_WORDS = 30
_boot = BT.boot


def boot(g, rodata, software, index=True):
    cop, drom = _boot(g, rodata, software, index)
    if software:
        g2 = BT.load(g)
        names = [n["label"] for n in g2["nodes"]] + list(g2["relations"])
        if g2.get("domain") == "transit":
            names.append("station")
        drom, _ = P.attach(drom, names)
    return cop, drom


O._B.boot = boot
BT_DIR = os.path.join(HERE, "pieces")
SRC = os.path.join(BT_DIR, "graphlib.c")
R.OUT = os.path.join(HERE, "results", "t8")
R.TOK_LOG = os.path.join(R.OUT, "tok_by_task.jsonl")
R.M.OUT = R.OUT
_set = R.F.set_firmware
R.F.set_firmware = lambda name, src, extra: _set("tok-pieces", SRC, ["-I" + HERE])


def adapter_init():
    R.adapter_init()


if __name__ == "__main__":
    os.makedirs(BT_DIR, exist_ok=True)
    s = P.patch(open(os.path.join(HERE, "graphlib.c")).read())
    open(SRC, "w").write(s)
    R.M.init_worker = adapter_init
    os.makedirs(R.OUT, exist_ok=True)
    if os.path.exists(R.TOK_LOG):
        os.remove(R.TOK_LOG)
    R.F.BUILD = os.path.join(HERE, "build")
    R.F.set_firmware("tok-pieces", SRC, [])
    R.M.main()
