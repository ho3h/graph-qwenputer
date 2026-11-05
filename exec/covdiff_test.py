"""The tests registered for covdiff.py. Set arithmetic on saved logs, then two streams that should differ.

    CHIP_FIRMWARE=fw.elf python covdiff_test.py --out results/covdiff_test.json
"""
import argparse
import hashlib
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import covdiff as CD  # noqa: E402  (points cexec at the patched engine source)
import common as C  # noqa: E402
import decode as D  # noqa: E402
import tablecheck as TC  # noqa: E402

import numpy as np  # noqa: E402

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import core, elf, ref  # noqa: E402
from cexec import CExec  # noqa: E402

KINDS = CD.KINDS
CALC_ELF = os.path.join(C.X210, "vendor", "qwenputer-riscv", "tests", "data", "rv", "calc-bridge.elf")
CALLS = ("12*34", "7*6", "2*(3+4)-50", "99999999999*99999999999", "(1.2 - 3) * 4.5 - 0.75", "-84/18", "-84//18", "2**64 % 1000003", "gcd(462, 1071)", "123456789012345678901234567890 // 987654321", "2**200 % 1000000007")


def set_tests(logs_fw, logs_rvc, res):
    logs = logs_rvc + logs_fw
    base = CD.make_baseline(logs)
    # each saved stream against the full baseline
    rows = []
    for x in logs:
        d = CD.diff(x, base)
        rows.append({"file": os.path.relpath(x["_file"], HERE), "new": {k: d["counts"][k]["new"] for k in KINDS}, "fired_gates": d["counts"]["gates"]["fired"], "finding": d["finding"]})
    res["saved_streams_vs_full_baseline"] = {"streams": len(rows), "with_any_new": sum(r["finding"] for r in rows), "rows": rows}
    # leave one out, against set arithmetic done here on counts
    loo = []
    for k in KINDS:
        n = max(max((i for i, _ in x[k]), default=0) for x in logs) + 1
        cnt = np.zeros(n, np.int32)
        for x in logs:
            cnt[[i for i, _ in x[k]]] += 1
        res.setdefault("loo_counts", {})[k] = int((cnt > 0).sum())
        for j, x in enumerate(logs):
            b2 = CD.make_baseline(logs[:j] + logs[j + 1:])
            new = {i for i, _ in CD.diff(x, b2)["new"][k]}
            want = {i for i, _ in x[k] if cnt[i] == 1}
            loo.append({"file": os.path.basename(x["_file"]), "firmware": x.get("firmware"), "kind": k, "tool": len(new), "arithmetic": len(want), "equal": new == want})
    res["leave_one_out"] = {"cases": len(loo), "equal": sum(r["equal"] for r in loo), "gates": [r for r in loo if r["kind"] == "gates"]}
    # gates taken out of the baseline are listed exactly, each kind
    rng = random.Random(20261102)
    rem = []
    for k in KINDS:
        b2 = json.loads(json.dumps(base))
        out = set(rng.sample(base[k], 5))
        b2[k] = [i for i in base[k] if i not in out]
        for x in logs:
            pass
        union = {"tables_sha256": base["tables_sha256"], "label": "union", "positions": base["positions"], **{q: [[i, 0] for i in base[q]] for q in KINDS}}
        d = CD.diff(union, b2)
        rem.append({"kind": k, "removed": sorted(out), "listed": sorted(i for i, _ in d["new"][k]), "exact": {i for i, _ in d["new"][k]} == out, "others_new": sum(d["counts"][q]["new"] for q in KINDS if q != k)})
    res["removed_from_baseline"] = rem
    # a log from other tables is refused
    x = dict(logs[0])
    x["tables_sha256"] = hashlib.sha256(b"other").hexdigest()
    res["other_tables_refused"] = "refused" in CD.diff(x, base)
    # the firmwares against each other
    bf, br = CD.make_baseline(logs_fw), CD.make_baseline(logs_rvc)
    res["firmware_split"] = {k: {"fw": len(bf[k]), "rvc": len(br[k]), "union": len(base[k]), "fw_only": len(set(bf[k]) - set(br[k])), "rvc_only": len(set(br[k]) - set(bf[k]))} for k in KINDS}
    return base, bf, br


