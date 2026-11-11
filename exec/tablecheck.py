"""The compiled tables against the IR, with no stream (REGISTRATION.md, "Whole-table check"). Finding 4, condition 1 of the round 2 critical review.

This file rebuilds what every number in the tables means, by its own reading of engine.c, as exact rationals, and compares the result with forms taken directly from the IR nodes. Nothing runs through the engine.

    CHIP_FIRMWARE=... python tablecheck.py --label fw --out results/tablecheck_fw.json
    python tablecheck.py --label fw --corrupt 20261102:1000 --workers 4 --out results/tablecheck_corrupt.json

Independence. It does not import compile_ir.py or cexec.py. It shares with them: the IR objects (core.build, q35.ir), numpy, and the .npz file itself. It repeats two of compile_ir's rules because they have no other source: vh_nrows and h_always. The key in
cached() is repeated so the same file is found. The ROM rows use ref.rom_word, the pre-decode shared by the stock path and the engine.

What it cannot say: that fp32 evaluation in the engine's grouping equals the exact sum at a value never seen, or that the C loops do what this file reads them to do on rows no stream reached. See the DEVLOG.
"""
import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import random
import struct
import sys
import time
from collections import Counter
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402

import numpy as np  # noqa: E402

from chipformer.dsl.graph import ONE  # noqa: E402
from chipformer.q35 import ir as ir_mod  # noqa: E402
from chipformer.q35.ir import FFN, HD, Head  # noqa: E402
from chipformer.rv import core, ref as RF  # noqa: E402
from chipformer.rv import spec as S  # noqa: E402

# engine.c's level record, read from its enum
L_KIND, L_A0, L_A1, L_G0, L_E0, L_NE, L_LAG0, L_LAG1, L_FAN0, L_NH, L_B0, L_B1, L_LV, L_P0, L_P1, L_O0, L_O1, L_WIDTH = range(18)
FLOATS = ("tw", "ec", "ucoef", "o_w", "p_r")
ARRAYS = ("levels", "buckets", "eptr", "tix", "tw", "ec", "aexpr", "gstart", "ua", "ucoef", "uout", "outs", "zexpr", "lag_slot", "lag_dim", "fan_ptr", "fan_h", "fan_row",
          "h_v", "h_always", "vh_a", "vh_beta", "vh_nrows", "vh_S", "vh_v", "vh_z", "v_col", "v_expr", "z_expr", "z_o", "o_col", "o_dim", "o_w", "keep", "p_t", "p_a", "p_b", "p_r")
ZERO, UNIT = Fraction(0), Fraction(1)


# --- the file the executor loads -----------------------------------------------------------------------------------------------------
def program_path(c):
    h = hashlib.sha256(open(os.path.join(HERE, "compile_ir.py"), "rb").read())
    for f in (core.__file__, ir_mod.__file__, os.path.join(os.path.dirname(core.__file__), "spec.py")):
        h.update(open(f, "rb").read())
    h.update(json.dumps(c.stats(), sort_keys=True).encode())
    return os.path.join(HERE, "build", f"program-{h.hexdigest()[:12]}.npz")


def load_program(path):
    z = np.load(path)
    meta = json.loads(str(z["__meta"]))
    return {k: z[k] for k in z.files if k != "__meta"}, meta


def tables_sha(A):
    h = hashlib.sha256()
    for k in sorted(A):
        h.update(k.encode())
        h.update(str(A[k].dtype).encode())
        h.update(A[k].tobytes())
    return h.hexdigest()


# --- from the IR ---------------------------------------------------------------------------------------------------------------------
def form_plain(e):
    """An Expr as {(dim, lag): exact value}. Dim ONE at lag 0 is the constant."""
    out = {}
    for d, cf in e.terms.items():
        v = Fraction(float(cf))
        if v:
            out[(d, 0)] = out.get((d, 0), ZERO) + v
    return {k: v for k, v in out.items() if v}


def form_chan(ch):
    """A channel's expression with its conv taps folded in."""
    out = {}
    for lag, tap in enumerate(ch.taps):
        if not tap:
            continue
        t = Fraction(float(tap))
        for d, cf in ch.expr.terms.items():
            k = (d, lag)
            out[k] = out.get(k, ZERO) + Fraction(float(cf)) * t
    return {k: v for k, v in out.items() if v}


