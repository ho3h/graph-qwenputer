#!/usr/bin/env python3
"""Coverage of New York's calls against the stock baseline, and the greedy pick for its stock window: t8/fw/cov.py's chain and pick, with New York's path known and D1m's tags accepted. Through tokrun, T8_WRITES=1.

    python t8/fw/tokrun.py ../exam/cov_exam.py pick --baseline B --budget N --rows R... --out plan.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "rvc"), os.path.join(X210, "t8", "fw")]
import cov as CV  # noqa: E402

_gp = CV.D.graph_path


def graph_path(name):
    if name == "nyc":
        assert os.path.exists(os.path.join(HERE, "FROZEN"))
        b = os.path.join(X210, "data", "heldout", "nyc", "nyc")
        return b + ".graph.json", b + ".questions.json"
    return _gp(name)


CV.D.graph_path = graph_path
if sys.argv[1] == "pick":
    i = sys.argv.index("--out")
    CV.pick(sys.argv[sys.argv.index("--rows") + 1:i], sys.argv[sys.argv.index("--baseline") + 1], sys.argv[i + 1], int(sys.argv[sys.argv.index("--budget") + 1]))
else:
    i = sys.argv.index("--out")
    CV.chain(sys.argv[sys.argv.index("--rows") + 1:i], sys.argv[i + 1])
