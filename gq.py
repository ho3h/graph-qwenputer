#!/usr/bin/env python3
"""The graph-qwenputer toolkit: build a graph, check it, query it, then run it in the model.

    python3 gq.py import examples/packages.csv -o packages.graph.json   make a graph from a CSV file
    python3 gq.py check packages.graph.json                             check the graph against the firmware's limits
    python3 gq.py try packages.graph.json path app libc                 query the graph with the reference library
    python3 gq.py sim packages.graph.json --model model path app libc   run the real firmware on the simulator, no GPU
    python3 gq.py ask packages.graph.json --model model "A question"    ask Qwen, with the graph-qwenputer in its layers
    python3 gq.py build --model model                                   rebuild the firmware after you edit it

import, check and try need only Python 3.9. sim, ask and build need Python 3.12 to 3.14, requirements.txt and Homebrew's LLVM. build also needs Homebrew's lld.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "toolkit"))
import calls as C  # noqa: E402

NYC = os.path.join(HERE, "exam", "items", "nyc_b.graph.json")
ENV = dict(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.path.join(HERE, "vendor", "qwenputer-riscv"), T8_NOUN="on", T8_WRITES="1", T8_R1="1", T8_R2="1", T8_R3="1", T8_R4="1", T8_R5="1", T8_R6="1")


def nfc(s):
    return unicodedata.normalize("NFC", s)


def graph_path(p):
    return NYC if p == "nyc" else p


def load(path):
    try:
        return json.load(open(graph_path(path), encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"Can't read {path}: {e}")


COLUMNS = {"from": "from", "source": "from", "src": "from", "relation": "relation", "rel": "relation", "type": "relation", "to": "to", "target": "to", "dst": "to", "weight": "weight"}


def header(row, name):
    """The first row's columns as {field: position} if every cell names a column, otherwise None."""
    fields = [COLUMNS.get(c.lower()) for c in row]
    if len(row) < 2 or None in fields:
        return None
    if len(set(fields)) != len(fields) or not {"from", "relation", "to"} <= set(fields):
        sys.exit(f"Row 1 of {name} looks like a header, and import needs one each of from, relation and to, with weight if you want one. Got {row}.")
    return dict(zip(fields, range(len(row))))


def size(g):
    """'13 nodes, 15 edges, 1 relation': a graph's size, with each noun in the right number."""
    return ", ".join(f"{len(g[k])} {w}{'' if len(g[k]) == 1 else 's'}" for k, w in (("nodes", "node"), ("edges", "edge"), ("relations", "relation")))