def fkey(f):
    return tuple(sorted(f.items()))


def canonical(c):
    """Per level, in level order: what the tables should say."""
    levels = {}
    forms = {}

    def fid(f):
        return forms.setdefault(fkey(f), len(forms))

    for lv in sorted({n.level for n in c.nodes}):
        nodes = [n for n in c.nodes if n.level == lv]
        if isinstance(nodes[0], FFN):
            assert all(isinstance(n, FFN) for n in nodes)
            units = Counter()
            for n in nodes:
                for cf, a, b in n.terms:
                    units[(Fraction(float(cf)), fid(form_plain(a)), fid(form_plain(b)), n.out)] += 1
            levels[lv] = {"kind": 0, "units": units, "outs": sorted({n.out for n in nodes if n.terms})}
            continue
        assert all(isinstance(n, Head) for n in nodes)
        heads = []
        for n in nodes:
            assert n.n_cols == HD
            vhs = []
            for vd in n.vheads():
                out = Counter()
                for col, d, w in vd.out:
                    if col in vd.z and vd.z[col].terms:
                        out[(col, d, Fraction(float(w)), fid(form_plain(vd.z[col])))] += 1
                vhs.append({"v": {col: fid(form_chan(ch)) for col, ch in vd.v.items()}, "a": fid(form_plain(vd.a)), "beta": None if vd.beta is None else fid(form_plain(vd.beta)), "out": out,
                            "nrows": max(list(n.k) + [1]) + 1})
            heads.append({"q": {s: fid(form_chan(ch)) for s, ch in n.q.items()}, "k": {s: fid(form_chan(ch)) for s, ch in n.k.items()}, "vh": vhs,
                          "always": int(any(vd.a.terms for vd in n.vheads()))})
        levels[lv] = {"kind": 1, "heads": heads, "outs": sorted({d for n in nodes for vd in n.vheads() for _, d, _ in vd.out})}
    frozen = {d for n in c.nodes if isinstance(n, Head) and n.tiny for vh in n.vheads() for _, d, _ in vh.out} | {ONE}
    return {"levels": levels, "forms": forms, "frozen": frozen, "D": len(c.dims), "keep": [int(x) for x in c.keep], "one": ONE,
            "V": sum(len(n.vheads()) for n in c.nodes if isinstance(n, Head)), "names": [d.name for d in c.dims]}


# --- from the tables -----------------------------------------------------------------------------------------------------------------
class Problems:
    def __init__(self):
        self.n = 0
        self.kinds = Counter()
        self.first = []

    def add(self, kind, msg=""):
        self.n += 1
        self.kinds[kind] += 1
        if len(self.first) < 12:
            self.first.append(f"{kind}: {msg}"[:300])


def check(A, meta, can):
    """Returns (problems, counts, unread). `unread`: per array, entries this function never looked at."""
    P = Problems()
    counts = Counter()
    seen = {k: bytearray(len(A[k])) for k in A}
    try:
        _check(A, meta, can, P, counts, seen)
    except (IndexError, KeyError, ValueError, TypeError, AssertionError, ZeroDivisionError) as e:
        P.add("unreadable", f"{type(e).__name__}: {e}")
        return P, counts, {}
    unread = {k: int(len(v) - sum(v)) for k, v in seen.items() if len(v) != sum(v)}
    if unread:                  # a number no entry reaches: the revision after run 1 (REGISTRATION.md)
        P.add("number no entry reaches", str(unread))
    return P, counts, unread


