#!/usr/bin/env python3
"""exam/AFTER.md L: t8/fw/edit.py unchanged in logic, with the new tools and worked turns. T8_R1=1 T8_WRITES=1 T8_NOUN=on through tokrun."""
import copy
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "rvc"), os.path.join(X210, "t8", "fw")]
import decode as D  # noqa: E402
import worked as W  # noqa: E402
import tools as HT  # noqa: E402

_gp = D.graph_path
D.graph_path = lambda name: (os.environ.get("RUN_GRAPH") or os.path.join(HERE, "items", "nyc_t.graph.json"), None) if name == "nyc-t" else _gp(name)
base = {t["function"]["name"]: t for t in HT.tools_for("base")}
W.TOOLS = W.TOOLS + [copy.deepcopy(base[k]) for k in ("link", "unlink", "neighbours")]


def call(fn, args, line):
    return [{"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": fn, "arguments": args}}]}, {"role": "tool", "content": line}]


H = [{"role": "user", "content": "A new V train starts today. Northbound it runs Ash Rd, Elm Sq, Oak Av."}]
H += call("link", {"from": "Ash Rd", "relation": "V northbound", "to": "Elm Sq"}, "linked @3 Ash Rd > V northbound > @7 Elm Sq")
H += call("link", {"from": "Elm Sq", "relation": "V northbound", "to": "Oak Av"}, "linked @7 Elm Sq > V northbound > @9 Oak Av")
H += [{"role": "assistant", "content": "Done."}]
H += [{"role": "user", "content": "Start at Ash Rd station. Ride the V train 2 stops northbound. One stop means the next station. At which station are you now? Answer with the station name only."}]
H += call("chase", {"start": "Ash Rd", "legs": "V northbound 2"}, "@9 Oak Av") + [{"role": "assistant", "content": "Oak Av"}]
H += [{"role": "user", "content": "What's the next stop after Ash Rd on the V train going northbound? Answer with the station name only."}]
H += call("neighbours", {"node": "Ash Rd", "relation": "V northbound"}, "@7 Elm Sq") + [{"role": "assistant", "content": "Elm Sq"}]
H += [{"role": "user", "content": "The V train has been cancelled."}]
H += call("unlink", {"from": "Ash Rd", "relation": "V northbound", "to": "Elm Sq"}, "unlinked @3 Ash Rd > V northbound > @7 Elm Sq")
H += call("unlink", {"from": "Elm Sq", "relation": "V northbound", "to": "Oak Av"}, "unlinked @7 Elm Sq > V northbound > @9 Oak Av")
H += [{"role": "assistant", "content": "Done."}]
if os.environ.get("T8_R2") == "1":                                # exam/AFTER.md L2
    W.TOOLS = W.TOOLS + [{"type": "function", "function": {"name": "add_node", "description": "Add a new node with this name. Returns 'added @handle name'.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "the new node's name"}}, "required": ["name"]}}}]
    H += [{"role": "user", "content": "A new W train starts today, with two brand-new stations, Reed Pk and Sage St. Northbound it runs Ash Rd, Reed Pk, Sage St, Oak Av."}]
    H += call("add_node", {"name": "Reed Pk"}, "added @12 Reed Pk") + call("add_node", {"name": "Sage St"}, "added @13 Sage St")
    H += call("link", {"from": "Ash Rd", "relation": "W northbound", "to": "Reed Pk"}, "linked @3 Ash Rd > W northbound > @12 Reed Pk")
    H += call("link", {"from": "Reed Pk", "relation": "W northbound", "to": "Sage St"}, "linked @12 Reed Pk > W northbound > @13 Sage St")
    H += call("link", {"from": "Sage St", "relation": "W northbound", "to": "Oak Av"}, "linked @13 Sage St > W northbound > @9 Oak Av")
    H += [{"role": "assistant", "content": "Done."}]
if os.environ.get("R3_PATH") == "1":                              # exam/AFTER.md r3: a route across an added line
    W.TOOLS = W.TOOLS + [copy.deepcopy(base["path"])]
    H += [{"role": "user", "content": "What's the route with the fewest stops from Ash Rd to Oak Av?"}]
    H += call("path", {"from": "Ash Rd", "to": "Oak Av"}, "2 steps: @3 Ash Rd > @7 Elm Sq > @9 Oak Av") + [{"role": "assistant", "content": "Ash Rd, Elm Sq, Oak Av"}]
W.HISTORY = W.HISTORY + H
src = open(os.path.join(X210, "t8", "fw", "edit.py")).read()
assert src.count("MAX_CALLS, TURN, TOTAL = 6, 320, 1536") == 1
src = src.replace("MAX_CALLS, TURN, TOTAL = 6, 320, 1536", "MAX_CALLS, TURN, TOTAL = 12, 320, 3072")
sys.argv[0] = os.path.join(X210, "t8", "fw", "edit.py")
sys.path.insert(0, os.path.dirname(sys.argv[0]))
g = {"__name__": "__main__", "__file__": sys.argv[0]}
exec(compile(src, sys.argv[0], "exec"), g)
