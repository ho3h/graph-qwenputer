#!/usr/bin/env python3
"""The step-14 chart of web/template.html, drawn from counts, so that a bar can be added without hand arithmetic.

    python3 web/chart.py --check     (the rows below give the SVG that is in the template, byte for byte)

On 9 Nov's four bars this function gave the template's SVG of that day byte for byte (commit 5407515cde). Round 18 added the
second label line, recounted the first bar and added the reasoning-on bar.

A row is (label, [(count, kind, word), ...]) or (label, parts, second line). kind is right, wrong or none.
Each bar is drawn as shares of its own total. The second line is a smaller line under the label, for a bar's setup.
"""
import sys

W, PITCH, SUB = 380.0, 54, 16


def num(v):
    return f"{v:.1f}"


def svg(rows, aria):
    h = 262 + PITCH * (len(rows) - 4) + SUB * sum(len(r) > 2 for r in rows)
    out = [f'<svg viewBox="0 0 380 {h}" role="img" aria-label="{aria}"><g font-size="13" fill="currentColor"><rect x="0" y="2" width="12" height="12" rx="2" fill="var(--right)"/><text x="17" y="13">right</text>'
           '<rect x="62" y="2" width="12" height="12" rx="2" fill="var(--wrong)"/><text x="79" y="13">wrong</text><rect x="128" y="2" width="12" height="12" rx="2" fill="var(--none)"/><text x="145" y="13">refused or unfinished</text></g>']
    y = 54 - PITCH
    for label, parts, *sub in rows:
        y += PITCH + SUB * len(sub)
        total, x = sum(c for c, _, _ in parts), 0.0
        out.append(f'<text y="{y - 6 - SUB * len(sub)}" font-size="13" fill="currentColor">{label}</text>')
        if sub:
            out.append(f'<text y="{y - 6}" font-size="12" style="fill:var(--soft)">{sub[0]}</text>')
        for c, kind, word in parts:
            if not c:
                continue
            w = c * W / total
            out.append(f'<rect x="{num(x)}" y="{y}" width="{num(max(w - 2, 2.0))}" height="24" rx="2" fill="var(--{kind})"><title>{c} {word}</title></rect>')
            if w - 2 >= 22:                                         # room for the count
                out.append(f'<text x="{num(x + 7)}" y="{y + 17}" font-size="13" font-weight="700" style="fill:var(--{"ink" if kind == "none" else "on-mark"})">{c}</text>')
            x += w
    return "".join(out) + "</svg>"


SUBLINE = "One sample a question at temperature 0.6, limit 8,192 tokens"
ROWS = [("Qwen alone, no map, reasoning off", [(1, "right", "right"), (88, "wrong", "wrong"), (11, "none", "unfinished")]),
        ("Qwen given the map, listing each stop, reasoning off", [(54, "right", "right"), (36, "wrong", "wrong"), (10, "none", "unfinished")]),
        ("Qwen given the map, reasoning on, first 28 questions", [(26, "right", "right"), (0, "wrong", "wrong"), (2, "none", "unfinished")], SUBLINE),
        ("Graph-qwenputer, first version", [(47, "right", "right"), (53, "none", "refused")]),
        ("Graph-qwenputer, after one fix", [(100, "right", "right")])]
ARIA = ("Scores on two-train questions from New York's question file. Qwen alone, no map, reasoning off, 100 questions: 1 right, 88 wrong, 11 unfinished. "
        "Qwen given the map, listing each stop, reasoning off, 100 questions: 54 right, 36 wrong, 10 unfinished. "
        "Qwen given the map, reasoning on, first 28 questions, one sample a question at temperature 0.6, limit 8,192 tokens: 26 right, 0 wrong, 2 unfinished. "
        "Graph-qwenputer, first version, 100 questions: 47 right, 53 refused. Graph-qwenputer, after one fix, 100 questions: 100 right.")

if __name__ == "__main__":
    import os
    t = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html"), encoding="utf-8").read()
    if sys.argv[1:] == ["--check"]:
        made = svg(ROWS, ARIA)
        i = t.index('<svg viewBox="0 0 380 ')
        have = t[i:t.index("</svg>", i) + 6]
        if made != have:
            k = next((n for n, (p, q) in enumerate(zip(made, have)) if p != q), min(len(made), len(have)))
            print("differs at", k, "\nmade:", made[k - 60:k + 80], "\nhave:", have[k - 60:k + 80])
            sys.exit(1)
        print("chart.py: the five bars of 10 Nov are the template's SVG byte for byte,", len(made), "characters")
