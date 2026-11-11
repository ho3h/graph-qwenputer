"""Which gates a run fired that were never compared on stock (REGISTRATION.md, part C). Finding 4, condition 2 of the round 2 critical review.

A residual check says nothing about a gate that never fires. So a gate run logs what it fired, and anything outside the baseline is a finding that needs a stock window.

    # a run's log, from any script that drives the engine: import covdiff first (it points cexec at the patched source), then
    #     ex = CExec(c, T); ex.start(prompt); log = covdiff.Cov(ex, label); ...run...; log.save(path)
    python covdiff.py trace --firmware fw --trace results/trace_fw --plan plan_fw.json --out results/cov/fw        # one log per saved trace, replayed and compared with the stock bits
    python covdiff.py baseline --logs results/cov/rvc results/cov/fw --out results/cov_baseline.json               # the union
    python covdiff.py diff --log run.json --baseline results/cov_baseline.json --out findings.json                 # exit 1 if anything is new, 2 if the tables differ

engine.c is not changed. Like diag_coverage.py, this writes a patched copy under build/ with one store per fired gate or channel and per value head read or written, and points CHIP_SRC at it. The patch adds only those stores, checked by apply_patch; on every trace the patched engine is
compared with the saved stock bits again, so a wrong patch would show there. The normal engine is untouched and a gate run may also run with it for speed comparisons.

Positions are counted after start(): the prompt is not compared on stock, so it is not in the baseline, and it is not in a run's log either.
"""
import argparse
import ctypes as ct
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MAX = 65536
MAX_VH = 1024


def apply_patch(src):
    """engine.c with the coverage stores. Every inserted line is a store to these arrays, nothing else changes."""
    edits = [("            int32_t g = g0 + i + k, u1 = gstart[g + 1];\n", "            if (!cov_gate[g0 + i + k]) { cov_gate[g0 + i + k] = 1; cov_gate_first[g0 + i + k] = p->steps; }\n", True),
             ("            int32_t c = f0 + i + k;\n", "            if (!cov_chan[c]) { cov_chan[c] = 1; cov_chan_first[c] = p->steps; }\n", False),
             ("                p->reads++;\n", "                if (!cov_read[vh]) { cov_read[vh] = 1; cov_read_first[vh] = p->steps; }\n", False),
             ("                    p->writes++;\n", "                    if (!cov_write[vh]) { cov_write[vh] = 1; cov_write_first[vh] = p->steps; }\n", False)]
    out = src
    for anchor, line, before in edits:
        assert out.count(anchor) == 1, anchor
        out = out.replace(anchor, line + anchor if before else anchor + line)
    decl = ("unsigned char cov_gate[%d], cov_chan[%d], cov_read[%d], cov_write[%d];\nlong long cov_gate_first[%d], cov_chan_first[%d], cov_read_first[%d], cov_write_first[%d];\n" % (MAX, MAX, MAX_VH, MAX_VH, MAX, MAX, MAX_VH, MAX_VH))
    anchor = "static inline float bf16r(float f) {"
    assert out.count(anchor) == 1
    out = out.replace(anchor, decl + anchor)
    removed = [ln for ln in src.splitlines() if ln not in out.splitlines()]
    assert not removed, removed
    return out


def install():
    src = open(os.path.join(HERE, "engine.c")).read()
    path = os.path.join(HERE, "build", "engine_covlog.c")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = apply_patch(src)
    if not os.path.exists(path) or open(path).read() != text:
        open(path, "w").write(text)
    os.environ["CHIP_SRC"] = path


install()

import common as C  # noqa: E402
import decode as D  # noqa: E402

import numpy as np  # noqa: E402

from chipformer.q35.ir import Head  # noqa: E402
from chipformer.rv import core  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402
from cexec import CExec  # noqa: E402


def tables_sha(A):
    h = hashlib.sha256()
    for k in sorted(A):
        if k == "vh_nrows":          # load_init raises it by the snapshot; the rest is fixed
            continue
        h.update(k.encode())
        h.update(str(A[k].dtype).encode())
        h.update(A[k].tobytes())
    return h.hexdigest()


