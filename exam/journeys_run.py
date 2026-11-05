#!/usr/bin/env python3
"""exam/AFTER.md Q: t8/fw/edit.py with `path` and `close`, and worked turns for them. T8_R1=1 T8_WRITES=1 T8_NOUN=on through tokrun."""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "rvc"), os.path.join(X210, "t8", "fw")]
import decode as D  # noqa: E402
import worked as W  # noqa: E402
import tools as HT  # noqa: E402

_gp = D.graph_path


def graph_path(name):
    if name == "nyc":
        b = os.path.join(X210, "data", "heldout", "nyc", "nyc")
        return b + ".graph.json", b + ".questions.json"
    if name == "nyc-b":                                            # exam/AFTER.md r6: a closed stop blocks
        b = os.path.join(X210, "data", "heldout", "nyc", "nyc")
        return os.path.join(HERE, "items", "nyc_b.graph.json"), b + ".questions.json"
    if name == "nyc-relabelled-b":                                 # exam/AFTER.md S5
        return os.path.join(HERE, "items", "sealed", "nyc-relabelled_b.graph.json"), os.path.join(X210, "data", "heldout", "nyc-relabelled", "nyc-relabelled.questions.json")
    return _gp(name)


D.graph_path = graph_path
base = {t["function"]["name"]: t for t in HT.tools_for("base")}
W.TOOLS = W.TOOLS + [copy.deepcopy(base[k]) for k in ("path", "close")]


def call(fn, args, line):
    return [{"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": fn, "arguments": args}}]}, {"role": "tool", "content": line}]


H = [{"role": "user", "content": "What's the route with the fewest stops from Ash Rd to Oak Av?"}]
H += call("path", {"from": "Ash Rd", "to": "Oak Av"}, "2 steps: @3 Ash Rd > @7 Elm Sq > @9 Oak Av") + [{"role": "assistant", "content": "Ash Rd, Elm Sq, Oak Av"}]
H += [{"role": "user", "content": "Elm Sq is closed. What's the route now?"}]
H += call("close", {"node": "Elm Sq"}, "closed @7 Elm Sq") + call("path", {"from": "Ash Rd", "to": "Oak Av"}, "3 steps: @3 Ash Rd > @5 Pine St > @6 Birch Av > @9 Oak Av") + [{"role": "assistant", "content": "Ash Rd, Pine St, Birch Av, Oak Av"}]
if os.environ.get("J_REOPEN") == "1":                              # exam/AFTER.md r6: the walkthrough reopens a stop
    W.TOOLS = W.TOOLS + [copy.deepcopy(base["reopen"])]
    H += [{"role": "user", "content": "Elm Sq is open again. What's the route now?"}]
    H += call("reopen", {"node": "Elm Sq"}, "reopened @7 Elm Sq") + call("path", {"from": "Ash Rd", "to": "Oak Av"}, "2 steps: @3 Ash Rd > @7 Elm Sq > @9 Oak Av") + [{"role": "assistant", "content": "Ash Rd, Elm Sq, Oak Av"}]
W.HISTORY = W.HISTORY + H
src = open(os.path.join(X210, "t8", "fw", "edit.py")).read()
sys.argv[0] = os.path.join(X210, "t8", "fw", "edit.py")
sys.path.insert(0, os.path.dirname(sys.argv[0]))
exec(compile(src, sys.argv[0], "exec"), {"__name__": "__main__", "__file__": sys.argv[0]})