def cmd_import(a):
    inverse = {}
    for x in a.inverse:
        if x.count("=") != 1 or not all(x.split("=")):
            sys.exit(f"--inverse takes two relation names, A=B. Got {x!r}.")
        inverse[nfc(x.split("=")[0])] = nfc(x.split("=")[1])
    both = {nfc(x) for x in a.both}
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as f:
            raw = list(csv.reader(f))
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        sys.exit(f"Can't read {a.csv}: {e}")
    nodes, rels, edges, skipped, repeats = {}, {}, {}, [], 0
    node = lambda s: nodes.setdefault(nfc(s), len(nodes))
    rel = lambda s: rels.setdefault(nfc(s), len(rels))

    def put(key, w, i):
        if edges.get(key, w) != w:
            sys.exit(f"Row {i} of {a.csv}: {list(nodes)[key[0]]} > {list(rels)[key[1]]} > {list(nodes)[key[2]]} has weight {edges[key]} already, and this row gives {w}. Keep one.")
        edges[key] = w

    first, cols, seen_rows = True, None, set()
    for i, row in enumerate(raw, 1):
        row = [c.strip() for c in row]
        if not any(row):
            continue
        if row[0].startswith("#"):
            skipped.append(i)
            continue
        if first:
            first, cols = False, header(row, a.csv)
            if cols:
                continue
        if cols:                                                   # the header's order, back to from,relation,to,weight
            if any(row[len(cols):]):
                sys.exit(f"Row {i} of {a.csv} has more cells than the header. Got {row}.")
            row = [row[cols[k]] if k in cols and cols[k] < len(row) else "" for k in ("from", "relation", "to", "weight")]
        if not row[0]:
            sys.exit(f"Row {i} of {a.csv}: the first cell is empty. Got {row}.")
        if not any(row[1:]):                                       # a node with no edges yet
            node(row[0])
            continue
        if len(row) not in (3, 4) or not all(row[:3]):
            sys.exit(f"Row {i} of {a.csv}: use from,relation,to or from,relation,to,weight. Got {row}.")
        try:
            w = int(row[3]) if len(row) == 4 and row[3] else 1
        except ValueError:
            sys.exit(f"Row {i} of {a.csv}: the weight must be a whole number. Got {row[3]!r}.")
        x, r_, y = node(row[0]), rel(row[1]), node(row[2])
        repeats += (x, r_, y) in seen_rows
        seen_rows.add((x, r_, y))
        put((x, r_, y), w, i)
        if nfc(row[1]) in both:
            put((y, r_, x), w, i)
        if nfc(row[1]) in inverse:
            put((y, rel(inverse[nfc(row[1])]), x), w, i)
    for flag, names in (("--both", both), ("--inverse", inverse)):
        for r_ in names:
            if r_ not in rels:
                sys.exit(f"{flag} names {r_!r}, and no row of {a.csv} uses that relation. Its relations: {', '.join(rels) or 'none'}.")
    g = {"format": "x210-graph/1", "name": a.name or os.path.basename(a.csv).split(".")[0], "domain": a.domain,
         "nodes": [{"label": s, "prop": 0, "src": s} for s in nodes], "relations": list(rels),
         "edges": sorted([x, r_, y, w] for (x, r_, y), w in edges.items()), "splice": a.splice, "change": a.change, "meta": {}}
    err, warn = C.problems(g)
    if skipped:
        print(f"Note: skipped {len(skipped)} row(s) that start with #, which marks a comment: row {', '.join(map(str, skipped[:5]))}.")
    if repeats > 0:
        print(f"Note: {repeats} row(s) repeat an edge with the same weight. The graph keeps one.")
    if not edges:
        print("Note: 0 edges. import reads rows split by commas, so a file split by ; or tabs needs converting first.")
    for w_ in warn:
        print("Note:", w_)
    if err:
        sys.exit("\n".join(["Not written:"] + err[:20]))
    out = a.o or g["name"] + ".graph.json"
    try:
        json.dump(g, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except OSError as e:
        sys.exit(f"Can't write {out}: {e}")
    print(f"{out}: {size(g)}.")


def cmd_check(a):
    g = load(a.graph)
    err, warn = C.problems(g)
    for w in warn:
        print("Note:", w)
    for e in err[:20]:
        print("Problem:", e)
    if err:
        sys.exit(f"{a.graph} has {len(err)} problem(s).")
    print(f"{a.graph}: {size(g)}. The file is valid.", flush=True)
    if a.firmware:
        sys.exit(firmware(a, g_path=a.graph, calls=[]))
    print("To test the fit in the real firmware's memory: gq.py check --firmware --model DIR GRAPH")


def need_model(a):
    if not a.model:
        sys.exit("This command needs --model DIR. For sim and check --firmware, the three small files are enough:\n  hf download hopski/graph-qwenputer chipformer.json config.json tokenizer.json --local-dir model")
    for f in ("chipformer.json", "tokenizer.json", "config.json"):
        if not os.path.exists(os.path.join(a.model, f)):
            sys.exit(f"{a.model} has no {f}. Point --model at the model folder.")


def need_python(a, tools=()):
    """Plain words before a run would fail deep inside the simulator."""
    code = "import importlib.util as u, sys; sys.exit(2 if not (3, 12) <= sys.version_info[:2] <= (3, 14) else 0 if all(u.find_spec(m) for m in ('torch', 'numpy', 'tokenizers')) else 1)"
    try:
        c = subprocess.call([a.python, "-c", code])
    except OSError as e:
        sys.exit(f"Can't run {a.python}: {e}")
    if c == 2:
        sys.exit(f"This command needs Python 3.12, 3.13 or 3.14, and {a.python} is another version. The pinned torch has no build for Python 3.15. --python picks another.")
    if c:
        sys.exit(f"{a.python} can't find torch, numpy and tokenizers. Run: pip install -r requirements.txt. --python picks another Python.")
    for path, fix in ((os.environ.get("CHIP_CC") or "/opt/homebrew/opt/llvm/bin/clang", "brew install llvm, or set CHIP_CC to another clang"),) + tuple(tools):
        if not os.path.exists(path):
            sys.exit(f"This command needs {path}. Run: {fix}.")


def firmware(a, g_path, calls):
    need_model(a)
    need_python(a)
    env = dict(os.environ, TOK_CKPT=os.path.abspath(a.model), **ENV)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(calls, f)
    return subprocess.call([a.python, "-B", os.path.join(HERE, "t8", "fw", "tokrun.py"), os.path.join(HERE, "toolkit", "sim_run.py"), os.path.abspath(graph_path(g_path)), f.name], env=env)


def split_calls(a):
    if a.call:
        return [a.call]
    if sys.stdin.isatty():
        sys.exit("Give a call, such as: path A B. Or pipe several, one a line, with arguments split by |.")
    return [[p.strip() for p in line.split("|")] for line in sys.stdin if line.strip()]


def cmd_try(a):
    sys.exit(subprocess.call([sys.executable, os.path.join(HERE, "try.py"), "--graph", graph_path(a.graph)] + a.call))


def cmd_sim(a):
    err, _ = C.problems(load(a.graph))
    if err:
        sys.exit("\n".join(["Fix these first:"] + err[:20]))
    calls = split_calls(a)
    for c in calls:
        msg = C.problem(c[0], c[1:])
        if msg:
            sys.exit(msg)
    sys.exit(firmware(a, a.graph, calls))


def cmd_ask(a):
    g = load(a.graph)
    err, _ = C.problems(g)
    if err:
        sys.exit("\n".join(["Fix these first:"] + err[:20]))
    wanted, msg = C.tools_wanted(a.tools)
    if msg:
        sys.exit(msg)
    if a.examples:
        _, msg = C.read_examples(a.examples, wanted)
        if msg:
            sys.exit(msg)
    if not a.model:
        sys.exit("ask needs --model DIR, the whole model: hf download hopski/graph-qwenputer --local-dir model")
    need_python(a)
    cmd = [a.python, os.path.join(HERE, "run.py"), "--model", a.model, "--graph", graph_path(a.graph), "--python", a.python]
    if a.examples:
        cmd += ["--examples", a.examples]
    if a.tools:
        cmd += ["--tools", a.tools]
    if a.whole:
        cmd += ["--whole"]
    sys.exit(subprocess.call(cmd + a.turns))


def cmd_build(a):
    need_model(a)
    need_python(a, (("/opt/homebrew/opt/lld/bin/ld.lld", "brew install lld"),))
    env = dict(os.environ, TOK_CKPT=os.path.abspath(a.model), **ENV)
    p = subprocess.run([a.python, "-B", os.path.join(HERE, "t8", "fw", "gen.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        last = [ln for ln in p.stderr.splitlines() if ln.strip()][-1][:300]
        sys.exit(f"t8/fw/gen.py failed: {last}\nIf that is an AssertionError, a patch in gen.py looks for text you changed in fw/graphlib.c. docs/TOOLKIT.md lists the functions gen.py replaces.")
    code = "import os, fwb, hashlib\nif not os.path.isdir(fwb.X.MODEL): fwb.X.MODEL = os.environ['TOK_CKPT']\np = fwb.build(); print(p); print(hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16])"
    sys.exit(subprocess.call([a.python, "-B", "-c", code], env=env, cwd=os.path.join(HERE, "t8", "fw")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("import", help="make a graph from a CSV of from,relation,to[,weight]")
    p.add_argument("csv")
    p.add_argument("-o", help="the graph file to write")
    p.add_argument("--name")
    p.add_argument("--domain", default="custom")
    p.add_argument("--both", action="append", default=[], metavar="RELATION", help="this relation runs in both directions")
    p.add_argument("--inverse", action="append", default=[], metavar="A=B", help="for each edge in relation A, also add the reverse edge in relation B")
    p.add_argument("--splice", action="append", default=[], metavar="RELATION", help="a closed node can be passed along this relation; otherwise a closed node blocks")
    p.add_argument("--change", metavar="RELATION", help="the relation used to change between legs of a chase")
    p.set_defaults(fn=cmd_import)
    for name, fn, h in (("check", cmd_check, "check a graph against the firmware's limits"), ("try", cmd_try, "query with the reference library, no model"), ("sim", cmd_sim, "run the real firmware on the simulator, no GPU"), ("ask", cmd_ask, "ask Qwen with the graph-qwenputer in its layers")):
        p = sub.add_parser(name, help=h)
        p.add_argument("graph", help="a graph file, or nyc for New York")
        if name in ("check", "sim", "ask"):
            p.add_argument("--model", help="the model folder")
            p.add_argument("--python", default=sys.executable, help="a Python with requirements.txt installed")
        if name == "check":
            p.add_argument("--firmware", action="store_true", help="load the graph into the real firmware's memory")
        if name in ("try", "sim"):
            p.add_argument("call", nargs="*", help="a call and its arguments; without one, reads calls from stdin")
        if name == "ask":
            p.add_argument("--examples", help="your own worked turns, a JSON file; see docs/TOOLKIT.md")
            p.add_argument("--tools", help="the calls Qwen can make, separated by commas")
            p.add_argument("--whole", action="store_true", help="run the 11 added layers on the real weights too, about 60 machine tokens a second")
            p.add_argument("turns", nargs="+", help="each argument is one turn of one conversation")
        p.set_defaults(fn=fn)
    p = sub.add_parser("build", help="rebuild the firmware after you edit fw/graphlib.c or t8/fw/gen.py")
    p.add_argument("--model", help="the model folder")
    p.add_argument("--python", default=sys.executable)
    p.set_defaults(fn=cmd_build)
    a, rest = ap.parse_known_args()                                # Python before 3.12 hands a call written after --model to rest
    if a.cmd in ("try", "sim"):
        a.call = a.call + rest
    elif rest:
        ap.error(f"unrecognized arguments: {' '.join(rest)}")
    a.fn(a)


if __name__ == "__main__":
    main()
