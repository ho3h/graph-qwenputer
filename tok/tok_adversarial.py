"""T1b: awkward names through the joining rule, by tokenizer alone. See REGISTRATION.md.

    python tok/tok_adversarial.py --out tok/results/t1b.json
"""
import argparse
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "vendor", "qwenputer-riscv"), os.path.join(X210, "cop"), os.path.join(X210, "lib"), HERE]
from chipformer.rv import bridge as BR  # noqa: E402
import fragments as F  # noqa: E402
import tok_only as TO  # noqa: E402
import test_a1_dev as TA  # noqa: E402

HAND = ["St.", "St. Marks", "Bleecker St.", "O'Neil", "'s", "Mary's", "(Downtown)", "A (B)", "A-", "-A", "--", "/", "x/y", "a, b", "a,", "Q&A", "A&", "1", "42 St", "42", "4.5", "7th",
        "٣", "٣ St", "é", "éx", "Zürich", "Köln.", "中文", "東京駅", "русский", "דוד", "🙂", "🙂 St", " lead", "trail ", "two  spaces", "tab\there", "new\nline", "\n", " ",
        "<tool_call>", "</tool_call>", "<|im_end|>", "a<think>b", "<tool_response>", "@5 Oak", "> x", "x >", "| y", "a b", " ", "ſ", "ﬁ", "A" * 40, "supercalifragilistic", "x" * 64]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    T = BR.Text(TO.TOK)
    fr = F.Frag(T.tok, T.printable[:256])
    res = {"hand": [], "random": Counter()}
    bad = Counter()
    for name in HAND:
        labels, rels = [name, "Oak"], ["r"]
        g = {"nodes": [{"label": x} for x in labels], "relations": rels}
        row = {"name": name, "lines": 0, "bytes_ok": 0, "tokens_ok": 0, "first_bad": None}
        for sh, parts in TO.synth_lines(g):
            if parts and parts[0][1] == 1 and sh == "plain":
                continue
            text = TO.text_of(parts, labels, rels)
            want = fr.enc(F.HEAD + text + F.TAIL)
            got = fr.wrapped(parts, labels, rels)
            b = T.decode_bytes(got) == (F.HEAD + text + F.TAIL).encode()
            t = got == want
            row["lines"] += 1
            row["bytes_ok"] += b
            row["tokens_ok"] += t
            if not t and row["first_bad"] is None:
                i = next((i for i, (x, y) in enumerate(zip(got, want)) if x != y), min(len(got), len(want)))
                row["first_bad"] = {"shape": sh, "got": [T.tok.id_to_token(x) for x in got[max(0, i - 1): i + 3]], "real": [T.tok.id_to_token(x) for x in want[max(0, i - 1): i + 3]]}
        res["hand"].append(row)
    total = Counter()
    for seed in range(300):
        g = TA.rand_graph(seed)
        labels, rels = [n["label"] for n in g["nodes"]], list(g["relations"])
        for sh, parts in TO.synth_lines(g):
            text = TO.text_of(parts, labels, rels)
            want = fr.enc(F.HEAD + text + F.TAIL)
            got = fr.wrapped(parts, labels, rels)
            total["lines"] += 1
            total["bytes_ok"] += T.decode_bytes(got) == (F.HEAD + text + F.TAIL).encode()
            ok = got == want
            total["tokens_ok"] += ok
            if not ok and len(res.setdefault("random_bad", [])) < 30:
                i = next((i for i, (x, y) in enumerate(zip(got, want)) if x != y), min(len(got), len(want)))
                res["random_bad"].append({"text": text, "got": [T.tok.id_to_token(x) for x in got[max(0, i - 1): i + 3]], "real": [T.tok.id_to_token(x) for x in want[max(0, i - 1): i + 3]]})
    res["random"] = dict(total)
    json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
    for r in res["hand"]:
        print(repr(r["name"])[:30], r["lines"], r["bytes_ok"], r["tokens_ok"], (r["first_bad"] or {}).get("shape"), (r["first_bad"] or {}).get("got"), (r["first_bad"] or {}).get("real"))
    print(res["random"], res.get("random_bad", [])[:8])


if __name__ == "__main__":
    main()
