"""Shared helpers for the X2.10 data builders: canonical x210-graph/1 assembly, deterministic JSON, answers from
reflib, and the transit conversion used by the cities, NYC and its variants.

Run every builder with the read-only qwenputer venv and no bytecode:
    PYTHONDONTWRITEBYTECODE=1 <venv>/bin/python -B data/build/<builder>.py
"""
import hashlib
import json
import os
import re
import signal
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
X210 = os.path.dirname(DATA)
REPO = os.path.dirname(os.path.dirname(X210))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(X210, "lib"))
import reflib  # noqa: E402

HANDLE = re.compile(r"(?:^|(?<=[\s:>|]))@(\d+)(?= |$)", re.M)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def clean_label(s):
    return unicodedata.normalize("NFC", s).strip()


NOUN_BY_DOMAIN = {"transit": "station"}                         # SPEC 1: every other domain has no noun for a node
WRITE_NOUN = False                                              # SPEC 1. Off until the streams reading today's graph files finish: turning it on changes every file's hash


def noun_for(domain):
    return NOUN_BY_DOMAIN.get(domain)


def make_graph(name, domain, nodes, relations, edges, splice=(), change=None, meta=None):
    """nodes: list of dicts {label, src, prop}; edges: [(node_index, relation_name, node_index, weight)] in the
    caller's node indexing. Returns (graph, old->new handle map). Nodes are ordered by (label, src); edges sorted by
    (from, rel, to). Duplicate (from, rel, to) triples raise."""
    for n in nodes:
        assert n["label"] == clean_label(n["label"]), ("label not NFC/stripped", n["label"])
        assert 0 <= n.get("prop", 0) <= 65535
        assert "@" not in n["label"], ("label contains @", n["label"])
    order = sorted(range(len(nodes)), key=lambda i: (nodes[i]["label"], nodes[i]["src"]))
    assert len({(nodes[i]["label"], nodes[i]["src"]) for i in order}) == len(nodes), "duplicate (label, src)"
    new = {old: h for h, old in enumerate(order)}
    rix = {r: i for i, r in enumerate(relations)}
    assert len(rix) == len(relations), "duplicate relation name"
    out, seen = [], set()
    for a, r, b, w in edges:
        assert 0 <= w <= 65535
        e = (new[a], rix[r], new[b])
        assert e not in seen, ("duplicate edge", e)
        seen.add(e)
        out.append([e[0], e[1], e[2], int(w)])
    out.sort()
    g = {"format": "x210-graph/1", "name": name, "domain": domain,
         "nodes": [{"label": nodes[i]["label"], "prop": int(nodes[i].get("prop", 0)), "src": str(nodes[i]["src"])}
                   for i in order],
         "relations": list(relations), "edges": out, "splice": list(splice), "change": change, "meta": meta or {}}
    if WRITE_NOUN:
        g["noun"] = noun_for(domain)
    return g, new


def dumps(obj, list_keys=("nodes", "edges", "questions", "edits", "items")):
    """Deterministic JSON: top-level keys one per line, and one element per line for the big lists."""
    lines = ["{"]
    keys = list(obj)
    for i, k in enumerate(keys):
        v = obj[k]
        comma = "," if i < len(keys) - 1 else ""
        if k in list_keys and isinstance(v, list) and v:
            lines.append(f" {json.dumps(k)}: [")
            for j, x in enumerate(v):
                lines.append("  " + json.dumps(x, ensure_ascii=False, separators=(", ", ": "))
                             + ("," if j < len(v) - 1 else ""))
            lines.append(" ]" + comma)
        else:
            lines.append(f" {json.dumps(k)}: " + json.dumps(v, ensure_ascii=False, separators=(", ", ": ")) + comma)
    lines.append("}")
    return "\n".join(lines) + "\n"


def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(dumps(obj))
    return sha256_file(path)


def handles(text):
    """The handles in a result text, in order (labels never contain '@')."""
    return [int(m) for m in HANDLE.findall(text)]


class RefError(Exception):
    """reflib raised or did not return within the time limit (a reflib bug, never a data answer)."""


def _alarm(*_):
    raise TimeoutError("reflib call exceeded the time limit")


