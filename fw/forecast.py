"""Replay Qwen's calls from the byte-token control (rvc/results/wrapctl_bytes, base Qwen, no machine) on the reference machine, on
the rvc and fw builds: the same forecast as rvc/results/m3_forecast_from_control_calls.json, by question kind.

    python fw/forecast.py      # writes results/forecast_from_control_calls.json

Each result is compared with the transcript's. Arithmetic on rates is left to the DEVLOG and labelled.
"""

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fwbox as F  # noqa: E402

X, BR = F.X, F.BR
GRAPHS = {"tiny": "host/test/tiny", "c024": "data/dev/cities/c024", "c025": "data/dev/cities/c025", "r001": "data/dev/random/r001"}


def main():
    T = BR.Text(X.tokenizer_json())
    res = {}
    for name, src in (("rvc", os.path.join(F.X210, "rvc", "graphlib.c")), ("fw", os.path.join(HERE, "graphlib.c"))):
        F.set_firmware(name, src)
        kinds, bad, total, calls = defaultdict(lambda: [0, 0, 0]), 0, 0, 0
        byq = {}
        for g_name, rel in GRAPHS.items():
            p = os.path.join(F.X210, rel)
            assert "heldout" not in p
            g = json.load(open(p + ".graph.json"))
            qs = {x["id"]: x for x in json.load(open(p + ".questions.json"))["questions"]}
            for ln in open(os.path.join(F.X210, "rvc", "results", "wrapctl_bytes", f"{g_name}.jsonl")):
                r = json.loads(ln)
                b = X.Box(g, T, max_records=10_000_000)
                for s in qs[r["id"]].get("setup") or []:
                    b.call(T.encode(X.template_text(s["fn"], s["args"])))
                t = 0
                for c in r["calls"]:
                    o = b.call(c["ids"])
                    t += o.chip
                    calls += 1
                    bad += o.result != c["result"]
                total += t
                k = kinds[r["kind"]]
                k[0] += 1
                k[1] += t
                k[2] += len(r["calls"])
                byq[f"{g_name}#{r['id']}"] = t
        res[name] = {"total_chip": total, "calls": calls, "results_differing_from_transcript": bad,
                     "by_kind": {a: {"questions": b[0], "chip": b[1], "calls": b[2], "chip_per_question": round(b[1] / b[0])} for a, b in kinds.items()}}
        print(name, json.dumps(res[name]), flush=True)
    json.dump(res, open(os.path.join(HERE, "results", "forecast_from_control_calls.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
