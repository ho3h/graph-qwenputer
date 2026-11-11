"""How many of Qwen's saved calls take the fast path? A call took the slow path if any pc of `gather` ran. Writes results/fast_path_real.json."""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import attrib as A  # noqa: E402
import fwbox as F  # noqa: E402
import hist as H  # noqa: E402

X, BR = F.X, F.BR


def main():
    src = os.path.join(HERE, "graphlib.c")
    F.set_firmware("fw", src)
    assert A.same_code(X.ELF, F.build_g(src, "fw"))
    att = A.Attrib(os.path.join(F.BUILD, "fw-g.elf"))
    gather = {pc for pc, ch in att.chain.items() if any(n == "gather" for n, _ in ch)}
    assert gather
    T = BR.Text(X.tokenizer_json())
    calls, slow, ex = 0, 0, []
    for jpath in H.real_files():
        meta = json.load(open(os.path.join(os.path.dirname(jpath), "meta.json")))
        g = json.load(open(H.checked(meta["graph"])))
        qs = {x["id"]: x for x in json.load(open(H.checked(meta["questions"])))["questions"]}
        for line in open(jpath):
            r = json.loads(line)
            b = F.Box(g, T, attrib=att)
            for s in qs[r["id"]].get("setup") or []:
                b.call(T.encode(X.template_text(s["fn"], s["args"])))
            for c in r["calls"]:
                b.m.p_tally, b.m.p_ctx = {}, 0
                b.call(c["ids"])
                calls += 1
                if any(pc in gather for _, pc in b.m.p_tally):
                    slow += 1
                    ex.append(c["text"][:200])
    out = {"calls": calls, "slow_path": slow, "examples": ex[:5]}
    json.dump(out, open(os.path.join(HERE, "results", "fast_path_real.json"), "w"), indent=1)
    print(out)


if __name__ == "__main__":
    main()
