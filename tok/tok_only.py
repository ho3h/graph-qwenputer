"""T1: stored tokens against the real tokenizer, no model and no machine. See REGISTRATION.md.

    python tok/tok_only.py --out tok/results/t1.json
"""
import argparse
import glob
import json
import os
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "vendor", "qwenputer-riscv"), os.path.join(X210, "cop"), HERE]

from chipformer.rv import bridge as BR  # noqa: E402
from chipformer.rv import elf  # noqa: E402
import boot as B  # noqa: E402
import fragments as F  # noqa: E402

TOK = os.path.expanduser("~/Models/x210/Qwen3.5-4B/tokenizer.json")
FW_ELF = os.path.join(X210, "fw", "build", "fw.elf")
DROM_MAX = 128 * 1024


def synth_lines(g):
    """Every node and relation in every SPEC 3 shape: (shape, parts). Handles are real, the combinations are not meant to be reachable."""
    N, R = len(g["nodes"]), len(g["relations"])
    for h in range(N):
        o = (h + 1) % N
        yield "plain", [("fmt", h)]
        yield "ambiguous", [("lit", "AMBIGUOUS "), ("num", 2), ("lit", ": "), ("fmt", h), ("lit", " | "), ("fmt", o)]
        yield "closed_h", [("lit", "CLOSED "), ("fmt", h)]
        yield "multi", [("lit", "MULTI "), ("num", 3), ("lit", " at "), ("fmt", h), ("lit", " after "), ("num", 2), ("lit", " steps")]
        yield "leg_end", [("lit", "leg "), ("num", 2), ("lit", ": "), ("lit", "END at "), ("fmt", h), ("lit", " after "), ("num", 1), ("lit", " steps")]
        yield "nochange", [("lit", "leg "), ("num", 2), ("lit", ": NOCHANGE at "), ("fmt", h)]
        yield "neighbours", [("fmt", h), ("lit", "\n"), ("fmt", o)]
        yield "path", [("num", 1), ("lit", " steps: "), ("fmt", h), ("lit", " > "), ("fmt", o)]
        yield "cost", [("lit", "cost "), ("num", 12), ("lit", ": "), ("fmt", h), ("lit", " > "), ("fmt", o)]
        yield "close", [("lit", "closed "), ("fmt", h)]
        yield "reopen", [("lit", "reopened "), ("fmt", h)]
        yield "not_closed", [("lit", "not closed "), ("fmt", h)]
        yield "link", [("lit", "linked "), ("fmt", h), ("lit", " > "), ("rel", h % R if R else 0), ("lit", " > "), ("fmt", o)] if R else ("plain", [("fmt", h)])


def text_of(parts, labels, rels):
    s = []
    for k, v in parts:
        s.append(v if k == "lit" else str(v) if k == "num" else f"@{v} {labels[v]}" if k == "fmt" else rels[v] if k == "rel" else v.decode("utf-8", "surrogateescape"))
    return "".join(s)


def spaces_ok(parts):
    return True


def check(fr, T, parts, labels, rels, text, stat, name):
    want = fr.enc(F.HEAD + text + F.TAIL)
    got = fr.wrapped(parts, labels, rels)
    b_ok = T.decode_bytes(got) == (F.HEAD + text + F.TAIL).encode("utf-8", "surrogateescape")
    t_ok = got == want
    has_arg = any(k == "arg" for k, _ in parts)
    key = "arg" if has_arg else "no_arg"
    stat[key + "_lines"] += 1
    stat[key + "_bytes_ok"] += b_ok
    stat[key + "_tokens_ok"] += t_ok
    if not b_ok and len(stat["bytes_bad"]) < 40:
        stat["bytes_bad"].append([name, text])
    if not t_ok:
        stat["token_bad_kinds"][mismatch_kind(fr, parts, labels, text)] += 1
        if not has_arg and len(stat["token_bad"]) < 60:
            i = next((i for i, (x, y) in enumerate(zip(got, want)) if x != y), min(len(got), len(want)))
            stat["token_bad"].append({"where": name, "text": text, "got": [fr.tok.id_to_token(x) for x in got[max(0, i - 2): i + 4]], "real": [fr.tok.id_to_token(x) for x in want[max(0, i - 2): i + 4]]})
    return b_ok, t_ok