def _check(A, meta, can, P, counts, seen):
    for k in ARRAYS:
        if k not in A:
            P.add("array missing", k)
    extra = set(A) - set(ARRAYS)
    if extra:
        P.add("array unknown", str(sorted(extra)))
    D = can["D"]
    if meta["D"] != D or meta["V"] != can["V"] or meta["one"] != can["one"]:
        P.add("header", f"{meta['D']} {meta['V']} {meta['one']}")
    T = {k: A[k].tolist() for k in ARRAYS}

    def mark(name, a, b=None):
        if b is None:
            seen[name][a] = 1
        elif b > a:
            seen[name][a:b] = b"\x01" * (b - a)

    def ptr(name, i):
        if not 0 <= i < len(T[name]):
            raise IndexError(f"{name}[{i}] out of range")
        return T[name][i]

    # parallel arrays and start arrays
    for group in (("ua", "ucoef", "uout"), ("fan_h", "fan_row"), ("v_col", "v_expr"), ("o_col", "o_dim", "o_w"), ("p_t", "p_a", "p_b", "p_r"), ("lag_slot", "lag_dim"), ("vh_a", "vh_beta", "vh_nrows", "vh_S"), ("tix", "tw")):
        if len({len(T[k]) for k in group}) != 1:
            P.add("lengths", str(group))
    for start, target in (("gstart", "ua"), ("fan_ptr", "fan_h"), ("h_v", "vh_a"), ("vh_v", "v_col"), ("vh_z", "z_expr"), ("z_o", "o_col"), ("eptr", "tix")):
        s = T[start]
        if s[0] != 0 or s[-1] != len(T[target]) or any(s[i] > s[i + 1] for i in range(len(s) - 1)):
            P.add("start array", start)
    if len(T["eptr"]) != len(T["ec"]) + 1:
        P.add("lengths", "eptr ec")
    if len(T["h_v"]) != len(T["h_always"]) + 1:
        P.add("lengths", "h_v h_always")
    if len(T["vh_v"]) != len(T["vh_a"]) + 1 or len(T["vh_z"]) != len(T["vh_a"]) + 1 or len(T["z_o"]) != len(T["z_expr"]) + 1:
        P.add("lengths", "per value head")
    if len(T["levels"]) != len(can["levels"]):
        P.add("levels", f"{len(T['levels'])} records, IR has {len(can['levels'])}")
    if T["keep"] != can["keep"]:
        P.add("keep", "")
    mark("keep", 0, len(T["keep"]))

    fr_cache = {}

    def fr(x):
        v = fr_cache.get(x)
        if v is None:
            v = fr_cache[x] = Fraction(x)
        return v

    eptr, tix, tw, ec = T["eptr"], T["tix"], T["tw"], T["ec"]
    run = Counter()                # running position of each range across levels
    all_mem = set()                # temporaries and lag slots: each mem index has one owner
    forms = can["forms"]
    local = {}

    def fid(f):
        k = fkey(f)
        v = forms.get(k)
        if v is None:
            v = local.setdefault(k, -1 - len(local))
        return v

    # first entries of start arrays and the sentinels are read here
    for start in ("gstart", "fan_ptr", "h_v", "vh_v", "vh_z", "z_o", "eptr"):
        mark(start, 0, len(T[start]))
    levels_list = sorted(can["levels"])
    prev_lv = None
    for li, rec in enumerate(T["levels"]):
        if len(rec) != L_WIDTH:
            P.add("levels", "record width")
        mark("levels", li)
        lv = rec[L_LV]
        if li >= len(levels_list) or lv != levels_list[li]:
            P.add("levels", f"record {li} has level {lv}")
            continue
        if prev_lv is not None and lv <= prev_lv:
            P.add("levels", "order")
        prev_lv = lv
        want = can["levels"][lv]
        if rec[L_KIND] != want["kind"]:
            P.add("level kind", f"level {lv}")
            continue
        # this level's temporaries, in creation order, and lag slots
        for name, a, b in (("p", rec[L_P0], rec[L_P1]), ("buckets", rec[L_B0], rec[L_B1]), ("outs", rec[L_O0], rec[L_O1])):
            if a != run[name] or b < a:
                P.add("range", f"level {lv} {name} {a} {b}, expected to start at {run[name]}")
            run[name] = b
        temps, lags = {}, {}
        if rec[L_KIND] == 1:
            if rec[L_LAG0] != run["lag"] or rec[L_LAG1] < rec[L_LAG0]:
                P.add("range", f"level {lv} lag")
            run["lag"] = rec[L_LAG1]
            for i in range(rec[L_LAG0], rec[L_LAG1]):
                slot, d = ptr("lag_slot", i), ptr("lag_dim", i)
                mark("lag_slot", i), mark("lag_dim", i)
                counts["lag_dims"] += 1
                if not 0 <= d < D or slot < D:
                    P.add("lag", f"level {lv} slot {slot} dim {d}")
                for j in range(3):
                    if slot + j in all_mem:
                        P.add("lag", f"mem {slot + j} has two owners")
                    all_mem.add(slot + j)
                    lags[slot + j] = (d, j + 1)
        elif rec[L_LAG0] or rec[L_LAG1] or rec[L_FAN0] or rec[L_NH]:
            P.add("levels", f"level {lv}: head fields set on an FFN level")
        memo = {}
        for i in range(rec[L_P0], rec[L_P1]):
            t, a, b, r = ptr("p_t", i), ptr("p_a", i), ptr("p_b", i), ptr("p_r", i)
            mark("p_t", i), mark("p_a", i), mark("p_b", i), mark("p_r", i)
            counts["pairs"] += 1
            if t < D or t in all_mem:
                P.add("pair", f"level {lv} target {t}")
            all_mem.add(t)
            fm = {}
            rr = fr(r)
            if r == 0 or abs(math.frexp(r)[0]) != 0.5:
                P.add("pair ratio not a power of two", f"level {lv} pair {i} r {r}")
            for ix, w in ((a, UNIT), (b, rr)):
                if ix < D:
                    if ix in can["frozen"]:
                        P.add("pair on a tiny dim", f"level {lv} dim {ix}")
                    if ix < 0:
                        raise IndexError(f"pair operand {ix}")
                    fm[(ix, 0)] = fm.get((ix, 0), ZERO) + w
                elif ix in lags:
                    fm[lags[ix]] = fm.get(lags[ix], ZERO) + w
                elif ix in memo:
                    for k, v in memo[ix].items():
                        fm[k] = fm.get(k, ZERO) + w * v
                else:
                    P.add("pair operand undefined here", f"level {lv} mem {ix}")
            memo[t] = fm
            temps[t] = 0

        used_temps = set()

        def form(e):
            """Expression e as the engine sums it, in this level's scope."""
            if not 0 <= e < len(ec):
                raise IndexError(f"expression {e}")
            mark("ec", e)
            s, t = eptr[e], eptr[e + 1]
            mark("tix", s, t), mark("tw", s, t)
            out = {}
            if ec[e]:
                out[(0, 0)] = fr(ec[e])
            for i in range(s, t):
                ix = tix[i]
                w = fr(tw[i])
                if ix < D:
                    k = (ix, 0)
                    out[k] = out.get(k, ZERO) + w
                elif ix in lags:
                    k = lags[ix]
                    out[k] = out.get(k, ZERO) + w
                elif ix in memo:
                    used_temps.add(ix)
                    for k, v in memo[ix].items():
                        out[k] = out.get(k, ZERO) + w * v
                else:
                    P.add("term reads a mem index undefined in this level", f"level {lv} expr {e} mem {ix}")
            counts["terms_read"] += t - s
            return {k: v for k, v in out.items() if v}

        # runs of equal length: the engine trusts these, not eptr
        e0, ne = rec[L_E0], rec[L_NE]
        cover = e0
        for bi in range(rec[L_B0], rec[L_B1]):
            n, a, b = ptr("buckets", bi)
            mark("buckets", bi)
            if a != cover or b <= a:
                P.add("bucket", f"level {lv} bucket {bi} covers {a}..{b}, next should be {cover}")
            cover = b
            for e in range(a, b):
                if eptr[e + 1] - eptr[e] != n:
                    P.add("bucket", f"level {lv} expr {e} has {eptr[e + 1] - eptr[e]} terms, run says {n}")
        if cover != e0 + ne:
            P.add("bucket", f"level {lv} runs end at {cover}, forms end at {e0 + ne}")

        outs = T["outs"][rec[L_O0]:rec[L_O1]]
        mark("outs", rec[L_O0], rec[L_O1])
        if outs != want["outs"]:
            P.add("outs", f"level {lv}")

        if rec[L_KIND] == 0:
            a0, a1, g0 = rec[L_A0], rec[L_A1], rec[L_G0]
            if a0 != run["a"] or a1 < a0 or g0 != run["g"]:
                P.add("range", f"level {lv} a or gate range")
            run["a"], run["g"] = a1, g0 + ne
            aid = {}
            for i in range(a0, a1):
                aid[i] = fid(form(ptr("aexpr", i)))
                mark("aexpr", i)
            got = Counter()
            for x in range(ne):
                b = fid(form(e0 + x))
                g = g0 + x
                counts["gates"] += 1
                for u in range(ptr("gstart", g), ptr("gstart", g + 1)):
                    ai, cf, d = ptr("ua", u), ptr("ucoef", u), ptr("uout", u)
                    mark("ua", u), mark("ucoef", u), mark("uout", u)
                    if ai not in aid:
                        P.add("unit's a is outside this level", f"level {lv} unit {u} a {ai}")
                        continue
                    if not 0 <= d < D:
                        P.add("unit output out of range", f"unit {u} dim {d}")
                    got[(fr(cf), aid[ai], b, d)] += 1
                    counts["units"] += 1
            if got != want["units"]:
                miss = want["units"] - got
                more = got - want["units"]
                P.add("units", f"level {lv}: {sum(miss.values())} expected units not in the tables, {sum(more.values())} in the tables not in the IR; first missing out dim {[k[3] for k in list(miss)[:3]]}, first extra {[k[3] for k in list(more)[:3]]}")
        else:
            z0, z1, h0, f0, nh = rec[L_A0], rec[L_A1], rec[L_G0], rec[L_FAN0], rec[L_NH]
            if z0 != run["z"] or z1 < z0 or h0 != run["h"] or f0 != run["fan"]:
                P.add("range", f"level {lv} z, head or fan range")
            run["z"], run["h"], run["fan"] = z1, h0 + nh, f0 + ne
            if nh != len(want["heads"]) or nh > 32:
                P.add("heads", f"level {lv} has {nh}, IR {len(want['heads'])}")
            got_q = [{} for _ in range(nh)]
            got_k = [{} for _ in range(nh)]
            for x in range(ne):
                f = fid(form(e0 + x))
                c_ = f0 + x
                counts["channels"] += 1
                for j in range(ptr("fan_ptr", c_), ptr("fan_ptr", c_ + 1)):
                    h, rk = ptr("fan_h", j), ptr("fan_row", j)
                    mark("fan_h", j), mark("fan_row", j)
                    if not 0 <= h < nh:
                        P.add("fan head", f"level {lv} {h}")
                        continue
                    row, kind = rk & 0xFFFF, rk >> 16
                    if kind not in (0, 1):
                        P.add("fan kind", f"level {lv} {kind}")
                        continue
                    tgt = got_k[h] if kind else got_q[h]
                    if row in tgt:
                        P.add("fan twice", f"level {lv} head {h} row {row}")
                    tgt[row] = f
                    counts["fan"] += 1
            zset = set()
            for i in range(z0, z1):
                zset.add(ptr("zexpr", i))
                mark("zexpr", i)
            zform = {e: fid(form(e)) for e in zset}
            for hh in range(min(nh, len(want["heads"]))):
                h = h0 + hh
                wh = want["heads"][hh]
                mark("h_always", h)
                if ptr("h_always", h) != wh["always"]:
                    P.add("h_always", f"level {lv} head {hh}")
                if got_q[hh] != wh["q"]:
                    P.add("queries", f"level {lv} head {hh}")
                if got_k[hh] != wh["k"]:
                    P.add("keys", f"level {lv} head {hh}")
                vhs = list(range(ptr("h_v", h), ptr("h_v", h + 1)))
                if len(vhs) != len(wh["vh"]):
                    P.add("value heads", f"level {lv} head {hh}: {len(vhs)} vs {len(wh['vh'])}")
                for x, vh in enumerate(vhs[:len(wh["vh"])]):
                    wv = wh["vh"][x]
                    counts["value_heads"] += 1
                    mark("vh_a", vh), mark("vh_beta", vh), mark("vh_S", vh), mark("vh_nrows", vh)
                    if ptr("vh_S", vh) != vh:
                        P.add("vh_S", f"value head {vh} state {T['vh_S'][vh]}")
                    if ptr("vh_nrows", vh) != wv["nrows"]:
                        P.add("vh_nrows", f"value head {vh}")
                    ea = ptr("vh_a", vh)
                    a_f = fid({}) if ea == -1 else fid(form(ea))
                    if ea < -1 or a_f != wv["a"]:
                        P.add("decay", f"value head {vh}")
                    eb = ptr("vh_beta", vh)
                    if eb < -1:
                        P.add("write gate", f"value head {vh}")
                    b_f = None if eb == -1 else fid(form(eb))
                    if b_f != wv["beta"]:
                        P.add("write gate", f"value head {vh}")
                    got_v = {}
                    for i in range(ptr("vh_v", vh), ptr("vh_v", vh + 1)):
                        col = ptr("v_col", i)
                        mark("v_col", i), mark("v_expr", i)
                        if col in got_v or not 0 <= col < HD:
                            P.add("value column", f"value head {vh} col {col}")
                        got_v[col] = fid(form(ptr("v_expr", i)))
                        counts["value_columns"] += 1
                    if got_v != wv["v"]:
                        P.add("values", f"value head {vh}")
                    got_o = Counter()
                    for zg in range(ptr("vh_z", vh), ptr("vh_z", vh + 1)):
                        ze = ptr("z_expr", zg)
                        mark("z_expr", zg)
                        if ze not in zform:
                            P.add("z outside this level's list", f"value head {vh} expr {ze}")
                            continue
                        for o in range(ptr("z_o", zg), ptr("z_o", zg + 1)):
                            col, d, w = ptr("o_col", o), ptr("o_dim", o), ptr("o_w", o)
                            mark("o_col", o), mark("o_dim", o), mark("o_w", o)
                            got_o[(col, d, fr(w), zform[ze])] += 1
                            counts["head_outputs"] += 1
                    if got_o != wv["out"]:
                        P.add("head outputs", f"value head {vh}")
        unused = set(temps) - used_temps
        if unused:                      # a temporary read only by a later temporary still counts as used
            for i in range(rec[L_P0], rec[L_P1]):
                for ix in (T["p_a"][i], T["p_b"][i]):
                    unused.discard(ix)
            if unused:
                P.add("temporary never read", f"level {lv}: {sorted(unused)[:5]}")
    if len(all_mem) != meta["n_mem"] - D or (all_mem and (min(all_mem) != D or max(all_mem) != meta["n_mem"] - 1)):
        P.add("mem", f"{len(all_mem)} owned, header says {meta['n_mem'] - D}")
    for name, array, length in (("p", "p_t", len(T["p_t"])), ("buckets", "buckets", len(T["buckets"])), ("outs", "outs", len(T["outs"])), ("a", "aexpr", len(T["aexpr"])), ("g", "gstart", len(T["gstart"]) - 1),
                                ("z", "zexpr", len(T["zexpr"])), ("h", "h_always", len(T["h_always"])), ("fan", "fan_ptr", len(T["fan_ptr"]) - 1), ("lag", "lag_slot", len(T["lag_slot"]))):
        if run[name] != length:
            P.add("range", f"{array}: levels cover {run[name]} of {length}")
    counts["forms_expected"] = len(forms)
    counts["forms_not_in_ir"] = len(local)


