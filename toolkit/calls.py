"""The calls the firmware answers and the graph file's optional fields, shared by gq.py, try.py and toolkit/sim_run.py."""
import json
import unicodedata

# The firmware's own limits: tok/boot_tok.py and fw/graphlib.c. exam/LIMITS.md has the measurements.
MAX_NODES, MAX_RELATIONS, MAX_LABEL, MAX_WEIGHT, MAX_NEW_NAME, EDGES_MEASURED = 1024, 64, 64, 65535, 31, 6880
ARGS = {
    "find": ["name", "has"], "follow": ["node", "relation", "steps"], "chase": ["start", "legs", "closed", "reopened"],
    "neighbours": ["node", "relation", "direction"], "path": ["from", "to"], "cheapest": ["from", "to"],
    "close": ["node"], "reopen": ["node"], "add_node": ["name"],
    "link": ["from", "relation", "to", "weight"], "unlink": ["from", "relation", "to"],
}
OPTIONAL = {"has", "closed", "reopened", "direction", "weight"}


def problem(fn, vals):
    """A plain sentence when these arguments can't make the call, otherwise None."""
    if fn not in ARGS:
        return f"Unknown call {fn}. Calls: {', '.join(ARGS)}."
    need = [p for p in ARGS[fn] if p not in OPTIONAL]
    if not len(need) <= len(vals) <= len(ARGS[fn]):
        return f"{fn} takes {', '.join(need)}" + "".join(f", optional {p}" for p in ARGS[fn] if p in OPTIONAL) + f". Got {len(vals)} argument(s)."
    return None


def unreadable(s):
    """Why the firmware can't read this name, if so: control characters, or text that isn't valid Unicode."""
    if any(ord(ch) < 32 for ch in s):
        return "contains a control character."
    try:
        s.encode()
    except UnicodeEncodeError:
        return "isn't valid Unicode."
    return ""


def problems(g):
    """(errors, warnings) against the file format and the firmware's limits."""
    err, warn = [], []
    if not isinstance(g, dict) or any(k not in g for k in ("nodes", "relations", "edges")):
        return ["The file needs nodes, relations and edges. See docs/TOOLKIT.md."], []
    for k in ("nodes", "relations", "edges"):
        if not isinstance(g[k], list):
            return [f"{k} must be a list. See docs/TOOLKIT.md."], []
    if g.get("format", "x210-graph/1") != "x210-graph/1":
        err.append(f"format is {g['format']!r}. This toolkit reads x210-graph/1.")
    if not isinstance(g.get("splice", []), list):
        return [f"splice must be a list of relation names."], []
    labels = [n.get("label") if isinstance(n, dict) else None for n in g["nodes"]]
    rels = g["relations"]
    if not all(isinstance(x, str) for x in rels):
        return ["Each relation must be a name."], []
    n, r = len(labels), len(rels)
    if n > MAX_NODES:
        err.append(f"{n} nodes. The firmware holds {MAX_NODES}.")
    if r > MAX_RELATIONS:
        err.append(f"{r} relations. The firmware holds {MAX_RELATIONS}.")
    if len(set(rels)) != r:
        err.append("Two relations have the same name.")
    for rel in rels:
        if not rel.strip():
            err.append(f"Relation {rel!r} needs a name.")
        elif unreadable(rel):
            err.append(f"Relation {rel!r} {unreadable(rel)}")
        elif ";" in rel:
            err.append(f"Relation {rel!r} contains ';', which separates the legs of a chase.")
    for i, lab in enumerate(labels):
        if not isinstance(lab, str) or not lab.strip():
            err.append(f"Node {i} needs a label.")
            continue
        if unreadable(lab):
            err.append(f"Label {lab!r} {unreadable(lab)}")
            continue
        prop = g["nodes"][i].get("prop", 0)
        if not (isinstance(prop, int) and 0 <= prop <= 65535):
            err.append(f"Node {lab!r} has prop {prop!r}. It must be a whole number from 0 to 65,535.")
        if unicodedata.normalize("NFC", lab) != lab:
            err.append(f"Label {lab!r} is not in NFC form. gq.py import fixes this.")
        if len(lab.encode()) > MAX_LABEL:
            err.append(f"Label {lab!r} is {len(lab.encode())} bytes. The firmware holds {MAX_LABEL}.")
        if lab.startswith("@"):
            err.append(f"Label {lab!r} starts with @, which marks a handle in a query.")
    seen = set()
    for e in g["edges"]:
        if not (isinstance(e, list) and len(e) == 4 and all(isinstance(x, int) for x in e)):
            err.append(f"Edge {e} must be [from, relation, to, weight], four whole numbers.")
            continue
        a, rel, b, w = e
        if not (0 <= a < n and 0 <= rel < r and 0 <= b < n):
            err.append(f"Edge {e} points outside the nodes or relations list.")
            continue
        if not 0 <= w <= MAX_WEIGHT:
            err.append(f"Edge {e} has weight {w}. The firmware holds 0 to {MAX_WEIGHT}.")
        if (a, rel, b) in seen:
            err.append(f"Edge {labels[a]} > {rels[rel]} > {labels[b]} appears twice.")
        seen.add((a, rel, b))
    for rel in g.get("splice", []):
        if rel not in rels:
            err.append(f"splice names {rel!r}, which is not a relation.")
    if g.get("change") and g["change"] not in rels:
        err.append(f"change names {g['change']!r}, which is not a relation.")
    if err:
        return err, warn
    if len(g["edges"]) > EDGES_MEASURED:
        warn.append(f"{len(g['edges'])} edges. The measured fit is about {EDGES_MEASURED} with 9-byte names, and long names lower it. Run: gq.py check --firmware.")
    shared = sorted({lab for lab in labels if labels.count(lab) > 1})
    if shared:
        warn.append(f"{len(shared)} names are shared, such as {shared[0]!r}. A query by that name gets AMBIGUOUS unless a relation or a transfer settles it.")
    return err, warn


