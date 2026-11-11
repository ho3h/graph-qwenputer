#!/usr/bin/env python3
"""t8/fw/edit.py unchanged, with New York's path known to decode.graph_path. Through tokrun with T8_WRITES=1."""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(X210, "rvc"))
import decode as D  # noqa: E402

_gp = D.graph_path


def graph_path(name):
    if name == "nyc":
        assert os.path.exists(os.path.join(HERE, "FROZEN"))
        b = os.path.join(X210, "data", "heldout", "nyc", "nyc")
        return b + ".graph.json", b + ".questions.json"
    return _gp(name)


D.graph_path = graph_path
script = os.path.join(X210, "t8", "fw", "edit.py")
sys.argv[0] = script
sys.path.insert(0, os.path.dirname(script))
runpy.run_path(script, run_name="__main__")