# --- each firmware's numbers: the ROM and DROM rows in the heads -----------------------------------------------------------------------
def elf_regions(path):
    """Own reader. {rom words, drom bytes} from the PT_LOAD segments."""
    b = open(path, "rb").read()
    assert b[:4] == b"\x7fELF" and b[4] == 1
    phoff = struct.unpack_from("<I", b, 0x1C)[0]
    phentsize, phnum = struct.unpack_from("<HH", b, 0x2A)
    rom, drom = bytearray(), bytearray()
    for i in range(phnum):
        kind, off, vaddr, _, filesz, memsz, _, _ = struct.unpack_from("<8I", b, phoff + i * phentsize)
        if kind != 1 or not memsz:
            continue
        blob = b[off:off + filesz] + bytes(memsz - filesz)
        for buf, base, size in ((rom, S.ROM_BASE, 4 * S.ROM_WORDS), (drom, S.DROM_BASE, 4 * S.DROM_WORDS)):
            if base <= vaddr and vaddr + len(blob) <= base + size:
                end = vaddr - base + len(blob)
                buf.extend(bytes(max(0, end - len(buf))))
                buf[vaddr - base:end] = blob
    rom.extend(bytes(-len(rom) % 4))
    return [int.from_bytes(rom[i:i + 4], "little") for i in range(0, len(rom), 4)], bytes(drom)


