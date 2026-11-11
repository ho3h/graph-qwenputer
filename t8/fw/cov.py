#!/usr/bin/env python3
"""exec/covdiff.py on tok's engine and tables, unchanged in logic, its build paths moved under t8/fw/build so nothing is written in exec/ or tok/. Adds one command, `chain`: the machine's calls from saved chain rows, run on the coverage engine, logged, for `diff` against the baseline.

    python t8/fw/tokrun.py ../t8/fw/cov.py trace --firmware clean --trace t8/fw/results/trace --plan t8/fw/plan_clean.json --out t8/fw/results/cov/clean
    python t8/fw/tokrun.py ../t8/fw/cov.py baseline --logs t8/fw/results/cov/clean --out t8/fw/results/cov_baseline.json
    python t8/fw/tokrun.py ../t8/fw/cov.py chain --rows R.jsonl [R2.jsonl] --out t8/fw/results/cov/chain.json
    python t8/fw/tokrun.py ../t8/fw/cov.py diff --log t8/fw/results/cov/chain.json --baseline t8/fw/results/cov_baseline.json --out t8/fw/results/covdiff_chain.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
TOK = os.path.join(X210, "tok")
BUILD = os.path.join(HERE, "build")
src = open(os.path.join(X210, "exec", "covdiff.py")).read()
for old, new in (("HERE = os.path.dirname(os.path.abspath(__file__))", f"HERE = {TOK!r}"), ('os.path.join(HERE, "build", "engine_covlog.c")', repr(os.path.join(BUILD, "engine_covlog.c")))):
    assert src.count(old) == 1, old
    src = src.replace(old, new)
src = src.replace('if __name__ == "__main__":\n    main()\n', "")
ns = {"__name__": "covdiff_t8", "__file__": os.path.join(TOK, "covdiff.py")}
sys.path.insert(0, TOK)
exec(compile(src, ns["__file__"], "exec"), ns)
import cexec  # noqa: E402

cexec.HERE = BUILD                                                  # the library goes under t8/fw/build
C, D, core, CExec, BR = ns["C"], ns["D"], ns["core"], ns["CExec"], __import__("chipformer.rv.bridge", fromlist=["x"])
X = C.X


def chain(rows, out):
    L = C.Lite(tokenizer=False)
    T = L.T
    ex, cov, n = None, None, 0
    for p in rows:
        for ln in open(p):
            r = json.loads(ln)
            gp = D.graph_path(r["tag"][0])[0]
            g = json.load(open(gp))
            for c in r["calls"]:
                m0 = D.parked_machine(g, T, None)
                m = D.parked_machine(g, T, None)
                ses = BR.Session(T, m)
                ses.qwen([T.TCO] + T.encode(c["text"]) + [T.TCC], max_records=400000)
                core.snapshot(L.c, m0)
                if ex is None:
                    ex = CExec(L.c, L.T)
                    cov = ns["Cov"](ex, "chain machine calls", {"compared_on_stock": False, "firmware": "clean", "rows": rows})
                ex.clear()
                ex.load_init()
                ex.run(ses.toks)
                n += 1
    cov.extra["calls"] = n
    cov.save(out)
    print(n, "calls", ex.flags(), flush=True)


def pick(rows, base_p, out, budget):
    """Greedy: the machine calls that reach the most never-compared items per position, up to budget positions. Each call alone, as chain() runs it."""
    L = C.Lite(tokenizer=False)
    T = L.T
    base = json.load(open(base_p))
    known = {k: set(base[k]) for k in ("gates", "channels", "reads", "writes")}
    ex, cov, cands = None, None, []
    for p in rows:
        for ln in open(p):
            r = json.loads(ln)
            g = json.load(open(D.graph_path(r["tag"][0])[0]))
            for c in r["calls"]:
                m0 = D.parked_machine(g, T, None)
                m = D.parked_machine(g, T, None)
                ses = BR.Session(T, m)
                ses.qwen([T.TCO] + T.encode(c["text"]) + [T.TCC], max_records=400000)
                core.snapshot(L.c, m0)
                if ex is None:
                    ex = CExec(L.c, L.T)
                    cov = ns["Cov"](ex, "pick", {})
                ex.clear()
                ex.load_init()
                cov.reset()
                ex.run(ses.toks)
                new = set()
                for k, a in (("gates", cov.gate), ("channels", cov.chan), ("reads", cov.read), ("writes", cov.write)):
                    new |= {(k, int(i)) for i in ns["np"].nonzero(a)[0] if int(i) not in known[k]}
                if new:
                    cands.append({"graph": r["tag"][0], "args": c["args"], "positions": len(ses.toks), "new": new, "from": os.path.basename(os.path.dirname(p))})
    every = set().union(*(x["new"] for x in cands))
    left, chosen, used = set(every), [], 0
    while left:
        fit = [x for x in cands if used + x["positions"] <= budget and x["new"] & left]
        if not fit:
            break
        x = max(fit, key=lambda y: len(y["new"] & left) / y["positions"])
        chosen.append({**{k: x[k] for k in ("graph", "args", "positions", "from")}, "adds": len(x["new"] & left)})
        left -= x["new"]
        used += x["positions"]
    plan = [{"name": f"win{i:02d}", "graph": x["graph"], "calls": [["chase", x["args"]]]} for i, x in enumerate(chosen)]
    json.dump(plan, open(out, "w"), indent=0, ensure_ascii=False)
    by = lambda s: {k: sum(1 for a, _ in s if a == k) for k in ("gates", "channels", "reads", "writes")}
    print(json.dumps({"calls_seen": len(cands), "new_in_all": by(every), "chosen": len(chosen), "positions": used, "left": by(left)}), [(x["adds"], x["positions"]) for x in chosen], flush=True)


if len(sys.argv) > 1 and sys.argv[1] == "pick":
    i = sys.argv.index("--out")
    pick(sys.argv[sys.argv.index("--rows") + 1:i], sys.argv[sys.argv.index("--baseline") + 1], sys.argv[i + 1], int(sys.argv[sys.argv.index("--budget") + 1]))
elif len(sys.argv) > 1 and sys.argv[1] == "chain":
    i = sys.argv.index("--out")
    chain(sys.argv[sys.argv.index("--rows") + 1:i], sys.argv[i + 1])
elif __name__ == "__main__":
    ns["main"]()
