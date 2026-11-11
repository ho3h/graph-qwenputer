"""Shape of the circuit the executor must run: nodes per level, units, nonzeros, sharing, lag use. No weights loaded.

    python stats.py --out results/circuit_stats.json
"""
import argparse, collections, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "rvc"))
import box as X  # noqa
from chipformer.q35.ir import FFN, Head, Target, HD  # noqa
from chipformer.rv import bridge as BR, core  # noqa

def key(e):
    return tuple(sorted((d, float(c)) for d, c in e.terms.items()))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out"); a = ap.parse_args()
    t0 = time.time()
    tc = json.load(open(os.path.join(X.MODEL, "config.json")))["text_config"]
    T = BR.Text(X.tokenizer_json())
    c = core.build(Target(tc["linear_num_key_heads"], tc["linear_num_value_heads"], tc["intermediate_size"]), T)
    r = {"build_s": round(time.time() - t0, 1), "stats": c.stats(), "dims": len(c.dims), "token_fns": len(c.token_fns), "keep": c.keep, "levels": []}
    all_a, all_b = collections.Counter(), collections.Counter()
    alen, blen = collections.Counter(), collections.Counter()
    tot_a = tot_b = 0
    for lv in sorted({n.level for n in c.nodes}):
        ns = [n for n in c.nodes if n.level == lv]
        if isinstance(ns[0], FFN):
            us = [(cf, x, y, n.out) for n in ns for cf, x, y in n.terms]
            na = sum(len(x.terms) for _, x, _, _ in us); nb = sum(len(y.terms) for _, _, y, _ in us)
            ua, ub = {key(x) for _, x, _, _ in us}, {key(y) for _, _, y, _ in us}
            for _, x, y, _ in us:
                alen[len(x.terms)] += 1; blen[len(y.terms)] += 1
                all_a[key(x)] += 1; all_b[key(y)] += 1
            tot_a += na; tot_b += nb
            r["levels"].append({"level": lv, "kind": "ffn", "units": len(us), "a_nnz": na, "b_nnz": nb, "a_unique": len(ua), "b_unique": len(ub),
                                "a_unique_nnz": sum(len(k) for k in ua), "b_unique_nnz": sum(len(k) for k in ub), "outs": len({u[3] for u in us}), "into": sum(n.into for n in ns)})
        else:
            hs = ns
            d = {"level": lv, "kind": "head", "heads": len(hs), "vheads": sum(len(h.vheads()) for h in hs), "names": [h.name for h in hs][:6]}
            def nn(chs): return sum(len(ch.expr.terms) * sum(1 for t in ch.taps if t) for ch in chs.values())
            d["q_rows"] = sum(len(h.q) for h in hs); d["k_rows"] = sum(len(h.k) for h in hs)
            d["v_rows"] = sum(len(v.v) for h in hs for v in h.vheads()); d["z_rows"] = sum(len(v.z) for h in hs for v in h.vheads())
            d["q_nnz"] = sum(nn(h.q) for h in hs); d["k_nnz"] = sum(nn(h.k) for h in hs); d["v_nnz"] = sum(nn(v.v) for h in hs for v in h.vheads())
            d["z_nnz"] = sum(len(e.terms) for h in hs for v in h.vheads() for e in v.z.values())
            d["a_nnz"] = sum(len(v.a.terms) for h in hs for v in h.vheads()); d["beta"] = sum(v.beta is not None for h in hs for v in h.vheads())
            d["out"] = sum(len(v.out) for h in hs for v in h.vheads())
            d["lag_dims"] = len({(lag, x) for h in hs for v in h.vheads() for ch in list(h.q.values()) + list(h.k.values()) + list(v.v.values()) for lag, t in enumerate(ch.taps) if t and lag for x in ch.expr.terms})
            d["taps"] = dict(collections.Counter(str(ch.taps) for h in hs for v in h.vheads() for ch in list(h.q.values()) + list(h.k.values()) + list(v.v.values())))
            d["tiny"] = sorted({h.tiny for h in hs}); d["levels"] = sorted({h.levels for h in hs}); d["qhot"] = sorted({getattr(h, "qhot", 2) for h in hs})
            d["n_cols"] = sorted({h.n_cols for h in hs})
            r["levels"].append(d)
    r["ffn"] = {"a_nnz": tot_a, "b_nnz": tot_b, "a_unique_all": len(all_a), "b_unique_all": len(all_b), "alen": dict(sorted(alen.items())), "blen": dict(sorted(blen.items()))}
    # token features: nonzeros per family
    print(json.dumps(r["ffn"]), r["stats"], r["token_fns"], flush=True)
    for d in r["levels"]:
        print({k: v for k, v in d.items() if k not in ("names", "taps")}, flush=True)
    if a.out:
        json.dump(r, open(a.out, "w"), indent=1)

main()
