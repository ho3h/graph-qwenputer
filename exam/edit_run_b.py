#!/usr/bin/env python3
"""exam/AFTER.md E6: t8/fw/edit.py unchanged, on the blocking map, with the two closure turns showing the blocking rule. Through tokrun with T8_R1..R6, T8_WRITES."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "rvc"), os.path.join(X210, "t8", "fw"), os.path.join(X210, "toolkit"), os.path.join(X210, "release", "toolkit")]
import decode as D  # noqa: E402
import turns as TN  # noqa: E402
import worked as W  # noqa: E402

_gp = D.graph_path


def graph_path(name):
    if name == "nyc-b":
        return os.path.join(HERE, "items", "nyc_b.graph.json"), os.path.join(X210, "data", "heldout", "nyc", "nyc.questions.json")
    if name in ("nyc-cf-b", "nyc-relabelled-b"):                   # exam/AFTER.md, the sealed maps
        m = name[:-2]
        return os.path.join(HERE, "items", "sealed", m + "_b.graph.json"), os.path.join(X210, "data", "heldout", m, m + ".questions.json")
    return _gp(name)


D.graph_path = graph_path
W.HISTORY = TN.blocking(W.HISTORY)
script = os.path.join(X210, "t8", "fw", "edit.py")
sys.argv[0] = script
sys.path.insert(0, os.path.dirname(script))
exec(compile(open(script).read(), script, "exec"), {"__name__": "__main__", "__file__": script})
