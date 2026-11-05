"""Compile a q35 circuit graph (the IR) into the flat tables engine.c interprets.

Memory is one fp32 array: mem[0:D] is the residual in IR dims, mem[D:] the lag windows (three slots per dim a conv tap reads, per head level). Every linear
form is an expression in one table (terms: mem index, weight); within a level each distinct form exists once. The rules follow q35.ir.evaluate:

  FFN level   y[out] += coef * bf16(max(bf16(128 b), 0) * bf16(a / 128)), then x[d] = bf16(x[d] + bf16(y[d]))
  head level  each value head: decay, write (key one-hot, beta), read (multi-hot, normed by the ref columns), output columns * relu(z) * w

Nothing here decides a value; a wrong table is what the saved negative control looks for.
"""
import numpy as np

from chipformer.dsl.graph import ONE
from chipformer.q35.ir import FFN, HD, Head

FFN_LEVEL, HEAD_LEVEL = 0, 1


def fp32(x):
    v = float(x)
    f = float(np.float32(v))
    assert f == v, f"weight {v!r} is not an fp32 value"
    return f


class Tables:
    def __init__(self, D):
        self.D = D
        self.eptr = [0]
        self.ec = []
        self.tix, self.tw = [], []
        self.n_mem = D
        self.lag_slot = {}

    def expr(self, terms):
        """terms: {mem index: weight}. New row in the term table. The constant dim ONE (mem[0], always 1) becomes the expression's constant."""
        c0 = 0.0
        for k, v in terms.items():
            if k == ONE:
                c0 = v
            elif v:
                self.tix.append(k)
                self.tw.append(v)
        self.ec.append(c0)
        self.eptr.append(len(self.tix))
        return len(self.eptr) - 2

    def batch(self, forms, buckets):
        """Append forms (in length order) contiguously and record runs of equal length, so the engine evaluates them with no per-expression branch. Returns the id of each form, in the order given."""
        order = sorted(range(len(forms)), key=lambda i: sum(1 for k in forms[i] if k != ONE))
        ids = [None] * len(forms)
        for i in order:
            ids[i] = self.expr(forms[i])
            n = self.eptr[-1] - self.eptr[-2]
            if buckets and buckets[-1][0] == n and buckets[-1][2] == ids[i]:
                buckets[-1][2] = ids[i] + 1
            else:
                buckets.append([n, ids[i], ids[i] + 1])
        return ids, order


def lagged(ch, D, lag_of):
    """A channel's expression over mem indices, its conv taps folded in. lag_of(lag, d) is the mem index of d at that lag."""
    out = {}
    for lag, tap in enumerate(ch.taps):
        if not tap:
            continue
        for d, cf in ch.expr.terms.items():
            k = d if lag == 0 else lag_of(lag, d)
            out[k] = out.get(k, 0.0) + fp32(float(cf) * float(tap))
    return out


def plain(e):
    return {d: fp32(cf) for d, cf in e.terms.items()}


def cse(exprs, next_mem, frozen, min_uses=2):
    """Paar's greedy sharing over one level: repeatedly make the most used pair (w_a x_a + w_b x_b, up to a common factor) a temporary t = x_a + r x_b, and replace it. exprs: list of
    {mem index: weight}. Terms on frozen indices (dims that may hold tiny counters, read with huge weights) stay as they are, so those sums keep every term. Returns (exprs, pairs [(t, a, b, r)], next_mem).
    Only pairs with a power-of-two ratio are made, so r is exact; each term's value is an integer or a dyadic value by the IR's own check."""
    import heapq
    exprs = [dict(e) for e in exprs]

    def ok(a, wa, b, wb):
        if a in frozen or b in frozen:
            return None
        r = wb / wa
        m, e = np.frexp(abs(r))
        if m != 0.5 or abs(wa) > 2.0**20 or abs(wb) > 2.0**20:
            return None
        return float(r)

    where = {}
    for i, e in enumerate(exprs):
        items = sorted(e.items())
        for x in range(len(items)):
            a, wa = items[x]
            if a in frozen:
                continue
            for y in range(x + 1, len(items)):
                b, wb = items[y]
                r = ok(a, wa, b, wb)
                if r is not None:
                    where.setdefault((a, b, r), set()).add(i)
    heap = [(-len(v), k) for k, v in where.items() if len(v) >= min_uses]
    heapq.heapify(heap)
    pairs = []
    while heap:
        neg, k = heapq.heappop(heap)
        cur = where.get(k)
        if not cur or len(cur) < min_uses:
            continue
        if len(cur) != -neg:
            heapq.heappush(heap, (-len(cur), k))
            continue
        a, b, r = k
        t = next_mem
        next_mem += 1
        pairs.append((t, a, b, r))
        touched = {}
        for i in list(cur):
            e = exprs[i]
            wa = e.pop(a)
            e.pop(b)
            rest = sorted(e.items())
            for c, wc in rest:                     # the old pairs of a and b with the rest of this expression go
                for (p, wp) in ((a, wa), (b, wa * r)):
                    x, wx, y, wy = (p, wp, c, wc) if p < c else (c, wc, p, wp)
                    rr = ok(x, wx, y, wy)
                    if rr is not None:
                        s_ = where.get((x, y, rr))
                        if s_ is not None:
                            s_.discard(i)
            e[t] = wa
            for c, wc in rest:                     # t > every index so far
                rr = ok(c, wc, t, wa)
                if rr is not None:
                    n = where.setdefault((c, t, rr), set())
                    n.add(i)
                    touched[(c, t, rr)] = len(n)
        del where[k]
        for kk, n in touched.items():
            if n >= min_uses:
                heapq.heappush(heap, (-n, kk))
    return exprs, pairs, next_mem