def rows_to_words(init, total):
    """The inverse of the head layout of a byte table, by this file's own arithmetic: word index -> head, value head, row pair, half, word in the row."""
    n_heads = total >> 11
    per = total // n_heads
    words = np.zeros(total, np.int64)
    for h, vh in enumerate(init):
        for x, rows in enumerate(vh):
            base = h * per + x * (per // 2)
            for wl in range(per // 2):
                pp, half, k = wl >> 4, wl >> 3 & 1, wl & 7
                row = rows[pp + 64 * half]
                v = 0
                for b in range(4):
                    v |= int(row[2 + 32 * half + 4 * k + b]) << (8 * b)
                words[base + wl] = v
    return words


def check_rom_rows(L, elf_path):
    """Rows the firmware fills, against the ELF. The DROM's front is the graph image, so only the ELF's read-only data is looked for in it."""
    m = C.X.machine_for(json.load(open(os.path.join(C.X210, "host", "test", "tiny.graph.json"))))
    core.snapshot(L.c, m)
    words, rodata = elf_regions(elf_path)
    want = np.zeros(S.ROM_WORDS, np.int64)
    for i, w in enumerate(words):
        want[i] = RF.rom_word(w, S.ROM_BASE + 4 * i) if w else 0
    got = rows_to_words([L.c.tables[f"rom{h}"].init for h in range(S.ROM_WORDS >> 11)], S.ROM_WORDS)
    gotd = rows_to_words([L.c.tables[f"drom{h}"].init for h in range(S.DROM_WORDS >> 11)], S.DROM_WORDS)
    db = gotd.astype("<u4").tobytes()
    used_heads = sorted({i >> 11 for i in np.nonzero(want)[0].tolist()})
    return {"elf_sha256": hashlib.sha256(open(elf_path, "rb").read()).hexdigest(), "rom_words_in_elf": len(words), "rom_words_nonzero": int((want != 0).sum()), "rom_words_differing": int((got != want).sum()),
            "rom_heads_holding_code": used_heads, "drom_bytes_in_elf": len(rodata), "drom_bytes_equal_machine": db[:len(m.drom)] == m.drom, "drom_tail_zero": not any(db[len(m.drom):]), "elf_rodata_found_in_drom": rodata in m.drom if rodata else None}


# --- the test of the check -------------------------------------------------------------------------------------------------------------
def new_value(rng, name, old):
    if name in FLOATS:
        how = rng.choice(("double", "negate", "plus_bit", "zero"))
        if old == 0:
            return "from_zero", rng.choice((1.0, 2.0**-14, -1.0, 128.0))
        return how, {"double": old * 2, "negate": -old, "plus_bit": old * (1 + 1 / 128), "zero": 0.0}[how]
    how = rng.choice(("plus_one", "minus_one", "flip_bit"))
    new = {"plus_one": old + 1, "minus_one": old - 1, "flip_bit": old ^ (1 << rng.randrange(9))}[how]
    return how, new


def seeded_cases(A, seed, total):
    rng = random.Random(seed)
    names = sorted(ARRAYS)
    sizes = [A[k].size for k in names]
    picks = []
    for k in names:
        for _ in range(10):
            picks.append((k, rng.randrange(A[k].size)))
    while len(picks) < total:
        k = rng.choices(names, weights=sizes)[0]
        picks.append((k, rng.randrange(A[k].size)))
    out = []
    for k, i in picks:
        old = A[k].flat[i].item()
        how, new = new_value(rng, k, old)
        if k == "tix":
            new = new % 65536
        if float(np.array(new, A[k].dtype)) == float(old):       # must change the number
            new = old + 1 if k not in FLOATS else (old * 2 if old else 1.0)
            how += "+"
        out.append({"source": f"seed:{seed}", "table": k, "index": i, "old": old, "new": float(new) if k in FLOATS else int(new), "how": how})
    return out


def earlier_cases(A):
    out = []
    a = json.load(open(os.path.join(HERE, "results", "negative_tables_tinyten.json")))["mutations"]
    b = json.load(open(os.path.join(HERE, "results", "negative_tables_dev.json")))["mutations"]
    for x, y in zip(a, b):
        assert (x["table"], x["index"], x["new"]) == (y["table"], y["index"], y["new"]), "the two earlier lists differ"
    for m in a:
        out.append({"source": "negative_tables_tinyten", "table": m["table"], "index": m["index"], "old": m["old"], "new": m["new"], "how": m["how"], "stream_caught": m["caught"]})
    for m in json.load(open(os.path.join(C.X210, "edits", "results", "negative_machine.json")))["corrupted_engine"]:
        out.append({"source": "edits/negative_machine", "table": m["table"], "index": m["index"], "old": m["old"], "new": m["new"], "how": m["how"], "stream_caught": m["caught"]})
    for m in out:
        m["old_matches_program"] = A[m["table"]][m["index"]].item() == m["old"]
    return out


_W = {}


def _init():
    L = C.Lite(tokenizer=False)
    A, meta = load_program(program_path(L.c))
    _W.update(A=A, meta=meta, can=canonical(L.c))


def _one(case):
    A, meta, can = _W["A"], _W["meta"], _W["can"]
    arr = A[case["table"]]
    arr = arr.copy()
    arr.flat[case["index"]] = case["new"]
    B = dict(A)
    B[case["table"]] = arr
    t0 = time.time()
    P, _, unread = check(B, meta, can)
    return {**case, "caught": P.n > 0, "n_problems": P.n, "kinds": dict(P.kinds), "first": P.first[:1], "unread": unread, "seconds": round(time.time() - t0, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--corrupt", default=None, help="seed:total, on top of the earlier cases")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None, help="only the first N cases (a timing run)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    L = C.Lite(tokenizer=False)
    path = program_path(L.c)
    A, meta = load_program(path)
    print("program", os.path.basename(path), "build", round(time.time() - t0, 1), flush=True)
    if a.corrupt:
        sd, total = a.corrupt.split(":")
        cases = earlier_cases(A) + seeded_cases(A, int(sd), int(total))
        if a.limit:
            cases = cases[:a.limit]
        res = {"program": os.path.basename(path), "tables_sha256": tables_sha(A), "seed": int(sd), "n_cases": len(cases), "cases": []}
        ctx = mp.get_context("spawn")
        with ctx.Pool(a.workers, initializer=_init) as pool:
            for k, r in enumerate(pool.imap(_one, cases, chunksize=4)):
                res["cases"].append(r)
                if (k + 1) % 50 == 0 or k + 1 == len(cases):
                    print(k + 1, "of", len(cases), "caught", sum(x["caught"] for x in res["cases"]), f"{time.time() - t0:.0f}s", flush=True)
                    json.dump(res, open(a.out, "w"), indent=0)
        rs = res["cases"]
        res["caught"], res["tried"] = sum(x["caught"] for x in rs), len(rs)
        res["earlier"] = {"tried": sum(x["source"] != f"seed:{sd}" for x in rs), "caught": sum(x["caught"] for x in rs if x["source"] != f"seed:{sd}"),
                          "stream_caught_then": sum(bool(x.get("stream_caught")) for x in rs), "old_value_matched": sum(bool(x.get("old_matches_program")) for x in rs if x["source"] != f"seed:{sd}")}
        res["by_table"] = {k: {"tried": sum(x["table"] == k for x in rs), "caught": sum(x["caught"] for x in rs if x["table"] == k)} for k in sorted({x["table"] for x in rs})}
        res["missed"] = [x for x in rs if not x["caught"]]
        res["seconds"] = round(time.time() - t0)
        json.dump(res, open(a.out, "w"), indent=0)
        print(json.dumps({k: res[k] for k in ("caught", "tried", "earlier", "seconds")}), "missed", len(res["missed"]), flush=True)
        return
    t1 = time.time()
    can = canonical(L.c)
    t2 = time.time()
    P, counts, unread = check(A, meta, can)
    t3 = time.time()
    elf_path = C.X.build_elf()
    res = {"label": a.label, "program": os.path.basename(path), "tables_sha256": tables_sha(A), "array_sizes": {k: int(len(A[k])) for k in sorted(A)}, "total_numbers": int(sum(A[k].size for k in A)),
           "ir_stats": L.c.stats(), "seconds": {"canonical": round(t2 - t1, 2), "check": round(t3 - t2, 2)}, "problems": P.n, "kinds": dict(P.kinds), "first": P.first, "counts": dict(counts), "unread": unread}
    res["firmware"] = check_rom_rows(L, elf_path)
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "array_sizes"})[:3000], flush=True)
    sys.exit(0 if P.n == 0 and res["firmware"]["rom_words_differing"] == 0 else 3)


if __name__ == "__main__":
    main()
