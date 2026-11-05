"""Can the comparison fail on these changes? Each mutant is a deliberate bug in fw/graphlib.c, built to fw/build/ and run through
test_m1_fw.py --quick and fuzz_fw.py --seeds 4. Results in results/mutants.json. Run under memguard; finite list.
"""

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "graphlib.c")).read()
PY = sys.executable
MUT = [
    ("tie_rule", "if (cy == by && x < w2[y]) w2[y] = (u16)x;", ""),
    ("stop_when_reached", "if (x == b) { cb = cx; break; }", "if (cst[b]) { cb = scratch[b]; break; }"),
    ("saturation", "if (cy > WSAT) cy = WSAT;\n            if (s) {", "if (s) {"),
    ("full_row", "return r[15] ? END : 15;", "return 15;"),
    ("row_80", "if (CAP_ROW(80)[0]) return 0;", ""),
    ("value_lt", "#define VAL_BAD(c) ((c) == '<')", "#define VAL_BAD(c) (0)"),
    ("name_gt", "#define NAME_BAD(c) (((c) | 2u) == '>' || (c) == '\\n')", "#define NAME_BAD(c) (0)"),
    ("gt_prefix", "#define IS_GT(r) (W0(r) == '>')", "#define IS_GT(r) ((r)[0] == '>')"),
    ("leg_count_precedence", 'if (np < 1 || np > MAX_LEGS || err == 1) { put_s("BADARG legs "); put_span(legs.p, legs.n); return; }\n    if (err) { put_s("NORELATION "); put_span(bad_rel.p, bad_rel.n); return; }',
     'if (err == 2) { put_s("NORELATION "); put_span(bad_rel.p, bad_rel.n); return; }\n    if (np < 1 || np > MAX_LEGS || err == 1) { put_s("BADARG legs "); put_span(legs.p, legs.n); return; }'),
    ("trim_plain", "static inline u32 plain(u32 c) { return c - 33u < 95u; }", "static inline u32 plain(u32 c) { return c - 9u < 119u; }"),
    ("key_from", "if (EQ4(p, 'f', 'r', 'o', 'm')) return K_FRM;", ""),
]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    return r.stdout + r.stderr


def main():
    out = []
    run([PY, os.path.join(HERE, "fuzz_fw.py"), "--firmware", os.path.join(HERE, "graphlib.c"), "--tag", "mut_base", "--seeds", "4", "--workers", "4"])
    fp0 = os.path.join(HERE, "results", "fuzz_mut_base.json")
    base = json.load(open(fp0))
    os.remove(fp0)
    known = {m["where"] for m in base["mismatches"]}             # known divergences (non-ASCII digits and the like) on the unmutated build
    for name, a, b in MUT:
        assert SRC.count(a) == 1, name
        p = os.path.join(HERE, "build", f"mut_{name}.c")
        open(p, "w").write(SRC.replace(a, b))
        tag = f"mut_{name}"
        env_cmd = [PY, os.path.join(HERE, "test_m1_fw.py"), "--firmware", p, "--tag", tag, "--workers", "4", "--quick"]
        run(env_cmd)
        s = json.load(open(os.path.join(HERE, "results", f"m1_{tag}", "m1_quick.summary.json")))
        m1 = {k: v["mismatches"] for k, v in s["parts"].items() if v["mismatches"]}
        run([PY, os.path.join(HERE, "fuzz_fw.py"), "--firmware", p, "--tag", tag, "--seeds", "4", "--workers", "4"])
        fp = os.path.join(HERE, "results", f"fuzz_{tag}.json")
        f = json.load(open(fp))
        new = [m for m in f["mismatches"] if m["where"] not in known]
        fz = {}
        for m in new:
            part = m["where"].split("#")[0].rstrip("0123456789")
            fz[part] = fz.get(part, 0) + 1
        row = {"mutant": name, "m1_quick": m1, "fuzz": fz, "caught": bool(m1 or fz)}
        out.append(row)
        print(row, flush=True)
        shutil.rmtree(os.path.join(HERE, "results", f"m1_{tag}"), ignore_errors=True)
        os.remove(fp)
        json.dump(out, open(os.path.join(HERE, "results", "mutants.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