def compile_ir(c):
    D = len(c.dims)
    t = Tables(D)
    P = {k: [] for k in ("gstart", "ua", "ucoef", "uout", "outs", "lag_slot", "lag_dim", "aexpr", "zexpr",
                         "fan_ptr", "fan_h", "fan_row", "h_v", "h_always", "vh_a", "vh_beta", "vh_nrows", "vh_S", "vh_v", "vh_z",
                         "v_col", "v_expr", "z_expr", "z_o", "o_col", "o_dim", "o_w", "p_t", "p_a", "p_b", "p_r")}
    # dims that may hold a tiny counter (2^-n, read with huge weights): their terms are never moved into a shared sum
    frozen = {d for n in c.nodes if isinstance(n, Head) and n.tiny for vh in n.vheads() for _, d, _ in vh.out}
    frozen.add(ONE)
    levels, buckets = [], []
    V = 0
    stats = {"terms_before": 0, "pairs": 0}

    def share(exprs):
        stats["terms_before"] += sum(len(e) for e in exprs)
        out, pairs, t.n_mem = cse(exprs, t.n_mem, frozen)
        stats["pairs"] += len(pairs)
        p0 = len(P["p_t"])
        for tt, a, b, r in pairs:
            P["p_t"].append(tt)
            P["p_a"].append(a)
            P["p_b"].append(b)
            P["p_r"].append(fp32(r))
        return out, p0, len(P["p_t"])

    for lv in sorted({n.level for n in c.nodes}):
        nodes = [n for n in c.nodes if n.level == lv]
        b0 = len(buckets)
        if isinstance(nodes[0], FFN):
            assert all(isinstance(n, FFN) for n in nodes)
            aidx, groups = {}, {}
            for n in nodes:
                for cf, a, b in n.terms:
                    ak = tuple(sorted(plain(a).items()))
                    if ak not in aidx:
                        aidx[ak] = len(aidx)
                    groups.setdefault(tuple(sorted(plain(b).items())), []).append((aidx[ak], fp32(cf), n.out))
            akeys, gkeys = list(aidx), list(groups)
            forms, p0, p1 = share([dict(k) for k in akeys] + [dict(k) for k in gkeys])
            a0 = len(P["aexpr"])
            for f in forms[: len(akeys)]:
                P["aexpr"].append(t.expr(f))
            ids, order = t.batch(forms[len(akeys):], buckets)
            g0 = len(P["gstart"])
            e0 = ids[order[0]]
            for x, i in enumerate(order):
                assert ids[i] == e0 + x
                P["gstart"].append(len(P["ua"]))
                for ai, cf, d in groups[gkeys[i]]:
                    P["ua"].append(a0 + ai)
                    P["ucoef"].append(cf)
                    P["uout"].append(d)
            o0 = len(P["outs"])
            P["outs"].extend(sorted({d for us in groups.values() for _, _, d in us}))
            levels.append([FFN_LEVEL, a0, len(P["aexpr"]), g0, e0, len(gkeys), 0, 0, 0, 0, b0, len(buckets), lv, p0, p1, o0, len(P["outs"])])
            continue
        assert all(isinstance(n, Head) for n in nodes)
        l0 = len(P["lag_dim"])
        lag_slots = {}

        def lag_of(lag, d):
            if d not in lag_slots:
                lag_slots[d] = t.n_mem
                t.n_mem += 3
                P["lag_dim"].append(d)
                P["lag_slot"].append(lag_slots[d])
            return lag_slots[d] + lag - 1

        ckeys, zkeys, fans = {}, {}, {}

        def chan(ch, h, row, kind):
            k = tuple(sorted(lagged(ch, D, lag_of).items()))
            cid = ckeys.setdefault(k, len(ckeys))
            fans.setdefault(cid, []).append((h, row | kind << 16))

        z_pending = []                                # (index in z_expr, key of its form), filled after sharing
        h0 = len(P["h_v"])
        for hi, n in enumerate(nodes):
            assert n.n_cols == HD
            P["h_v"].append(len(P["vh_a"]))
            P["h_always"].append(int(any(vd.a.terms for vd in n.vheads())))
            for s, ch in n.q.items():
                chan(ch, hi, s, 0)
            for s, ch in n.k.items():
                chan(ch, hi, s, 1)
            for vd in n.vheads():
                P["vh_S"].append(V)
                V += 1
                P["vh_a"].append(t.expr(plain(vd.a)) if vd.a.terms else -1)
                P["vh_beta"].append(-1 if vd.beta is None else t.expr(plain(vd.beta)))
                P["vh_nrows"].append(max(list(n.k) + [1]) + 1)       # load_init raises this if a snapshot sets a later row
                P["vh_v"].append(len(P["v_col"]))
                P["vh_z"].append(len(P["z_expr"]))
                for col, ch in vd.v.items():
                    P["v_col"].append(col)
                    P["v_expr"].append(t.expr(lagged(ch, D, lag_of)))
                by_z = {}
                for col, d, w in vd.out:
                    if col in vd.z and vd.z[col].terms:
                        by_z.setdefault(tuple(sorted(plain(vd.z[col]).items())), []).append((col, d, fp32(w)))
                for zk, os_ in by_z.items():
                    z_pending.append((len(P["z_expr"]), zkeys.setdefault(zk, len(zkeys))))
                    P["z_expr"].append(-1)
                    P["z_o"].append(len(P["o_col"]))
                    for col, d, w in os_:
                        P["o_col"].append(col)
                        P["o_dim"].append(d)
                        P["o_w"].append(w)
        cl, zl = list(ckeys), list(zkeys)
        forms, p0, p1 = share([dict(k) for k in cl] + [dict(k) for k in zl])
        cforms, zforms = forms[: len(cl)], forms[len(cl):]
        ids, order = t.batch(cforms, buckets)
        e0 = ids[order[0]]
        f0 = len(P["fan_ptr"])
        for x, i in enumerate(order):
            assert ids[i] == e0 + x
            P["fan_ptr"].append(len(P["fan_h"]))
            for hi, rk in fans[i]:
                P["fan_h"].append(hi)
                P["fan_row"].append(rk)
        z0 = len(P["zexpr"])
        zid = [t.expr(f) for f in zforms]
        P["zexpr"].extend(zid)
        for j, zi in z_pending:
            P["z_expr"][j] = zid[zi]
        o0 = len(P["outs"])
        P["outs"].extend(sorted({d for n in nodes for vd in n.vheads() for _, d, _ in vd.out}))
        levels.append([HEAD_LEVEL, z0, len(P["zexpr"]), h0, e0, len(cl), l0, len(P["lag_dim"]), f0, len(nodes), b0, len(buckets), lv, p0, p1, o0, len(P["outs"])])
    # sentinels so every start array can be read at [i + 1]
    P["gstart"].append(len(P["ua"]))
    P["fan_ptr"].append(len(P["fan_h"]))
    P["h_v"].append(len(P["vh_a"]))
    P["vh_v"].append(len(P["v_col"]))
    P["vh_z"].append(len(P["z_expr"]))
    P["z_o"].append(len(P["o_col"]))
    fl = ("ucoef", "o_w", "p_r")
    A = {k: np.array(P[k], np.float32 if k in fl else np.int32) for k in P}
    A["eptr"] = np.array(t.eptr, np.int32)
    assert t.n_mem < 65536
    A["tix"] = np.array(t.tix, np.uint16)
    A["tw"] = np.array(t.tw, np.float32)
    A["ec"] = np.array(t.ec, np.float32)
    A["levels"] = np.array(levels, np.int32)
    A["buckets"] = np.array(buckets, np.int32)
    A["keep"] = np.array(c.keep, np.int32)
    return {"arrays": A, "D": D, "n_mem": t.n_mem, "V": V, "one": ONE, "stats": stats}


def cached(c, key_files):
    """compile_ir, kept on disk under exec/build: the key is the source of this file, the circuit's builder and the printable table."""
    import hashlib
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256(open(os.path.abspath(__file__), "rb").read())
    for f in key_files:
        h.update(open(f, "rb").read())
    h.update(json.dumps(c.stats(), sort_keys=True).encode())
    path = os.path.join(here, "build", f"program-{h.hexdigest()[:12]}.npz")
    if os.path.exists(path):
        z = np.load(path)
        meta = json.loads(str(z["__meta"]))
        return {"arrays": {k: z[k] for k in z.files if k != "__meta"}, **meta}
    P = compile_ir(c)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.npz"
    np.savez(tmp, __meta=np.array(json.dumps({k: v for k, v in P.items() if k != "arrays"})), **P["arrays"])
    os.replace(tmp, path)
    return P