def mismatch_kind(fr, parts, labels, text):
    if any(k == "arg" for k, _ in parts):
        return "echoed argument"
    if text[-1:] in ".,:;!?)]}'\"/-&" or any(c.isalnum() is False and (c + "\n") in text for c in set(text) if c not in " \n"):
        return "punctuation before a newline"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    T = BR.Text(TOK)
    fr = F.Frag(T.tok, T.printable[:256])
    from collections import defaultdict
    new = lambda: defaultdict(int, {"bytes_bad": [], "token_bad": [], "token_bad_kinds": Counter()})
    res = {"tokenizer": TOK, "synth": {}, "real": {}, "fit": []}
    syn, real = new(), new()
    shape = defaultdict(lambda: [0, 0, 0])
    added = [t for t in T.tok.get_added_tokens_decoder().values()]
    added_s = [x.content for x in added]
    res["labels_with_added_token"] = []
    rodata = elf.program(FW_ELF).rodata if os.path.exists(FW_ELF) else b""
    labels_seen = rel_seen = tok_seen = 0
    longest = 0
    above16 = 0
    tokens_total = 0
    paths = sorted(glob.glob(os.path.join(X210, "data", "dev", "*", "*.graph.json")))
    assert not any("heldout" in p for p in paths)
    graphs = {}
    for p in paths:
        name = os.path.relpath(p, os.path.join(X210, "data", "dev"))[: -len(".graph.json")]
        g = json.load(open(p))
        graphs[name] = g
        labels = [n["label"] for n in g["nodes"]]
        rels = list(g["relations"])
        relmap = {r: i for i, r in enumerate(rels)}
        labels_seen += len(labels)
        rel_seen += len(rels)
        for s in labels + rels:
            if any(x in s for x in added_s):
                res["labels_with_added_token"].append([name, s])
        n_tok = 0
        for s in labels + rels:
            ids = fr.label(s)
            n_tok += len(ids)
            longest = max(longest, len(ids))
            above16 += sum(i >= 65536 for i in ids)
        tokens_total += n_tok
        for sh, parts in synth_lines(g):
            text = text_of(parts, labels, rels)
            b, t = check(fr, T, parts, labels, rels, text, syn, f"{name}:{sh}")
            shape[sh][0] += 1
            shape[sh][1] += b
            shape[sh][2] += t
        qp = p.replace(".graph.json", ".questions.json")
        if os.path.exists(qp):
            for q in json.load(open(qp))["questions"]:
                text = q.get("answer_text")
                if not text:
                    continue
                parts = F.parse(text, labels, relmap)
                if parts is None:
                    real["no_parse"] += 1
                    continue
                check(fr, T, parts, labels, rels, text, real, f"{name} q{q['id']}")
        try:
            _, drom = B.boot(g, rodata, software=True)
            base = len(drom)
            extra = 4 * (n_tok + len(labels) + 1 + len(rels) + 1)
            res["fit"].append({"graph": name, "drom": base, "with_tokens": base + extra, "fits": base + extra <= DROM_MAX, "tokens": n_tok, "extra": extra})
        except B.BootLimit as e:
            res["fit"].append({"graph": name, "boot_limit": str(e)})
    machine = new()
    for f in ("chain3", "chain4_fresh"):
        path = os.path.join(X210, "rvc", "results", f, "all.jsonl")
        for ln in open(path):
            r = json.loads(ln)
            g = graphs[r["graph"]]
            labels = [n["label"] for n in g["nodes"]]
            rels = list(g["relations"])
            relmap = {x: i for i, x in enumerate(rels)}
            for c in r["calls"]:
                text = c["result"]
                parts = F.parse(text, labels, relmap)
                if parts is None:
                    machine["no_parse"] += 1
                    continue
                check(fr, T, parts, labels, rels, text, machine, f"{f} {r['graph']} q{r['id']}")
    res["synth"], res["real"], res["machine"] = syn, real, machine
    res["by_shape"] = {k: dict(zip(("lines", "bytes_ok", "tokens_ok"), v)) for k, v in shape.items()}
    res["labels_and_relations"] = labels_seen + rel_seen
    res["tokens_in_tables"] = tokens_total
    res["tokens_at_or_above_65536"] = above16
    res["most_tokens_in_a_name"] = longest
    fit = [x for x in res["fit"] if x.get("fits")]
    no = [x for x in res["fit"] if not x.get("fits")]
    res["fit_summary"] = {"graphs": len(res["fit"]), "fit": len(fit), "do_not": [(x["graph"], x.get("with_tokens"), x.get("boot_limit")) for x in no],
                          "largest": max(fit, key=lambda x: x["with_tokens"]) if fit else None}
    # the real tool turn's fixed tokens, for the report
    res["fixed_head"] = [T.tok.id_to_token(i) for i in fr.enc(F.HEAD)]
    res["fixed_tail"] = [T.tok.id_to_token(i) for i in fr.enc(F.TAIL)]
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False, default=dict)
    show = {k: {x: y for x, y in dict(res[k]).items() if x not in ("token_bad", "bytes_bad")} for k in ("synth", "real", "machine")}
    print(json.dumps(show, indent=0, default=dict))
    print(res["by_shape"])
    print(res["fit_summary"], res["labels_with_added_token"][:5], res["seconds"], res["tokens_in_tables"], res["tokens_at_or_above_65536"], res["most_tokens_in_a_name"])


if __name__ == "__main__":
    main()
