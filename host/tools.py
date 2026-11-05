"""The tool contract as Qwen sees it (SPEC.md section 3), and the exact bytes around each tool response (section 6).

Shared by the host baseline and, later, the circuit: the schema, the system prompt and the wrapping must not differ
between them, so they live here and nowhere else.
"""

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from reflib import Graph  # noqa: E402


def _fn(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}


NODE = "a node: its handle such as @12, or its exact name"
REL = "a relation name, exactly as listed"

TOOLS = [
    _fn("find", "Find a node by name. Returns '@handle name', or AMBIGUOUS with every match, or NONE.",
        {"name": {"type": "string", "description": "the node's exact name"},
         "has": {"type": "string", "description": "optional: only nodes with an outgoing edge in this relation"}},
        ["name"]),
    _fn("follow", "Take a relation's outgoing edge a number of times. Returns the node reached, or MULTI (more than "
                  "one way on) or END (no way on) with where it stopped.",
        {"node": {"type": "string", "description": "the start " + NODE[2:]},
         "relation": {"type": "string", "description": REL},
         "steps": {"type": "string", "description": "how many edges to take, 1 to 255"}},
        ["node", "relation", "steps"]),
    _fn("chase", "Follow several legs in turn ('relation n; relation n; ...', 1 to 16 legs). Before each leg after "
                 "the first it changes once along the change relation if the current node has no edge in the leg's "
                 "relation. Returns the node reached, or the first failing leg's line.",
        {"start": {"type": "string", "description": "the start " + NODE[2:]},
         "legs": {"type": "string", "description": "legs such as 'A northbound 3; 1 southbound 2'"}},
        ["start", "legs"]),
    _fn("neighbours", "The nodes one edge away in a relation, one '@handle name' per line, or NONE.",
        {"node": {"type": "string", "description": NODE},
         "relation": {"type": "string", "description": REL},
         "direction": {"type": "string", "description": "optional: 'out' (default) or 'in'"}},
        ["node", "relation"]),
    _fn("path", "The route with the fewest edges, over all relations: 'k steps: @h0 name > ... > @hk name', or NOPATH.",
        {"from": {"type": "string", "description": "the start " + NODE[2:]},
         "to": {"type": "string", "description": "the end " + NODE[2:]}},
        ["from", "to"]),
    _fn("cheapest", "The route with the lowest total weight: 'cost c: @h0 name > ... > @hk name', or NOPATH.",
        {"from": {"type": "string", "description": "the start " + NODE[2:]},
         "to": {"type": "string", "description": "the end " + NODE[2:]}},
        ["from", "to"]),
    _fn("close", "Close a node: searches avoid it until it is reopened. Returns 'closed @handle name'.",
        {"node": {"type": "string", "description": NODE}}, ["node"]),
    _fn("reopen", "Reopen a closed node. Returns 'reopened @handle name'.",
        {"node": {"type": "string", "description": NODE}}, ["node"]),
    _fn("link", "Add an edge from one node to another in a relation. Returns 'linked @a name > relation > @b name'.",
        {"from": {"type": "string", "description": "the start " + NODE[2:]},
         "relation": {"type": "string", "description": REL},
         "to": {"type": "string", "description": "the end " + NODE[2:]},
         "weight": {"type": "string", "description": "optional: the edge's weight, 0 to 65535 (default 0)"}},
        ["from", "relation", "to"]),
    _fn("unlink", "Remove the edge from one node to another in a relation. "
                  "Returns 'unlinked @a name > relation > @b name'.",
        {"from": {"type": "string", "description": "the start " + NODE[2:]},
         "relation": {"type": "string", "description": REL},
         "to": {"type": "string", "description": "the end " + NODE[2:]}},
        ["from", "relation", "to"]),
]

# The dev arm "clear": the same schema, with node arguments described by the lead's generic wording.
CLEAR_NODE = "use the exact name or the @handle"


