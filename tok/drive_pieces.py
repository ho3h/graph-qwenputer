"""tok/drive.py on the piece-table firmware: same flow, same checkpoint. See REGISTRATION.md T9."""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["CHIP_FIRMWARE"] = os.path.join(HERE, "build", "tok-pieces.elf")
import overlay as O  # noqa: E402
import boot_tok as BT  # noqa: E402
import pieces as P  # noqa: E402

BT.HDR_WORDS = 30
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
sys.argv = [os.path.join(HERE, "drive.py")] + sys.argv[1:]
runpy.run_path(os.path.join(HERE, "drive.py"), run_name="__main__")
