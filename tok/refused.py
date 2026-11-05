"""T7: refused names through a piece table from the graph's own names, by tokenizer alone. See REGISTRATION.md.

    python tok/refused.py --out tok/results/t7.json
"""
import argparse
import glob
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "vendor", "qwenputer-riscv"), os.path.join(X210, "cop"), HERE]
from chipformer.rv import bridge as BR  # noqa: E402
import fragments as F  # noqa: E402
import tok_only as TO  # noqa: E402

NOUNS = {"cities": "station"}          # as t8's noun.py gives a transit graph: boot data, read from the graph's domain there
SP, NL = 32, 10


def letter(c):
    return 65 <= c <= 90 or 97 <= c <= 122


def digit(c):
    return 48 <= c <= 57


CONTR = (b"'s", b"'t", b"'re", b"'ve", b"'m", b"'ll", b"'d")


def cut(b):
    """The tokenizer's regex on ASCII bytes, as simple firmware would run it; None at the first non-ASCII byte. b includes the leading space."""
    out, i, n = [], 0, len(b)
    if any(c >= 128 for c in b):
        return None
    while i < n:
        c = b[i]
        low = b[i:i + 3].lower()
        hit = next((k for k in CONTR if low.startswith(k)), None)
        if hit:
            out.append(b[i:i + len(hit)])
            i += len(hit)
        elif letter(c) or (c not in (13, 10) and not digit(c) and i + 1 < n and letter(b[i + 1])):
            j = i + 1
            while j < n and letter(b[j]):
                j += 1
            out.append(b[i:j])
            i = j
        elif digit(c):
            out.append(b[i:i + 1])
            i += 1
        elif c == 32 and i + 1 < n and b[i + 1] not in (32, 9, 10, 13, 11, 12) and not digit(b[i + 1]):     # a space joins punctuation (a letter was taken above)
            j = i + 2
            while j < n and not letter(b[j]) and not digit(b[j]) and b[j] not in (32, 9, 10, 13, 11, 12):
                j += 1
            out.append(b[i:j])
            i = j
        elif c in (32, 9, 10, 13, 11, 12):
            j = i
            while j < n and b[j] in (32, 9, 10, 13, 11, 12):
                j += 1
            out.append(b[i:j])          # (a space before a letter was taken above; before a digit or at the end it stands alone)
            i = j
        else:
            j = i + 1
            while j < n and not letter(b[j]) and not digit(b[j]) and b[j] not in (32, 9, 10, 13, 11, 12):
                j += 1
            out.append(b[i:j])
            i = j
    return out


def table(fr, names):
    """piece bytes -> tokens, only pieces of two bytes or more (one byte prints as its byte token anyway)."""
    t = {}
    for s in names:
        b = (" " + s).encode()
        p = cut(b)
        if p is None:
            continue
        for x in p:
            if len(x) >= 2 and x not in t:
                ids = fr.tok.encode(x.decode(), add_special_tokens=False).ids
                t[x] = ids
    return t


def table_bytes(t):
    return 2 * 512 + sum(1 + len(k) + 1 + 2 * len(v) + 2 for k, v in t.items())


def spell(fr, T, arg, t, stat):
    """Tokens for an echoed argument after a pending space. Bytes wherever the table has nothing."""
    b = b" " + arg
    p = cut(b)
    if p is None:
        return [T.printable[c] for c in b]
    out = []
    for x in p:
        if x in t:
            out += t[x]
            stat["bytes_by_piece"] += len(x)
        else:
            out += [T.printable[c] for c in x]
            stat["bytes_by_byte"] += len(x)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    T = BR.Text(TO.TOK)
    fr = F.Frag(T.tok, T.printable[:256])
    graphs, tabs, fit = {}, {}, []
    t1 = json.load(open(os.path.join(HERE, "results", "t1.json")))
    base = {x["graph"]: x.get("drom") for x in t1["fit"]}
    for p in sorted(glob.glob(os.path.join(X210, "data", "dev", "*", "*.graph.json"))):
        assert "heldout" not in p
        name = os.path.relpath(p, os.path.join(X210, "data", "dev"))[: -len(".graph.json")]
        g = json.load(open(p))
        graphs[name] = g
        names = [n["label"] for n in g["nodes"]] + list(g["relations"])
        if name.startswith("cities/"):
            names.append(NOUNS["cities"])
        tabs[name] = table(fr, names)
        fit.append({"graph": name, "pieces": len(tabs[name]), "bytes": table_bytes(tabs[name])})
    sets = defaultdict(list)
    for f in ("chain3", "chain4_fresh"):
        for ln in open(os.path.join(X210, "rvc", "results", f, "all.jsonl")):
            r = json.loads(ln)
            sets["machine_chains"] += [(r["graph"], c["result"]) for c in r["calls"]]
    for gg, nm in (("tiny", None), ("c024", "cities/c024"), ("c025", "cities/c025"), ("r001", "random/r001")):
        if nm is None:
            continue
        for ln in open(os.path.join(HERE, "results", "t6", gg + ".jsonl")):
            r = json.loads(ln)
            sets["t6"] += [(nm, c["result"]) for c in r["calls"]]
    for name, g in graphs.items():
        qp = os.path.join(X210, "data", "dev", name + ".questions.json")
        for q in json.load(open(qp))["questions"]:
            if q.get("answer_text"):
                sets["answer_text"].append((name, q["answer_text"]))
    res = {"sets": {}, "fit": fit}
    for sname, lines in sets.items():
        s = Counter()
        bad = []
        for gname, line in lines:
            pre = next((p for p in F.ARG_PREFIX if line.startswith(p)), None)
            if pre is None:
                continue
            arg = line[len(pre):].encode("utf-8", "surrogateescape")
            kind = pre.split()[0] + ("_city" if gname.startswith("cities/") else "_random")
            head = fr.enc(pre[:-1])
            got = head + spell(fr, T, arg, tabs[gname], s) if arg else head + [fr.SP]
            want = fr.enc(line)
            s[kind + "_lines"] += 1
            s["lines"] += 1
            byt = T.decode_bytes(got) == line.encode("utf-8", "surrogateescape")
            s["bytes_ok"] += byt
            ok = got == want
            s[kind + "_tokens_ok"] += ok
            s["tokens_ok"] += ok
            if not ok and len(bad) < 12:
                bad.append({"line": line, "got": [fr.tok.id_to_token(x) for x in got][:14], "real": [fr.tok.id_to_token(x) for x in want][:14]})
        res["sets"][sname] = {"counts": dict(s), "not_equal_examples": bad}
    room = []
    for x in fit:
        b = base.get(x["graph"])
        if not b:
            continue
        room.append(x["bytes"])
    res["bytes_mean"] = sum(room) / len(room)
    res["bytes_max"] = max(room)
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
    for k, v in res["sets"].items():
        print(k, v["counts"])
        print(v["not_equal_examples"][:4])
    print(res["bytes_mean"], res["bytes_max"], res["seconds"])


if __name__ == "__main__":
    main()