def tools_for(arm: str = "base") -> list:
    if arm == "base":
        return TOOLS
    assert arm == "clear", arm
    out = copy.deepcopy(TOOLS)
    for t in out:
        fn = t["function"]
        for p in NODE_PARAMS[fn["name"]]:
            fn["parameters"]["properties"][p]["description"] = CLEAR_NODE
    return out


# Which parameters name a node and which a relation (for the spelling report). chase's legs hold relations too.
NODE_PARAMS = {"find": ["name"], "follow": ["node"], "chase": ["start"], "neighbours": ["node"],
               "path": ["from", "to"], "cheapest": ["from", "to"], "close": ["node"], "reopen": ["node"],
               "link": ["from", "to"], "unlink": ["from", "to"]}
REL_PARAMS = {"find": ["has"], "follow": ["relation"], "neighbours": ["relation"], "link": ["relation"],
              "unlink": ["relation"]}


def system_prompt(g: dict) -> str:
    """The system message: the graph's name and its relations (never its nodes). Shared with the circuit runs."""
    rels = "; ".join(g["relations"])
    s = (f"You answer questions about the graph \"{g['name']}\" with the graph tools. "
         f"Its relations are: {rels}.")
    if g.get("change"):
        s += f" Changing between lines uses the relation \"{g['change']}\"."
    s += " A node argument is a handle such as @12 or a node's exact name."
    return s


def tools_sha256(arm: str = "base") -> str:
    return hashlib.sha256(json.dumps(tools_for(arm), sort_keys=True).encode()).hexdigest()


# --- SPEC section 6: the bytes of a tool response -------------------------------------------------------------
def response_body(result: str) -> str:
    """What the machine prints: '<tool_response>\\n' + result lines + '\\n</tool_response>'."""
    return "<tool_response>\n" + result + "\n</tool_response>"


def forced_text(result: str, think: bool) -> str:
    """Everything after Qwen's '</tool_call>' up to its next own token, in the chat template's exact format:
    end of the assistant turn, the tool turn (rendered as a user turn), and the next generation prompt."""
    gen = "<think>\n" if think else "<think>\n\n</think>\n\n"
    return "<|im_end|>\n<|im_start|>user\n" + response_body(result) + "<|im_end|>\n<|im_start|>assistant\n" + gen


# --- Qwen 3.5's native tool-call syntax ---------------------------------------------------------------------
FUNC_RE = re.compile(r"<function=([^>\n]*)>")
PARAM_RE = re.compile(r"<parameter=([^>\n]*)>(.*?)</parameter>", re.S)


def parse_call(text: str) -> dict:
    """Parse the text between '<tool_call>' and '</tool_call>'.

    The template writes '<parameter=NAME>\\nVALUE\\n</parameter>'. `raw` keeps each value exactly as written;
    `args` drops exactly one leading and one trailing newline (the template's own), as Qwen's reference parser
    does, and nothing else, so spelling variants reach the tool untouched."""
    out = {"fn": None, "args": {}, "raw": {}, "error": None}
    m = FUNC_RE.search(text)
    if not m:
        out["error"] = "no <function=...>"
        return out
    out["fn"] = m.group(1)
    body = text[m.end():]
    end = body.find("</function>")
    if end < 0:
        out["error"] = "no </function>"
    else:
        body = body[:end]
    for name, val in PARAM_RE.findall(body):
        v = val[1:] if val.startswith("\n") else val
        v = v[:-1] if v.endswith("\n") else v
        if name in out["args"]:
            out["error"] = f"repeated parameter {name}"
        out["raw"][name] = val
        out["args"][name] = v
    return out


def answer_call(graph: Graph, call: dict) -> str:
    """The tool's result text for a parsed call. A call with no function name answers NOFUNCTION (empty name)."""
    if call["fn"] is None:
        return "NOFUNCTION "
    return graph.call(call["fn"], call["args"])
