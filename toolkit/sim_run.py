#!/usr/bin/env python3
"""The real firmware on the simulator, with the reference machine and reference library beside it on every call. Run by gq.py through t8/fw/tokrun.py."""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(os.path.dirname(HERE), "exam")]
import calls as C  # noqa: E402
import mach as M  # noqa: E402
import noun as N  # noqa: E402
import reflib  # noqa: E402
import box as XX  # noqa: E402

g_path, calls_path = sys.argv[1], sys.argv[2]
calls = json.load(open(calls_path))
os.unlink(calls_path)
g = N.with_noun(C.filled(json.load(open(g_path, encoding="utf-8"))))
SPACE = 220  # the token for one space, the only text the simulator needs around the calls
try:
    pair = M.Pair(g, [SPACE], [SPACE], coverage=False)
except subprocess.CalledProcessError as e:
    sys.exit(f"The C engine didn't compile: {e}")
except Exception as e:
    sys.exit(f"The graph does not fit the firmware: {e}")
if not calls:
    print(f"The graph loads into the firmware's memory: {len(g['nodes'])} nodes, {len(g['edges'])} edges.")
    size = lambda s: len(pair.T.encode(s))
    labs = sorted((n["label"] for n in g["nodes"]), key=size, reverse=True)[:2]
    rel = max(g["relations"], key=size, default=None)
    if labs:
        for fn, x in (("path", {"from": labs[0], "to": labs[-1]}), ("link", {"from": labs[0], "relation": rel, "to": labs[-1]})):
            if None not in x.values():
                n = size(XX.template_text(fn, x))
                print(f"A {fn} call between your two longest names is {n} tokens, and the firmware reads {XX.CAP_ROWS}." + (" That call would print TOOLONG." if n > XX.CAP_ROWS else ""))
    sys.exit(0)
G = reflib.Graph(g)
pair.fresh()
bad = 0
for c in calls:
    fn, vals = c[0], c[1:]
    msg = C.problem(fn, vals)
    if msg:
        sys.exit(msg)
    x = dict(zip(C.ARGS[fn], vals))
    ids = pair.T.encode(XX.template_text(fn, x))
    t0 = time.time()
    r = pair.call(ids)
    if r["body"] == XX.TOOLONG:                                     # the call changed nothing on the machine, so the reference library must not run it either
        bad += 1
        print(f"{r['body']}\n  The call is {len(ids)} tokens, and the firmware reads {XX.CAP_ROWS}. Shorter names or fewer legs fit.", flush=True)
        continue
    if fn == "link" and r["same"] and r["body"] == "FULL":          # the reference library has no limit on new edges, so it must not run this link either
        print(f"{r['body']}\n  The firmware holds 256 new edges in one conversation. The reference machine agrees. The reference library has no such limit, so it skips this call.", flush=True)
        continue
    want = G.call(fn, x)
    same = r["same"] and r["body"] == want
    bad += not same
    print(r["body"])
    print(f"  {r['chip']:,} machine tokens, {time.time() - t0:.1f} s. Reference machine and reference library: {'agree' if same else 'DIFFER: ' + repr(want)}.", flush=True)
sys.exit(1 if bad else 0)