def cmd(a):
    t0 = time.time()
    res = {"seed": 20261102}
    logs_fw, logs_rvc = CD.read_logs(["results/cov/fw"]), CD.read_logs(["results/cov/rvc"])
    base, bf, br = set_tests(logs_fw, logs_rvc, res)
    json.dump(base, open(os.path.join(HERE, "results", "cov_baseline.json"), "w"))
    res["baseline"] = {"file": "results/cov_baseline.json", "positions": base["positions"], "traces": len(base["traces"]), **{k: len(base[k]) for k in KINDS}, "gates_total": base["gates_total"], "channels_total": base["channels_total"], "value_heads": base["value_heads"]}
    old = json.load(open(os.path.join(HERE, "results", "diag_coverage_fw.json")))
    res["reported_with_prompts"] = {"fw_gates_diag_coverage": old["gates_ever_on"], "fw_gates_compared_only": len(bf["gates"]), "difference": old["gates_ever_on"] - len(bf["gates"]), "units_ever_on_reported": old["units_ever_on"], "reads_reported": old["ever_read"], "writes_reported": old["ever_written"]}
    print(json.dumps({k: res[k] for k in ("baseline", "reported_with_prompts", "firmware_split", "other_tables_refused")}), flush=True)
    print("saved vs full", res["saved_streams_vs_full_baseline"]["with_any_new"], "loo", res["leave_one_out"]["equal"], "of", res["leave_one_out"]["cases"], "removed", [r["exact"] for r in res["removed_from_baseline"]], flush=True)
    json.dump(res, open(a.out, "w"), indent=0)

    L = C.Lite(tokenizer=False)
    A, _ = TC.load_program(TC.program_path(L.c))
    names = (L, A)
    plan = {j["name"]: j for j in json.load(open(os.path.join(HERE, "plan_fw.json")))}

    # a stream that should differ: big-number calls on the vendored calc firmware, which uses the digit file and the quotient heads
    T = L.T
    m0 = ref.Machine.from_program(elf.program(CALC_ELF))
    BR.park(m0)
    m = ref.Machine.from_program(elf.program(CALC_ELF))
    BR.park(m)
    ses = BR.Session(T, m)
    ses.qwen(T.encode("<|im_start|>assistant\n"))
    for e in CALLS:
        ses.qwen(T.encode(f"<tool_call>\n<function=calc>\n<parameter=expression>\n{e}\n</parameter>\n</function>\n</tool_call>"))
        ses.qwen(T.encode(" ok "))
    core.snapshot(L.c, m0)
    ex = CExec(L.c, L.T)
    ex.clear()
    ex.load_init()
    ex.p.flags = 0
    cov = CD.Cov(ex, "calc-bridge big-number calls", {"firmware": "vendor calc-bridge.elf", "compared_on_stock": False, "calls": CALLS, "results": [T.decode_bytes(x).decode("utf-8", "replace") for x in ses.runs]})
    ex.run(ses.toks)
    cov.save(os.path.join(HERE, "results", "cov", "stream_calc_bridge.json"))
    log = cov.log()
    d = CD.diff(log, base, names)
    res["calc_bridge"] = {"positions": log["positions"], "results": log["results"], "flags": log["flags"], **{k: d[k] for k in ("counts", "finding", "new_gates_by_part", "new_heads_read", "new_heads_written", "first_new_position")}}
    json.dump(d, open(os.path.join(HERE, "results", "covdiff_calc_bridge.json"), "w"), indent=0)
    print(json.dumps(res["calc_bridge"])[:1800], flush=True)
    json.dump(res, open(a.out, "w"), indent=0)

    # the hub from its start, past where the stock trace stopped (fw firmware)
    job = plan["lim-hub"]
    tr = np.load(os.path.join(HERE, "results", "trace_fw", "lim-hub.npz"))
    meta = json.loads(str(tr["meta"]))
    t1 = time.time()
    m0_, stream, own, ses = D.session_for(L, job["graph"], meta["prompt"], [tuple(x) for x in job["calls"]], job.get("setup"), between=" ", tail="Done.")
    res_ref_s = round(time.time() - t1, 1)
    core.snapshot(L.c, m0_)
    ex2 = ex
    ex2.start([C.to_stream(L.v0, i) for i in meta["prompt"]])
    ex2.p.flags = 0
    cov = CD.Cov(ex2, "lim-hub whole", {"firmware": "fw", "compared_on_stock": False, "stock_trace_stopped_at": meta["positions"]})
    ex2.run(stream)
    cov.save(os.path.join(HERE, "results", "cov", "stream_hub_whole.json"))
    log = cov.log()
    d = CD.diff(log, base, names)
    firsts = sorted(f for k in KINDS for _, f in d["new"][k])
    res["hub_whole"] = {"positions": log["positions"], "stock_trace_stopped_at": meta["positions"], "reference_seconds": res_ref_s, "flags": log["flags"], **{k: d[k] for k in ("counts", "finding", "new_gates_by_part", "new_heads_read", "new_heads_written", "first_new_position")},
                        "new_first_fired_inside_the_traced_part": sum(f < meta["positions"] for f in firsts), "gate_first_positions_head": firsts[:10]}
    json.dump(d, open(os.path.join(HERE, "results", "covdiff_hub_whole.json"), "w"), indent=0)
    print(json.dumps(res["hub_whole"])[:1400], flush=True)
    res["seconds"] = round(time.time() - t0)
    json.dump(res, open(a.out, "w"), indent=0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    cmd(ap.parse_args())
