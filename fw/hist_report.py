"""Turn results/hist_raw_<tag>.json.gz into results/hist_<tag>.json: stages and C functions per SPEC function.

Stages (a token goes to the first that matches, reading its full chain: call sites plus DWARF inlining):
  print       under put*, print_path, put_edge
  capture     gather (and the capture walk of a firmware that has one)
  parse_call  call and its tag scanners: <function=...>, </function>, <parameter=...>, name compare, BADARG checks
  parse_args  splitting and checking argument text inside f_*: chase's legs, parse_int, steps_arg, direction
  resolve     rel_arg / rel_lookup, node_arg / node_or_print / parse_handle / label_eq, ghash
  work        the walk or search itself: everything else under f_*
  frame       main: park, GO resume (the GO token itself is counted apart as `go`)
"""

import argparse
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import attrib as A  # noqa: E402

PRINT = {"put", "put_s", "put_span", "put_num", "put_lab", "put_fmt", "put_edge", "print_path"}
CAPTURE = {"gather", "fast_parse", "name_rows", "copy_name", "copy_val"}
RESOLVE = {"rel_arg", "rel_lookup", "node_arg", "node_or_print", "parse_handle", "label_eq", "ghash"}
ARGS = {"parse_int", "steps_arg"}
OPCLASS = {"LBU": "load_byte", "LB": "load_byte", "LHU": "load_half", "LH": "load_half", "LW": "load_word",
           "SB": "store_byte", "SH": "store_half", "SW": "store_word", "BEQ": "branch", "BNE": "branch", "BLT": "branch",
           "BGE": "branch", "BLTU": "branch", "BGEU": "branch", "JAL": "jump", "JALR": "jump", "ECALL": "ecall",
           "MUL": "mul", "DIVU": "div", "REMU": "div", "DIV": "div", "REM": "div"}


def line_ranges(src):
    """Source lines of f_chase's leg parsing and f_neighbours' direction check: parse_args, not work."""
    lines = open(src).read().split("\n")
    out = {}
    for fn, a, b in (("f_chase", "// pass 1: count", "u32 h = node_or_print(start)"),
                     ("f_neighbours", "u32 d = 0;", "u32 h = node_or_print(node)")):
        s = next(i for i, ln in enumerate(lines) if a in ln and i > next(j for j, l in enumerate(lines) if f"void {fn}(" in l))
        e = next(i for i, ln in enumerate(lines) if b in ln and i > s)
        out[fn] = (s + 1, e + 1)
    return out


def stage(chain, ranges):
    names = [n for n, _ in chain]
    s = set(names)
    if s & PRINT:
        return "print"
    if s & CAPTURE:
        return "capture"
    fi = next((i for i, n in enumerate(names) if n.startswith("f_")), None)
    if fi is None:
        return "parse_call" if ("call" in s or s & {"at", "find_lit", "named_at", "next_param", "eq_lit"}) else "frame"
    tail = names[fi:]
    t = set(tail)
    if t & RESOLVE:
        return "resolve"
    if t & ARGS:
        return "parse_args"
    r = ranges.get(names[fi])
    if r:
        # the deepest frame inside f_x that has a line in f_x: the line says which part of f_x this is
        ln = chain[fi][1]
        if r[0] <= ln <= r[1]:
            return "parse_args"
    return "work"


def expand(ctx, pc, att):
    out = []
    for c in ctx:
        out += att.chain[c]
    return out + att.chain[pc]


def report(tag, src, raw_path, out_path):
    raw = json.load(gzip.open(raw_path, "rt"))
    att = A.Attrib(os.path.join(HERE, "build", tag + "-g.elf"))
    ranges = line_ranges(src)
    res = {"tag": tag, "src": os.path.relpath(src, os.path.dirname(HERE)), "seconds": raw["seconds"], "notes": raw["notes"],
           "functions": {}}
    tot = defaultdict(lambda: None)
    memo = {}
    groups = dict(raw["groups"])
    # "all" pools the two parts, one per function
    for gr in sorted(groups):
        k = groups[gr]
        st, fn_, sym, ops, st_ops, lines = Counter(), Counter(), Counter(), Counter(), defaultdict(Counter), Counter()
        st_rec = Counter()
        for ctx, pc, n, rec in k["t"]:
            key = (tuple(ctx), pc)
            v = memo.get(key)
            if v is None:
                ch = expand(ctx, pc, att)
                v = memo[key] = (stage(ch, ranges), ch[-1][0], ch[-1][1])
            s_, inner, ln = v
            st[s_] += n
            st_rec[s_] += rec
            fn_[inner] += n
            lines[f"{inner}:{ln}"] += n
            sym[att.sym[pc]] += n
            o = OPCLASS.get(att.op[pc], "alu")
            ops[o] += n
            st_ops[s_][o] += n
        calls, chip = k["calls"], k["chip"]
        st["go"] += calls
        counted = sum(st.values())
        chips = sorted(c for c, _ in k["samples"])
        res["functions"][gr] = {
            "calls": calls, "chip_mean": round(chip / calls, 1), "chip_median": chips[len(chips) // 2], "chip_max": k["chip_max"],
            "echo_mean": round(k["echo"] / calls, 1), "cap_tokens_mean": round(k["cap"] / calls, 2),
            "cap_bytes_mean": round(k["cap_bytes"] / calls, 2), "instr_mean": round(k["records"] / calls, 1),
            "counted_equals_chip": counted == chip, "ctx_not_root_at_halt": k["ctx_bad"],
            "stage_tokens_mean": {a: round(b / calls, 1) for a, b in st.most_common()},
            "stage_share": {a: round(b / chip, 4) for a, b in st.most_common()},
            "stage_tok_per_instr": {a: round(st[a] / st_rec[a], 3) for a in st_rec if st_rec[a]},
            "c_function_tokens_mean": {a: round(b / calls, 1) for a, b in fn_.most_common(30)},
            "symtab_tokens_mean": {a: round(b / calls, 1) for a, b in sym.most_common(12)},
            "op_tokens_mean": {a: round(b / calls, 1) for a, b in ops.most_common()},
            "stage_ops_mean": {a: {o: round(c / calls, 1) for o, c in b.most_common(5)} for a, b in st_ops.items()},
            "top_lines_mean": {a: round(b / calls, 1) for a, b in lines.most_common(15)},
        }
    json.dump(res, open(out_path, "w"), indent=1)
    return res


def table(res):
    print(f"{'function':22} {'calls':>6} {'mean':>8} {'capt':>6} {'parse':>6} {'args':>6} {'reslv':>6} {'work':>6} {'print':>6} {'frame':>6}  ok")
    for gr, f in res["functions"].items():
        s = f["stage_share"]
        print(f"{gr:22} {f['calls']:6} {f['chip_mean']:8.0f} " + " ".join(f"{100 * s.get(k, 0):5.1f}%" for k in ("capture", "parse_call", "parse_args", "resolve", "work", "print"))
              + f" {100 * (s.get('frame', 0) + s.get('go', 0)):5.1f}%  {f['counted_equals_chip']} {f['ctx_not_root_at_halt']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    suf = "_quick" if a.quick else ""
    res = report(a.tag, os.path.abspath(a.src), os.path.join(HERE, "results", f"hist_raw_{a.tag}{suf}.json.gz"),
                 os.path.join(HERE, "results", f"hist_{a.tag}{suf}.json"))
    table(res)