class Cov:
    """Coverage from now on: the counts are reset and positions restart at 0."""

    def __init__(self, ex, label, extra=None):
        self.ex = ex
        self.label = label
        self.extra = extra or {}
        lib = ex.lib
        self.gate = np.ctypeslib.as_array((ct.c_ubyte * MAX).in_dll(lib, "cov_gate"))
        self.chan = np.ctypeslib.as_array((ct.c_ubyte * MAX).in_dll(lib, "cov_chan"))
        self.read = np.ctypeslib.as_array((ct.c_ubyte * MAX_VH).in_dll(lib, "cov_read"))
        self.write = np.ctypeslib.as_array((ct.c_ubyte * MAX_VH).in_dll(lib, "cov_write"))
        self.gate_f = np.ctypeslib.as_array((ct.c_longlong * MAX).in_dll(lib, "cov_gate_first"))
        self.chan_f = np.ctypeslib.as_array((ct.c_longlong * MAX).in_dll(lib, "cov_chan_first"))
        self.read_f = np.ctypeslib.as_array((ct.c_longlong * MAX_VH).in_dll(lib, "cov_read_first"))
        self.write_f = np.ctypeslib.as_array((ct.c_longlong * MAX_VH).in_dll(lib, "cov_write_first"))
        self.reset()

    def reset(self):
        for a in (self.gate, self.chan, self.read, self.write):
            a[:] = 0
        self.t0 = self.ex.p.steps

    def log(self):
        def pairs(on, first):
            ix = np.nonzero(on)[0]
            return [[int(i), int(first[i] - self.t0)] for i in ix]

        A = self.ex.A
        return {"label": self.label, **self.extra, "tables_sha256": tables_sha(A), "engine_source_sha256": hashlib.sha256(open(os.path.join(HERE, "engine.c"), "rb").read()).hexdigest(), "positions": int(self.ex.p.steps - self.t0),
                "gates_total": int(len(A["gstart"]) - 1), "channels_total": int(len(A["fan_ptr"]) - 1), "value_heads": int(len(A["vh_S"])), "gates": pairs(self.gate, self.gate_f), "channels": pairs(self.chan, self.chan_f),
                "reads": pairs(self.read, self.read_f), "writes": pairs(self.write, self.write_f), "flags": self.ex.flags()}

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        json.dump(self.log(), open(path, "w"))


def bits_of(keep):
    u = keep.view(np.uint32)
    r = (u + 0x7FFF + ((u >> 16) & 1)) & 0xFFFF0000
    return (r >> 16).astype(np.uint16)


def replay(L, ex, tr, keep_cols, plan_job):
    """One saved stock trace through the patched engine. Returns (Cov, tally). Only positions the trace holds. The machine is rebuilt without the reference run: the stream is in the trace."""
    meta = json.loads(str(tr["meta"]))
    n = meta["positions"]
    g = plan_job["graph"] if isinstance(plan_job["graph"], dict) else json.load(open(D.graph_path(plan_job["graph"])[0]))
    m0 = D.parked_machine(g, L.T, plan_job.get("setup"))
    core.snapshot(L.c, m0)
    stream = [C.to_stream(L.v0, int(t)) for t in tr["tokens"]]
    assert len(stream) == n
    ex.start([C.to_stream(L.v0, i) for i in meta["prompt"]])
    ex.p.flags = 0
    cov = Cov(ex, meta["name"], {"trace_elf_sha256": meta["elf_sha256"], "stock_finished": meta["finished"], "compared_on_stock": True})
    keep = ex.run(stream)
    kb = bits_of(keep).tolist()
    ptr, idx, bits = tr["ptr"].tolist(), tr["idx"].tolist(), tr["bits"].tolist()
    pos = {int(c) for c in keep_cols}
    cols = [int(c) for c in keep_cols]
    differ = residue = 0
    for i in range(n):
        a, b = ptr[i], ptr[i + 1]
        stock = dict(zip(idx[a:b], bits[a:b]))
        residue += sum(d not in pos for d in stock)
        differ += stock != {c: v for c, v in zip(cols, kb[i]) if v}
    return cov, {"job": meta["name"], "positions": n, "positions_differing": int(differ), "stock_residue_outside_keep": residue, "flags": ex.flags()}


def cmd_trace(a):
    L = C.Lite(tokenizer=False)
    keep_cols = L.meta["code_dims"] + [L.meta["tau_dim"], L.meta["mu_dim"]]
    elf = hashlib.sha256(open(C.X.build_elf(), "rb").read()).hexdigest()
    plan = {j["name"]: j for j in json.load(open(a.plan))}
    os.makedirs(a.out, exist_ok=True)
    ex = None
    tally = []
    for name, job in plan.items():
        p = os.path.join(a.trace, name + ".npz")
        if not os.path.exists(p):
            continue
        tr = dict(np.load(p))
        meta = json.loads(str(tr["meta"]))
        assert meta["elf_sha256"] == elf, f"{name} was traced on another firmware"
        if ex is None:
            core.snapshot(L.c, D.parked_machine(job["graph"] if isinstance(job["graph"], dict) else json.load(open(D.graph_path(job["graph"])[0])), L.T, job.get("setup")))
            ex = CExec(L.c, L.T)
        t0 = time.time()
        cov, t = replay(L, ex, tr, keep_cols, job)
        cov.extra["firmware"] = a.firmware
        cov.save(os.path.join(a.out, name + ".json"))
        t["seconds"] = round(time.time() - t0, 1)
        t["gates"] = int(cov.gate.sum())
        tally.append(t)
        print(json.dumps(t), flush=True)
        if t["positions_differing"]:
            print("STOP: the replay differs from the saved stock bits", flush=True)
            json.dump(tally, open(os.path.join(a.out, "tally.json"), "w"), indent=1)
            sys.exit(3)
    json.dump(tally, open(os.path.join(a.out, "tally.json"), "w"), indent=1)


def read_logs(dirs):
    out = []
    for d in dirs:
        for f in sorted(os.listdir(d)):
            if f.endswith(".json") and f != "tally.json":
                x = json.load(open(os.path.join(d, f)))
                x["_file"] = os.path.join(d, f)
                out.append(x)
    return out


