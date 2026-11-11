#!/usr/bin/env python3
"""Query and edit a graph with the reference library. No dependencies and no model.

    python3 try.py path "Bedford Av" "WTC Cortlandt"
    python3 try.py --graph examples/team.graph.json path Ana Kofi
    printf 'close | 6 Av\\npath | Bedford Av | WTC Cortlandt\\n' | python3 try.py

Edits last for one session: pipe several lines, one call a line, arguments split by |.
"""
import argparse
import json
import os
import sys

os.environ.update(T8_R1="1", T8_R2="1")  # the rules the firmware runs: a shared name settled by the relation, add_node and one-station names
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "lib"), os.path.join(HERE, "t8", "fw"), os.path.join(HERE, "toolkit")]
import calls as C  # noqa: E402
import noun  # noqa: E402
import reflib  # noqa: E402

ok = True


def run(G, g, fn, vals):
    global ok
    if fn == "relations":
        return "\n".join(g["relations"])
    bad = C.problem(fn, vals)
    if bad:
        ok = False
        return bad.replace("Calls: ", "Calls: relations, ")
    return G.call(fn, dict(zip(C.ARGS[fn], vals)))


def load(path):
    try:
        g = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"Can't read {path}: {e}")
    err = [e for e in C.problems(g)[0] if "The firmware holds" not in e]   # try has no size limits
    if err:
        sys.exit("\n".join([f"{path} needs fixing first:"] + err[:20]))
    n = len(g["nodes"])
    g = C.filled(g)
    if n > 1024:
        print(f"Note: {n} nodes. The reference runs this, but the machine in the weights holds 1,024.", file=sys.stderr)
    return g


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--graph", default=os.path.join(HERE, "exam", "items", "nyc_b.graph.json"))
ap.add_argument("call", nargs="*", help="a call and its arguments; without one, reads calls from stdin")
a = ap.parse_args()
g = load(a.graph)
G = reflib.Graph(noun.with_noun(g))
if a.call:
    print(run(G, g, a.call[0], a.call[1:]))
elif sys.stdin.isatty():
    ap.print_help()
else:
    for line in sys.stdin:
        parts = [p.strip() for p in line.split("|")]
        if parts[0]:
            print(run(G, g, parts[0], parts[1:]))
sys.exit(0 if ok else 1)
