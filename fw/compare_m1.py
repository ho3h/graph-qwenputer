"""Before and after by function: rvc/results/m1_full.summary.json against a fw/ build's summary. Writes results/before_after.json.

    python fw/compare_m1.py results/m1_fw/m1_full.summary.json
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
FNS = ["find", "follow", "chase", "neighbours", "path", "cheapest", "close", "reopen", "link", "unlink"]


def main():
    a = json.load(open(os.path.join(X210, "rvc", "results", "m1_full.summary.json")))
    b = json.load(open(sys.argv[1]))
    out = {"parts_before": a["parts"], "parts_after": b["parts"], "fit_after": {k: b["fit"].get(k) for k in ("rom_bytes", "rodata_bytes", "ram_image_bytes")},
           "min_sp_before": a["min_sp"], "min_sp_after": b["min_sp"], "rows": []}
    for part in ("real", "dev", "random", "medium", "limits"):
        for fn in FNS:
            k = f"{part}/{fn}"
            x, y = a["tokens_per_call"].get(k), b["tokens_per_call"].get(k)
            if not x or not y:
                continue
            out["rows"].append({"part": part, "fn": fn, "calls": y["calls"], "calls_before": x["calls"], "before": x["chip_mean"], "after": y["chip_mean"],
                                "ratio": round(x["chip_mean"] / y["chip_mean"], 2), "max_before": x["chip_max"], "max_after": y["chip_max"], "echo": y["echo_mean"]})
    json.dump(out, open(os.path.join(HERE, "results", "before_after.json"), "w"), indent=1)
    for r in out["rows"]:
        print(r["part"], r["fn"], r["calls"], r["before"], r["after"], r["ratio"], r["max_before"], r["max_after"])
    print(b["parts"])
    print(out["fit_after"], b["min_sp"], b["graphs_fit"], b["drom_max_fit"])
    print({k: v for k, v in (b.get("fit") or {}).items() if k in ("frontier_label16_R4",)})


if __name__ == "__main__":
    main()
