#!/usr/bin/env python3
"""The toolkit's tests. python3 toolkit/test_toolkit.py needs only Python 3.9. Add --model DIR to run the real firmware too, with requirements.txt installed. Add --build to rebuild the firmware as well, which needs Homebrew's lld; the frozen firmware is put back afterwards."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GQ = os.path.join(ROOT, "gq.py")
model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else None
tmp = tempfile.mkdtemp(prefix="gq-test-")
fails = checks = 0


def run(*a, stdin=None):
    p = subprocess.run([sys.executable, GQ, *a], capture_output=True, text=True, input=stdin, cwd=ROOT)
    return p.returncode, p.stdout + p.stderr


def ok(cond, what, out=""):
    global fails, checks
    checks += 1
    if not cond:
        fails += 1
        print("FAIL", what, "\n", out[-600:])


def csv_file(name, text):
    p = os.path.join(tmp, name)
    open(p, "w", encoding="utf-8").write(text)
    return p


def graph(name):
    return os.path.join(tmp, name + ".graph.json")


# Import and query the examples.
c, o = run("import", "examples/packages.csv", "-o", graph("packages"))
ok(c == 0 and "13 nodes, 15 edges, 1 relation." in o, "import packages", o)
c, o = run("check", graph("packages"))
ok(c == 0 and "valid" in o, "check packages", o)
c, o = run("try", graph("packages"), "path", "app", "libc")
ok(c == 0 and o.strip() == "4 steps: @0 app > @2 auth > @5 crypto > @9 bignum > @12 libc", "path", o)
c, o = run("try", graph("packages"), "neighbours", "regex", "depends_on", "in")
ok(c == 0 and "router" in o and "templates" in o, "neighbours in", o)
c, o = run("import", "examples/flights.csv", "--both", "flight", "-o", graph("flights"))
ok(c == 0 and "8 nodes, 18 edges" in o, "import flights both ways", o)
c, o = run("try", graph("flights"), stdin="cheapest | Lisbon | Warsaw\nclose | Paris\ncheapest | Lisbon | Warsaw\nreopen | Paris\ncheapest | Lisbon | Warsaw\n")
L = o.strip().split("\n")
ok(c == 0 and L[0].startswith("cost 250") and L[2].startswith("cost 400") and L[4] == L[0], "a closure moves the route and reopening returns it", o)
# A closed node blocks unless the relation is listed as splice.
line = csv_file("line.csv", "A,next,B\nB,next,C\n")
run("import", line, "-o", graph("block"))
run("import", line, "--splice", "next", "-o", graph("splice"))
_, o = run("try", graph("block"), stdin="close | B\npath | A | C\n")
ok(o.strip().endswith("NOPATH"), "a closed node blocks", o)
_, o = run("try", graph("splice"), stdin="close | B\npath | A | C\n")
ok("@0 A > @2 C" in o, "splice runs through a closed node", o)
# Writes, unicode and inverse relations.
c, o = run("import", csv_file("u.csv", "Zoë,knows,東京\n東京,knows,Ana Maria\n"), "--inverse", "knows=known_by", "-o", graph("u"))
ok(c == 0 and "2 relations" in o, "inverse relation", o)
_, o = run("try", graph("u"), "path", "Ana Maria", "Zoë")
ok("2 steps" in o, "inverse edges and non-English names route", o)
_, o = run("try", graph("u"), stdin="add_node | Mira\nlink | Mira | knows | Zoë\npath | Mira | Ana Maria\nunlink | Mira | knows | Zoë\npath | Mira | Ana Maria\n")
L = o.strip().split("\n")
ok(L[2].startswith("3 steps") and L[-1] == "NOPATH", "add, link, unlink", o)
# Files the firmware would refuse, each refused with a plain message.
bad = {"many_nodes": {"nodes": [{"label": f"N{i}"} for i in range(1025)], "relations": ["r"], "edges": []},
       "many_rels": {"nodes": [{"label": "A"}], "relations": [f"r{i}" for i in range(65)], "edges": []},
       "long_label": {"nodes": [{"label": "A" * 65}], "relations": ["r"], "edges": []},
       "dup_edge": {"nodes": [{"label": "A"}, {"label": "B"}], "relations": ["r"], "edges": [[0, 0, 1, 1], [0, 0, 1, 2]]},
       "weight": {"nodes": [{"label": "A"}, {"label": "B"}], "relations": ["r"], "edges": [[0, 0, 1, 70000]]},
       "range": {"nodes": [{"label": "A"}], "relations": ["r"], "edges": [[0, 0, 5, 1]]},
       "semicolon": {"nodes": [{"label": "A"}], "relations": ["a;b"], "edges": []},
       "handle": {"nodes": [{"label": "@7"}], "relations": ["r"], "edges": []},
       "missing": {"nodes": []}}
for name, g in bad.items():
    p = os.path.join(tmp, name + ".json")
    json.dump(g, open(p, "w"))
    c, o = run("check", p)
    ok(c != 0 and "Traceback" not in o and ("Problem" in o or "needs" in o), f"check refuses {name}", o)
c, o = run("import", csv_file("bad.csv", "A,next\n"), "-o", graph("bad"))
ok(c != 0 and "Row 1" in o and "Traceback" not in o, "import names the bad row", o)
c, o = run("import", csv_file("bad2.csv", "A,next,B,heavy\n"), "-o", graph("bad"))
ok(c != 0 and "whole number" in o and "Traceback" not in o, "import names the bad weight", o)
c, o = run("check", os.path.join(tmp, "nothing.json"))
ok(c != 0 and "Can't read" in o, "a missing file", o)
c, o = run("try", graph("packages"), "nosuchcall", "x")
ok(c != 0 and "Unknown call" in o, "an unknown call", o)
c, o = run("sim", graph("packages"), "path", "app", "libc")
ok(c != 0 and "--model" in o and "Traceback" not in o, "sim explains that it needs the model folder", o)
c, o = run("check", "nyc")
ok(c == 0 and "496 nodes, 1761 edges" in o and "shared" in o, "New York by name", o)
# Messy files: each one gets a plain message or a note, never a silent change.
c, o = run("import", csv_file("hdr.csv", "From,Relation,To\nA,next,B\n"), "-o", graph("hdr"))
ok(c == 0 and "2 nodes, 1 edge," in o, "a capitalised header row is a header", o)
c, o = run("import", csv_file("order.csv", "from,to,relation\nA,B,next\n"), "-o", graph("order"))
_, o2 = run("try", graph("order"), "neighbours", "A", "next")
ok(c == 0 and "2 nodes, 1 edge, 1 relation." in o and "@1 B" in o2, "a header in another order sets the columns", o + o2)
c, o = run("import", csv_file("srct.csv", "source,target,relation,weight\nA,B,next,5\n"), "-o", graph("srct"))
ok(c == 0 and "2 nodes, 1 edge, 1 relation." in o and '"next"' in open(graph("srct"), encoding="utf-8").read() and "5" in open(graph("srct"), encoding="utf-8").read(), "source, target and weight headers", o)
c, o = run("import", csv_file("norel.csv", "source,target,weight\nA,B,5\n"), "-o", graph("x"))
ok(c != 0 and "looks like a header" in o, "a header with no relation is refused", o)
c, o = run("import", csv_file("bothrep.csv", "A,next,B\nA,next,B\n"), "--both", "next", "-o", graph("x"))
ok(c == 0 and "1 row(s) repeat" in o, "--both still reports a repeated row", o)
c, o = run("import", csv_file("empty1.csv", ",knows,B\n"), "-o", graph("x"))
ok(c != 0 and "first cell is empty" in o and "Traceback" not in o, "an empty first cell is refused", o)
c, o = run("import", csv_file("hash.csv", "#1 Dad,parent_of,Kim\nA,next,B\n"), "-o", graph("x"))
ok(c == 0 and "skipped 1" in o and "2 nodes" in o, "a skipped comment row is reported", o)
c, o = run("import", csv_file("w.csv", "A,next,B,5\nA,next,B,7\n"), "-o", graph("x"))
ok(c != 0 and "weight 5 already" in o, "two weights for one edge are refused", o)
c, o = run("import", csv_file("same.csv", "A,next,B,5\nA,next,B,5\n"), "-o", graph("x"))
ok(c == 0 and "1 row(s) repeat" in o and "1 edge," in o, "a repeated edge is reported", o)
c, o = run("import", line, "--both", "nxet", "-o", graph("x"))
ok(c != 0 and "--both names 'nxet'" in o, "a typo in --both is refused", o)
c, o = run("import", line, "--inverse", "nxet=back", "-o", graph("x"))
ok(c != 0 and "--inverse names 'nxet'" in o, "a typo in --inverse is refused", o)
c, o = run("import", line, "--inverse", "nope", "-o", graph("x"))
ok(c != 0 and "A=B" in o and "Traceback" not in o, "a malformed --inverse is refused", o)
c, o = run("import", csv_file("semi.csv", "A;next;B\nB;next;C\n"), "-o", graph("x"))
ok(c == 0 and "0 edges" in o and "Note" in o, "a file split by semicolons gets a note", o)
c, o = run("import", os.path.join(tmp, "nothing.csv"), "-o", graph("x"))
ok(c != 0 and "Can't read" in o and "Traceback" not in o, "a missing CSV", o)
open(os.path.join(tmp, "latin.csv"), "wb").write(b"Zo\xeb,knows,Ana\n")
c, o = run("import", os.path.join(tmp, "latin.csv"), "-o", graph("x"))
ok(c != 0 and "Can't read" in o and "Traceback" not in o, "a file that isn't UTF-8", o)
c, o = run("import", line, "-o", os.path.join(tmp, "no", "such", "dir.json"))
ok(c != 0 and "Can't write" in o and "Traceback" not in o, "an output path that can't be written", o)
c, o = run("import", csv_file("node.csv", "Solo,,\nA,next,B\n"), "-o", graph("x"))
ok(c == 0 and "3 nodes, 1 edge," in o, "a row with one name and spare commas is a node", o)
for name, g in {"nodes_number": {"nodes": 5, "relations": [], "edges": []}, "relation_list": {"nodes": [], "relations": [["a"]], "edges": []}, "splice_number": {"nodes": [], "relations": [], "edges": [], "splice": 5}, "format": {"format": "other", "nodes": [], "relations": [], "edges": []}}.items():
    p = os.path.join(tmp, name + ".json")
    json.dump(g, open(p, "w"))
    c, o = run("check", p)
    ok(c != 0 and "Traceback" not in o, f"check refuses {name}", o)
for name, g in {"format2": {"format": "x210-graph/2", "nodes": [], "relations": [], "edges": []}, "rel_list": {"nodes": [], "relations": [["a"]], "edges": []}, "change3": {"nodes": [], "relations": [], "edges": [], "change": 3}, "splice_none": {"nodes": [], "relations": [], "edges": [], "splice": ["nosuch"]}}.items():
    p = os.path.join(tmp, name + ".json")
    json.dump(g, open(p, "w"))
    c, o = run("try", p, "relations")
    ok(c != 0 and "Traceback" not in o, f"try refuses {name}", o)
for name, g in {"prop": {"nodes": [{"label": "A", "prop": 70000}], "relations": [], "edges": []}, "nul": {"nodes": [{"label": "A"}], "relations": ["a\0b"], "edges": []}, "surrogate": {"nodes": [{"label": "A\ud800"}], "relations": [], "edges": []}}.items():
    p = os.path.join(tmp, name + ".json")
    json.dump(g, open(p, "w"))
    c, o = run("check", p)
    ok(c != 0 and "Traceback" not in o, f"check refuses {name}", o)
# A hand-written graph needs only three fields.
p = os.path.join(tmp, "short.json")
json.dump({"nodes": [{"label": "A"}, {"label": "B"}], "relations": ["r"], "edges": [[0, 0, 1, 1]]}, open(p, "w"))
c, o = run("check", p)
ok(c == 0 and "valid" in o, "check takes a graph with only three fields", o)
c, o = run("try", p, "path", "A", "B")
ok(c == 0 and "@0 A > @1 B" in o, "try takes a graph with only three fields", o)
# A shared name settled by the relation, the rule the firmware runs.
c, o = run("try", "nyc", "chase", "14 St", "FX southbound 1")
ok(c == 0 and o.strip() == "@478 W 4 St-Wash Sq", "try settles a shared name as the firmware does", o)
# Calls and examples refused before anything loads.
c, o = run("sim", graph("packages"), "--model", tmp, "path", "app", "libc", "extra")
ok(c != 0 and "path takes" in o and "Traceback" not in o, "sim refuses extra arguments", o)
c, o = run("ask", graph("packages"), "--tools", "path,, nosuch", "Q")
ok(c != 0 and "Unknown tool nosuch" in o, "an unknown tool", o)
for name, turns, want in (("wrongfn", [{"user": "q", "calls": [{"fn": "neighbors", "args": {}, "result": ""}], "reply": "r"}], "tools on offer"),
                          ("wrongarg", [{"user": "q", "calls": [{"fn": "neighbours", "args": {"node": "a", "rel": "b"}, "result": ""}], "reply": "r"}], "neighbours takes"),
                          ("wrongfield", [{"question": "q"}], "needs user, calls and reply"),
                          ("callsnumber", [{"user": "q", "calls": 5, "reply": "r"}], "calls is a list"),
                          ("argsnumber", [{"user": "q", "calls": [{"fn": "path", "args": 5, "result": ""}], "reply": "r"}], "args is an object"),
                          ("resultnumber", [{"user": "q", "calls": [{"fn": "path", "args": {"from": "a", "to": "b"}, "result": 5}], "reply": "r"}], "result is text"),
                          ("notoffered", [{"user": "q", "calls": [{"fn": "unlink", "args": {"from": "a", "relation": "b", "to": "c"}, "result": ""}], "reply": "r"}], "tools on offer")):
    p = os.path.join(tmp, name + ".examples.json")
    json.dump(turns, open(p, "w"))
    c, o = run("ask", graph("packages"), "--examples", p, "--tools", "neighbours, path, close", "Q")
    ok(c != 0 and want in o and "Traceback" not in o, f"examples: {name}", o)
c, o = run("ask", graph("packages"), "--tools", ",", "Q")
ok(c != 0 and "names no tools" in o, "--tools with no names", o)
c, o = run("ask", graph("packages"), "--examples", os.path.join(tmp, "nothing.json"), "Q")
ok(c != 0 and "Can't read" in o and "Traceback" not in o, "a missing examples file", o)
c, o = run("ask", graph("packages"), "--examples", "examples/packages.examples.json", "--tools", "neighbours,path,close,add_node,link", "Q")
ok(c != 0 and "needs --model" in o, "the example file is valid, and ask then asks for the model", o)
# The real firmware.
if model:
    c, o = run("sim", "nyc", "--model", model, "chase", "14 St", "FX southbound 1")
    ok(c == 0 and o.startswith("@478 W 4 St-Wash Sq") and "agree" in o, "sim settles a shared name as try does", o)
    long_a, long_b = "a1b2c3d4-" * 7, "e5f6a7b8-" * 7
    run("import", csv_file("long.csv", f"{long_a},next,{long_b}\n"), "-o", graph("long"))
    c, o = run("sim", graph("long"), "--model", model, "path", long_a, long_b)
    ok(c != 0 and "TOOLONG" in o and "the firmware reads 80" in o and "Traceback" not in o, "a call past the firmware's 80 tokens is explained", o)
    c, o = run("check", graph("long"), "--firmware", "--model", model)
    ok(c == 0 and "would print TOOLONG" in o, "check --firmware warns about long names", o)
    run("import", csv_file("mid.csv", "a1b2c3d4-a1b2c3d4-a1b2c3,next,e5f6a7b8-e5f6a7b8-e5f6a7\n"), "-o", graph("mid"))
    c, o = run("check", graph("mid"), "--firmware", "--model", model)
    ok(c == 0 and "A path call" in o and "A link call" in o, "check --firmware reports path and link", o)
    p = os.path.join(tmp, "full.json")                              # about 3 minutes: past the firmware's 256 new edges
    json.dump({"nodes": [{"label": f"N{i}"} for i in range(260)], "relations": ["r"], "edges": []}, open(p, "w"))
    c, o = run("sim", p, "--model", model, stdin="".join(f"link | N{i} | r | N{i + 1}\n" for i in range(258)) + "neighbours | N0 | r\nneighbours | N257 | r\n")
    ok(c == 0 and o.count("linked") == 256 and o.count("\nFULL\n") == 2 and "DIFFER" not in o, "a full edge table is explained, and later calls still agree", o)
    if "--build" in sys.argv:
        built = os.path.join(ROOT, "t8", "fw", "build_r6")
        keep = os.path.join(tmp, "build_r6")
        shutil.copytree(built, keep)
        try:
            c, o = run("build", "--model", model)
            same_clang = "23.1.4" in subprocess.run(["/opt/homebrew/opt/llvm/bin/clang", "--version"], capture_output=True, text=True).stdout
            ok(c == 0 and ("3d66be3572228cec" in o or not same_clang), "build runs, and gives the frozen firmware's hash on clang 23.1.4", o)
        finally:
            shutil.rmtree(built)
            shutil.copytree(keep, built)
    c, o = run("sim", graph("flights"), "--model", model, stdin="path | Lisbon | Warsaw\ncheapest | Lisbon | Warsaw\nclose | Paris\ncheapest | Lisbon | Warsaw\nadd_node | Oslo\nlink | Oslo | flight | Berlin\npath | Oslo | Athens\n")
    ok(c == 0 and o.count("agree") == 7 and "DIFFER" not in o, "firmware equals the reference on flights", o)
    c, o = run("sim", graph("u"), "--model", model, "path", "Ana Maria", "Zoë")
    ok(c == 0 and "agree" in o, "firmware with non-English names", o)
    c, o = run("check", graph("packages"), "--firmware", "--model", model)
    ok(c == 0 and "loads into the firmware" in o, "the graph fits the firmware", o)
print(f"{checks} checks, {fails} failed.")
sys.exit(1 if fails else 0)
