"""Item 1: machine tokens by C function, per SPEC function, over Qwen's real calls and the dev questions.

    python hist.py --tag rvc --src ../rvc/graphlib.c [--workers 4] [--quick]

Same call sets and order as rvc/test_m1.py task_real / task_dev, so mean tokens per function must equal rvc's M1 figures on
an unchanged build (checked by the report). Raw output: results/hist_raw_<tag>.json.gz. Bounded: 4M records and a 300 s
alarm per call; the run stops at --max-seconds. Never reads data/heldout (asserted on every path).
"""

import argparse
import glob
import gzip
import json
import os
import signal
import sys
import time
from collections import defaultdict
from multiprocessing import get_context

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fwbox as F  # noqa: E402
import attrib as A  # noqa: E402
X = F.X
BR = F.BR

DEV = os.path.join(F.X210, "data", "dev")
HOST_OUT = os.path.join(F.X210, "host", "out")
OUT = os.path.join(HERE, "results")
CALL_LIMIT_S = 300
T, ATT = None, None


def checked(p):
    assert "heldout" not in p and "/raw/" not in p, p
    return p


def init_worker(tag, src):
    global T, ATT
    F.set_firmware(tag, src)
    T = BR.Text(X.tokenizer_json())
    ATT = A.Attrib(os.path.join(F.BUILD, tag + "-g.elf"))


class Alarm(Exception):
    pass


def _alarm(*_):
    raise Alarm(f"no answer within {CALL_LIMIT_S} s")


def limited(f, *a):
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(CALL_LIMIT_S)
    try:
        return f(*a)
    finally:
        signal.alarm(0)


class Tally:
    def __init__(self):
        self.g = defaultdict(lambda: {"calls": 0, "chip": 0, "echo": 0, "cap": 0, "cap_bytes": 0, "records": 0,
                                      "chip_max": 0, "ctx_bad": 0, "samples": [], "t": defaultdict(lambda: [0, 0])})

    def run(self, box, ids, part, fn):
        m = box.m
        m.p_tally, m.p_ctx = {}, 0
        r = limited(box.call, ids)
        k = self.g[f"{part}/{fn or '?'}"]
        k["calls"] += 1
        k["chip"] += r.chip
        k["echo"] += r.echo
        k["cap"] += len(ids)
        k["cap_bytes"] += sum(len(T.bytes[q]) for q in ids)
        k["records"] += r.records
        k["chip_max"] = max(k["chip_max"], r.chip)
        k["samples"].append([r.chip, len(ids)])
        if m.p_ctx != 0:
            k["ctx_bad"] += 1
        t = k["t"]
        cache = {}
        for (c, pc), (n, rec) in m.p_tally.items():
            cx = cache.get(c)
            if cx is None:
                cx = cache[c] = m.context(c)
            v = t[(cx, pc)]
            v[0] += n
            v[1] += rec
        return r

    def dump(self):
        return {g: {**{a: b for a, b in k.items() if a != "t"}, "t": dict(k["t"])} for g, k in self.g.items()}


def enc(fn, args):
    return T.encode(X.template_text(fn, args))


def task_dev(path):
    t = Tally()
    gpath = checked(path.replace(".questions.json", ".graph.json"))
    g = json.load(open(gpath))
    q = json.load(open(checked(path)))
    try:
        shared = F.Box(g, T, attrib=ATT)
    except F.B.BootLimit as e:
        return {"notes": [{"does_not_fit": os.path.basename(gpath), "why": str(e)}], "groups": {}}
    for x in q["questions"]:
        call = x["call"]
        fresh = bool(x.get("setup")) or call["fn"] in ("close", "reopen", "link", "unlink")
        if fresh:
            b = F.Box(g, T, attrib=ATT)
            for s in x.get("setup", []):
                t.run(b, enc(s["fn"], s["args"]), "dev", s["fn"])
        else:
            b = shared
        t.run(b, enc(call["fn"], call["args"]), "dev", call["fn"])
    labels = sorted({n["label"] for n in g["nodes"]})
    if len(labels) > 200:
        import random
        labels = random.Random(0).sample(labels, 64)
    for lab in labels:
        t.run(shared, enc("find", {"name": lab}), "dev", "find")
    return {"notes": [], "groups": t.dump()}


