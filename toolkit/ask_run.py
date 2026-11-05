#!/usr/bin/env python3
"""Qwen with the graph-qwenputer in its layers: t8/fw/edit.py with the tools and worked turns you choose. Run by run.py through t8/fw/tokrun.py."""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [HERE, os.path.join(ROOT, "rvc"), os.path.join(ROOT, "t8", "fw")]
import calls as C  # noqa: E402
import decode as D  # noqa: E402
import turns as TN  # noqa: E402
import worked as W  # noqa: E402
import tools as HT  # noqa: E402

_gp = D.graph_path
D.graph_path = lambda name: (os.environ["RUN_GRAPH"], None) if name == "run" else _gp(name)
base = {t["function"]["name"]: t for t in HT.tools_for("base")}
ADD_NODE = {"type": "function", "function": {"name": "add_node", "description": "Add a new node with this name. Returns 'added @handle name'.", "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "the new node's name"}}, "required": ["name"]}}}
base["add_node"] = ADD_NODE
wanted, msg = C.tools_wanted(os.environ.get("GQ_TOOLS"))
if msg:
    sys.exit(msg)
g = json.load(open(os.environ["RUN_GRAPH"], encoding="utf-8"))
chase = W.TOOLS[0]
if g.get("domain") != "transit":                                    # the frozen wording says stations
    for p in chase["function"]["parameters"]["properties"].values():
        p["description"] = p["description"].replace("stations", "nodes")
    if g["relations"]:
        chase["function"]["parameters"]["properties"]["legs"]["description"] = f"legs such as '{g['relations'][0]} 3; {g['relations'][-1]} 1'"
W.TOOLS = ([chase] if "chase" in wanted else []) + [copy.deepcopy(base[k]) for k in wanted if k != "chase"]


def turn(user, calls, reply):
    out = [{"role": "user", "content": user}]
    for c in calls:
        out += [{"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": c["fn"], "arguments": c["args"]}}]}, {"role": "tool", "content": c["result"]}]
    return out + [{"role": "assistant", "content": reply}]


if os.environ.get("GQ_EXAMPLES"):
    turns_, msg = C.read_examples(os.environ["GQ_EXAMPLES"], wanted)
    if msg:
        sys.exit(msg)
    W.HISTORY = [m for t in turns_ for m in turn(t["user"], t["calls"], t["reply"])]
else:
    D_ = [("What's the next stop after Ash Rd on the V train going northbound? Answer with the station name only.", [("neighbours", {"node": "Ash Rd", "relation": "V northbound"}, "@7 Elm Sq")], "Elm Sq"),
          ("What's the route with the fewest stops from Ash Rd to Oak Av?", [("path", {"from": "Ash Rd", "to": "Oak Av"}, "2 steps: @3 Ash Rd > @7 Elm Sq > @9 Oak Av")], "Ash Rd, Elm Sq, Oak Av"),
          ("Elm Sq is closed. What's the route now?", [("close", {"node": "Elm Sq"}, "closed @7 Elm Sq"), ("path", {"from": "Ash Rd", "to": "Oak Av"}, "3 steps: @3 Ash Rd > @5 Pine St > @6 Birch Av > @9 Oak Av")], "Ash Rd, Pine St, Birch Av, Oak Av"),
          ("Elm Sq is open again. What's the route now?", [("reopen", {"node": "Elm Sq"}, "reopened @7 Elm Sq"), ("path", {"from": "Ash Rd", "to": "Oak Av"}, "2 steps: @3 Ash Rd > @7 Elm Sq > @9 Oak Av")], "Ash Rd, Elm Sq, Oak Av"),
          ("A new W train starts today, with one brand-new station, Reed Pk. Northbound it runs Ash Rd, Reed Pk.", [("add_node", {"name": "Reed Pk"}, "added @12 Reed Pk"), ("link", {"from": "Ash Rd", "relation": "W northbound", "to": "Reed Pk"}, "linked @3 Ash Rd > W northbound > @12 Reed Pk")], "Done."),
          ("The W train has been cancelled.", [("unlink", {"from": "Ash Rd", "relation": "W northbound", "to": "Reed Pk"}, "unlinked @3 Ash Rd > W northbound > @12 Reed Pk")], "Done.")]
    keep = (W.HISTORY if g.get("splice") else TN.blocking(W.HISTORY)) if "chase" in wanted else []
    W.HISTORY = keep + [m for u, c, r in D_ if all(x[0] in wanted for x in c) for m in turn(u, [{"fn": a, "args": b, "result": d} for a, b, d in c], r)]
src = open(os.path.join(ROOT, "t8", "fw", "edit.py")).read()
assert src.count("MAX_CALLS, TURN, TOTAL = 6, 320, 1536") == 1
src = src.replace("MAX_CALLS, TURN, TOTAL = 6, 320, 1536", "MAX_CALLS, TURN, TOTAL = 12, 320, 3072")
NQ = "nq = len(AutoTokenizer.from_pretrained(X.MODEL))"
assert src.count(NQ) == 1
src = src.replace(NQ, "nq = 248077")                               # what len(AutoTokenizer) gave on Qwen 3.5 4B's own folder in the frozen runs: 248,070 tokens and 7 reserved names
sys.argv[0] = os.path.join(ROOT, "t8", "fw", "edit.py")
sys.path.insert(0, os.path.dirname(sys.argv[0]))
exec(compile(src, sys.argv[0], "exec"), {"__name__": "__main__", "__file__": sys.argv[0]})