KINDS = ("gates", "channels", "reads", "writes")


def make_baseline(logs):
    sha = {x["tables_sha256"] for x in logs}
    assert len(sha) == 1, "logs from different tables"
    res = {"tables_sha256": sha.pop(), "traces": [{"file": os.path.relpath(x["_file"], HERE), "firmware": x.get("firmware"), "label": x["label"], "positions": x["positions"], "elf": x.get("trace_elf_sha256")} for x in logs],
           "positions": sum(x["positions"] for x in logs), "gates_total": logs[0]["gates_total"], "channels_total": logs[0]["channels_total"], "value_heads": logs[0]["value_heads"]}
    for k in KINDS:
        res[k] = sorted({i for x in logs for i, _ in x[k]})
    return res


def describe(L, A):
    """Readable names: a gate's level and output dims; a channel's head; a value head's name."""
    names = [d.name for d in L.c.dims]
    heads = sorted((n for n in L.c.nodes if isinstance(n, Head)), key=lambda n: n.level)
    vh_names = [n.name for n in heads for _ in n.vheads()]
    gate_level = {}
    for rec in A["levels"]:
        if rec[0] == 0:
            for g in range(rec[3], rec[3] + rec[5]):
                gate_level[g] = int(rec[12])
    chan_level = {}
    for rec in A["levels"]:
        if rec[0] == 1:
            for c_ in range(rec[8], rec[8] + rec[5]):
                chan_level[c_] = int(rec[12])
    return names, vh_names, gate_level, chan_level


def diff(log, base, describe_with=None):
    if log["tables_sha256"] != base["tables_sha256"]:
        return {"refused": "the log and the baseline are from different tables", "log": log["tables_sha256"], "baseline": base["tables_sha256"]}
    out = {"log": log["label"], "positions": log["positions"], "baseline_positions": base["positions"], "new": {}, "counts": {}}
    for k in KINDS:
        known = set(base[k])
        new = [(i, f) for i, f in log[k] if i not in known]
        out["counts"][k] = {"fired": len(log[k]), "new": len(new)}
        out["new"][k] = new
    if describe_with:
        L, A = describe_with
        names, vh_names, gate_level, chan_level = describe(L, A)
        gs = A["gstart"]
        out["gates_detail"] = [{"gate": g, "first_position": f, "level": gate_level.get(g), "out_dims": sorted({names[int(d)] for d in A["uout"][gs[g]:gs[g + 1]]})[:4], "units": int(gs[g + 1] - gs[g])} for g, f in out["new"]["gates"]]
        out["new_gates_by_part"] = {}
        for x in out["gates_detail"]:
            for nm in x["out_dims"][:1]:
                pre = re.split(r"[.\[>=+]", nm)[0]
                out["new_gates_by_part"][pre] = out["new_gates_by_part"].get(pre, 0) + 1
        out["new_heads_read"] = sorted({vh_names[i] for i, _ in out["new"]["reads"]})
        out["new_heads_written"] = sorted({vh_names[i] for i, _ in out["new"]["writes"]})
        firsts = sorted(f for k in KINDS for _, f in out["new"][k])
        out["first_new_position"] = firsts[0] if firsts else None
    n = sum(v["new"] for v in out["counts"].values())
    out["finding"] = n > 0
    out["needs_stock_window"] = "yes: every position in new.* first fires something never compared on stock" if n else "no"
    return out


def cmd_baseline(a):
    res = make_baseline(read_logs(a.logs))
    json.dump(res, open(a.out, "w"))
    print(json.dumps({k: (len(res[k]) if k in KINDS else res[k]) for k in res if k != "traces"}), flush=True)


def cmd_diff(a):
    log, base = json.load(open(a.log)), json.load(open(a.baseline))
    d = None
    if a.names:
        L = C.Lite(tokenizer=False)
        import tablecheck as TC
        A, _ = TC.load_program(TC.program_path(L.c))
        d = (L, A)
    r = diff(log, base, d)
    if a.out:
        json.dump(r, open(a.out, "w"), indent=0)
    if "refused" in r:
        print(r["refused"], flush=True)
        sys.exit(2)
    print(json.dumps({k: r[k] for k in r if k not in ("new", "gates_detail")})[:1800], flush=True)
    sys.exit(1 if r["finding"] else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trace")
    t.add_argument("--firmware", required=True)
    t.add_argument("--trace", required=True)
    t.add_argument("--plan", required=True)
    t.add_argument("--out", required=True)
    t.set_defaults(fn=cmd_trace)
    b = sub.add_parser("baseline")
    b.add_argument("--logs", nargs="+", required=True)
    b.add_argument("--out", required=True)
    b.set_defaults(fn=cmd_baseline)
    d = sub.add_parser("diff")
    d.add_argument("--log", required=True)
    d.add_argument("--baseline", required=True)
    d.add_argument("--out")
    d.add_argument("--names", action="store_true")
    d.set_defaults(fn=cmd_diff)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