def task_real(jpath):
    t = Tally()
    meta = json.load(open(os.path.join(os.path.dirname(jpath), "meta.json")))
    g = json.load(open(checked(meta["graph"])))
    qs = {x["id"]: x for x in json.load(open(checked(meta["questions"])))["questions"]}
    for line in open(jpath):
        r = json.loads(line)
        b = F.Box(g, T, attrib=ATT)
        for s in qs[r["id"]].get("setup") or []:
            b.call(enc(s["fn"], s["args"]))
        for c in r["calls"]:
            t.run(b, c["ids"], "real", c["fn"])
    return {"notes": [], "groups": t.dump()}


def call_job(j):
    f, x = j
    try:
        return {"job": str(x), **f(x)}
    except Exception as e:
        import traceback
        return {"job": str(x), "notes": [{"crash": str(e), "tb": traceback.format_exc()[-800:]}], "groups": {}}


def real_files():
    out = []
    for run in ("dev1", "dev2", "dev2-repeat", "dev3-clear"):
        for f in sorted(glob.glob(os.path.join(HOST_OUT, run, "*", "*.jsonl"))):
            if os.path.exists(os.path.join(os.path.dirname(f), "meta.json")):
                out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--parts", default="real,dev")
    ap.add_argument("--max-seconds", type=int, default=3600)
    a = ap.parse_args()
    a.workers = min(a.workers, 4)
    src = os.path.abspath(a.src)
    F.set_firmware(a.tag, src)
    g = F.build_g(src, a.tag)
    assert A.same_code(X.ELF, g), "the -g build's code differs"
    jobs = []
    if "real" in a.parts:
        r = real_files()
        jobs += [(task_real, p) for p in (r[:2] if a.quick else r)]
    if "dev" in a.parts:
        q = [checked(p) for p in sorted(glob.glob(os.path.join(DEV, "*", "*.questions.json")))]
        jobs += [(task_dev, p) for p in (q[:3] if a.quick else q)]
    t0 = time.time()
    merged, notes = {}, []
    with get_context("spawn").Pool(a.workers, initializer=init_worker, initargs=(a.tag, src), maxtasksperchild=20) as pool:
        for i, res in enumerate(pool.imap_unordered(call_job, jobs)):
            notes += res["notes"]
            for gr, k in res["groups"].items():
                m = merged.setdefault(gr, {"calls": 0, "chip": 0, "echo": 0, "cap": 0, "cap_bytes": 0, "records": 0,
                                           "chip_max": 0, "ctx_bad": 0, "samples": [], "t": {}})
                for f in ("calls", "chip", "echo", "cap", "cap_bytes", "records", "ctx_bad"):
                    m[f] += k[f]
                m["chip_max"] = max(m["chip_max"], k["chip_max"])
                m["samples"] += k["samples"]
                for key, v in k["t"].items():
                    w = m["t"].setdefault(key, [0, 0])
                    w[0] += v[0]
                    w[1] += v[1]
            print(f"{time.time() - t0:.0f}s {i + 1}/{len(jobs)} {res['job'][-48:]} notes={len(res['notes'])}", flush=True)
            if time.time() - t0 > a.max_seconds:
                pool.terminate()
                notes.append({"stopped_at": i + 1, "of": len(jobs)})
                break
    for k in merged.values():
        k["t"] = [[list(c), pc, v[0], v[1]] for (c, pc), v in k["t"].items()]
    path = os.path.join(OUT, f"hist_raw_{a.tag}{'_quick' if a.quick else ''}.json.gz")
    with gzip.open(path, "wt") as fh:
        json.dump({"tag": a.tag, "src": src, "seconds": round(time.time() - t0, 1), "notes": notes, "groups": merged}, fh)
    print("wrote", path, "notes", notes[:5])


if __name__ == "__main__":
    main()