def filled(g):
    """A hand-written graph needs only nodes, relations and edges. This fills in the fields the machines read."""
    g = dict(g)
    for k, v in (("format", "x210-graph/1"), ("name", "graph"), ("domain", "custom"), ("splice", []), ("change", None), ("meta", {})):
        g.setdefault(k, v)
    g["nodes"] = [{"prop": 0, "src": n["label"], **n} for n in g["nodes"]]
    return g


DEFAULT_TOOLS = "chase,neighbours,path,close,reopen,add_node,link,unlink"


def tools_wanted(text):
    """The names in --tools, and a plain sentence if one is unknown."""
    wanted = [x.strip() for x in (text or DEFAULT_TOOLS).split(",") if x.strip()]
    for k in wanted:
        if k not in ARGS:
            return wanted, f"Unknown tool {k}. Tools: {', '.join(ARGS)}."
    return wanted, None if wanted else "--tools names no tools."


def read_examples(path, wanted):
    """Your worked turns, and a plain sentence if a turn can't work."""
    try:
        turns = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"Can't read {path}: {e}"
    for i, t in enumerate(turns if isinstance(turns, list) else [None], 1):
        if not isinstance(t, dict) or any(k not in t for k in ("user", "calls", "reply")):
            return None, f"Example {i} of {path} needs user, calls and reply. See docs/TOOLKIT.md."
        if not isinstance(t["user"], str) or not isinstance(t["reply"], str) or not isinstance(t["calls"], list):
            return None, f"Example {i} of {path}: user and reply are text, and calls is a list."
        for c in t["calls"]:
            if not isinstance(c, dict) or any(k not in c for k in ("fn", "args", "result")):
                return None, f"Example {i} of {path}: each call needs fn, args and result."
            if not isinstance(c["args"], dict) or not isinstance(c["result"], str):
                return None, f"Example {i} of {path}: a call's args is an object, and its result is text."
            if c["fn"] not in wanted:
                return None, f"Example {i} of {path} calls {c['fn']}, and the tools on offer are {', '.join(wanted)}."
            have, need = set(c["args"]), {p for p in ARGS[c["fn"]] if p not in OPTIONAL}
            if have - set(ARGS[c["fn"]]) or need - have:
                return None, f"Example {i} of {path}: {c['fn']} takes {', '.join(ARGS[c['fn']])}, and requires {', '.join(sorted(need))}. Got {', '.join(c['args'])}."
    return turns, None