def run(G, call, setup=(), limit=1.0):
    """Answer one question on a fresh state of G: run the setup calls in order, then the call. Returns
    (answer_text, setup results). The state (closed set and any link/unlink edits) is reset afterwards. A reflib exception or a call that runs past
    `limit` seconds raises RefError."""
    G.closed = set()
    edits = any(c["fn"] in ("link", "unlink") for c in [*setup, call])
    if edits:
        saved = ({k: list(v) for k, v in G.out.items()}, {k: list(v) for k, v in G.inn.items()})
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, limit)
    try:
        res = [G.call(c["fn"], c["args"]) for c in setup]
        ans = G.call(call["fn"], call["args"])
    except Exception as e:  # noqa: BLE001
        raise RefError(f"{type(e).__name__}: {e}") from None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
        G.closed = set()
        if edits:
            G.out, G.inn = saved
    return ans, res


def question(G, qid, kind, text, call, setup=(), **extra):
    ans, res = run(G, call, setup)
    q = {"id": qid, "kind": kind, "text": text}
    if setup:
        q["setup"] = [{**c, "result": r} for c, r in zip(setup, res)]
    q["call"] = call
    q["answer"] = handles(ans)
    q["answer_text"] = ans
    q.update(extra)
    return q


def questions_file(graph_name, graph_sha, qs):
    return {"format": "x210-questions/1", "graph": graph_name, "graph_sha256": graph_sha, "questions": qs}


def outcome(text):
    """A short class name for a result text (for counts only)."""
    t = text.split("\n")[0]
    t = re.sub(r"^leg \d+: ", "", t)
    for p in ("AMBIGUOUS", "NONE", "MULTI", "END", "NOCHANGE", "NOPATH", "CLOSED", "NORELATION", "BADARG",
              "OVERFLOW", "NOFUNCTION", "already closed", "not closed", "closed", "reopened", "already linked",
              "not linked", "linked", "unlinked", "cost", "FULL"):
        if t.startswith(p):
            return p
    if re.match(r"\d+ steps:", t):
        return "path"
    return "OK"


# ---------------------------------------------------------------- transit (X2.7 / X2.8 station format)
DIRS = {"N": "northbound", "S": "southbound"}


def transit_graph(src, name, meta):
    """X2.7-format {stations: {id: {name, complex}}, edges: [{from, route, dir, to}]} -> x210 graph.
    Relations: '<route> northbound|southbound' (routes in sorted order) plus 'transfer' between every ordered pair
    of distinct stations of one complex. Route edges weigh 1 (one stop), transfers 0."""
    S = src["stations"]
    ids = sorted(S)
    idx = {s: i for i, s in enumerate(ids)}
    nodes = [{"label": clean_label(S[s]["name"]), "src": s, "prop": 0} for s in ids]
    routes = sorted({e["route"] for e in src["edges"]})
    rels = [f"{r} {DIRS[d]}" for r in routes for d in ("N", "S")] + ["transfer"]
    edges = [(idx[e["from"]], f"{e['route']} {DIRS[e['dir']]}", idx[e["to"]], 1) for e in src["edges"]]
    comp = {}
    for s in ids:
        comp.setdefault(S[s]["complex"], []).append(s)
    for c in sorted(comp):
        for a in comp[c]:
            for b in comp[c]:
                if a != b:
                    edges.append((idx[a], "transfer", idx[b], 0))
    used = {r for _, r, _, _ in edges}
    rels = [r for r in rels if r in used or r == "transfer"]
    g, new = make_graph(name, "transit", nodes, rels, edges, splice=[r for r in rels if r != "transfer"],
                        change="transfer", meta=meta)
    return g, {s: new[idx[s]] for s in ids}


def legs_arg(legs):
    return "; ".join(f"{r} {DIRS[d]} {k}" for r, d, k in legs)


def transit_questions(G, chases, hmap):
    """Convert X2.7-style chase questions into chase calls. hmap: station id -> handle (via make_graph's map).
    Returns (questions, mismatches)."""
    qs, bad = [], []
    for q in chases:
        call = {"fn": "chase", "args": {"start": f"@{hmap[q['start']]}", "legs": legs_arg(q["legs"])}}
        orig = hmap[q["answer"]]
        x = question(G, len(qs), "chase", q["text"], call, orig_id=q["id"], orig_kind=q["kind"], orig_answer=orig)
        if x["answer"] != [orig] or outcome(x["answer_text"]) != "OK":
            bad.append({"orig_id": q["id"], "orig_kind": q["kind"], "call": call, "orig_answer": f"@{orig} "
                        + G.labels[orig], "reflib": x["answer_text"]})
        qs.append(x)
    return qs, bad
