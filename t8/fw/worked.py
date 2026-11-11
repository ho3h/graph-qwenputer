"""The frozen flow's tool and worked turns (t8/REGISTRATION.md, step W; infer/run.py example7, responses in the machine's form, plus one turn for reopened). One place, read by edit.py and speed/fast.py."""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "host"))
import tools as HT  # noqa: E402

TOOLS = copy.deepcopy([t for t in HT.tools_for("base") if t["function"]["name"] == "chase"])
TOOLS[0]["function"]["parameters"]["properties"]["closed"] = {"type": "string", "description": "stations the user says can't be used right now for any reason (closed, shut, skipped, no service, out of service), separated by ';'. Leave this out if none are."}
TOOLS[0]["function"]["parameters"]["properties"]["reopened"] = {"type": "string", "description": "stations the user says can be used again, separated by ';'. Leave this out if none are."}


def _turn(u, args, line, reply):
    return [{"role": "user", "content": u}, {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "chase", "arguments": args}}]}, {"role": "tool", "content": line}, {"role": "assistant", "content": reply}]


_q = " One stop means the next station. At which station are you now? Answer with the station name only."
HISTORY = (_turn("Trains aren't stopping at Elm Sq this week. Start at Ash Rd station. Ride the K train 2 stops northbound." + _q, {"start": "Ash Rd", "legs": "K northbound 2", "closed": "Elm Sq"}, "closed @7 Elm Sq\n@9 Birch Av", "Birch Av")
           + _turn("Oak Av has a burst pipe and nobody can get in. Start at Birch Av station. Ride the K train 1 stop southbound." + _q, {"start": "Birch Av", "legs": "K southbound 1", "closed": "Oak Av"}, "closed @5 Oak Av\n@3 Ash Rd", "Ash Rd")
           + _turn("My sister lives near Pine St. Start at Ash Rd station. Ride the K train 1 stop northbound." + _q, {"start": "Ash Rd", "legs": "K northbound 1"}, "@7 Elm Sq", "Elm Sq")
           + _turn("Good news, Oak Av is running again. Start at Birch Av station. Ride the K train 1 stop southbound." + _q, {"start": "Birch Av", "legs": "K southbound 1", "reopened": "Oak Av"}, "reopened @5 Oak Av\n@5 Oak Av", "Oak Av"))
