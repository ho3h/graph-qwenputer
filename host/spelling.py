"""How Qwen spells node labels and relation names inside its tool calls, against the graph's canonical names.

    python spelling.py RUNDIR [RUNDIR ...] [--examples 5]

Reads every RUNDIR/*.jsonl with its RUNDIR/meta.json (for the graph). Each node argument (find.name, follow.node,
chase.start, neighbours.node, path/cheapest from and to, close/reopen node) and relation argument (find.has,
follow.relation, neighbours.relation, each relation of chase's legs) falls in the first class that matches it:

  handle        '@12'                                   (nodes only)
  exact         equals a canonical name byte for byte
  space         equals one after trimming spaces/newlines (reflib accepts it); the kind is in the example
  nfc           equals one after NFC normalisation and trimming (reflib accepts it)
  case          equals one ignoring case
  punct         equals one ignoring case, spaces and punctuation ("St Annes" ~ "St. Anne's")
  accents       equals one ignoring case, punctuation and diacritics ("Otaki" ~ "Ōtaki")
  handle+label  '@12 Eastgate', as a response line prints it, label matching node 12 (reflib accepts it)
  handle+wrong  '@12 Eastgate' whose label does not match node 12 (the tool answers NONE)
  label+suffix  a canonical name plus trailing words ("Eastgate station"); the words are tallied separately
  partial       one is a part of the other after the punct folding ("Upton Pkwy" ~ "Upton Pkwy (80 St)")
  other         none of these

Only handle, exact, space, nfc and handle+label resolve in the tool (SPEC section 4). It also checks whether each call's token ids are
the tokenizer's own encoding of its text.
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tools as T  # noqa: E402
from run import guard  # noqa: E402

CLASSES = ["handle", "exact", "space", "nfc", "case", "punct", "accents", "handle+label", "handle+wrong",
           "label+suffix", "partial", "other"]
RESOLVES = {"handle", "exact", "space", "nfc", "handle+label"}


def fold(s, accents=False):
    s = unicodedata.normalize("NFKD" if accents else "NFC", s)
    if accents:
        s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", "", s.casefold())


def space_kind(v):
    k = []
    lead, trail = v[: len(v) - len(v.lstrip())], v[len(v.rstrip()):]
    if lead:
        k.append("lead-newline" if "\n" in lead else "lead-space")
    if trail:
        k.append("trail-newline" if "\n" in trail else "trail-space")
    return "+".join(k)


def classify(v, canon, labels=None):
    """(class, matched canonical name or None). `labels` (the list by handle) marks node arguments."""
    nodes = labels is not None
    if nodes and re.fullmatch(r"@\d+", v):
        return "handle", None
    m = re.fullmatch(r"@(\d+)\s+(.+)", unicodedata.normalize("NFC", v).strip()) if nodes else None
    if m:
        h = int(m.group(1))
        if h < len(labels) and unicodedata.normalize("NFC", labels[h]).strip() == m.group(2):
            return "handle+label", labels[h]
        return "handle+wrong", labels[h] if h < len(labels) else None
    if v in canon:
        return "exact", v
    if v.strip() in canon:
        return "space", v.strip()
    n = unicodedata.normalize("NFC", v).strip()
    if n in canon:
        return "nfc", n
    for cls, f in (("case", lambda s: unicodedata.normalize("NFC", s).strip().casefold()),
                   ("punct", fold), ("accents", lambda s: fold(s, True))):
        hit = [c for c in canon if f(c) == f(v)]
        if hit:
            return cls, hit[0]
    hit = [c for c in canon if v.strip().startswith(c + " ")]
    if hit:
        return "label+suffix", max(hit, key=len)
    fv = fold(v, True)
    if fv:
        hit = [c for c in canon if fv in fold(c, True) or (fold(c, True) and fold(c, True) in fv)]
        if hit:
            return "partial", min(hit, key=len)
    return "other", None


def legs_relations(legs):
    out = []
    for p in str(legs).split(";"):
        if p.strip():
            m = re.fullmatch(r"(.+?)\s+(\d+)", p.strip())
            out.append(m.group(1) if m else p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--examples", type=int, default=5)
    a = ap.parse_args()
    from transformers import AutoTokenizer
    from model import MODEL
    tok = AutoTokenizer.from_pretrained(MODEL)
    counts = {"node": Counter(), "relation": Counter()}
    ex = defaultdict(list)
    suffixes = Counter()
    ncalls = canon_tok = 0
    for rd in map(Path, a.runs):
        meta = json.loads((rd / "meta.json").read_text())
        g = json.loads(guard(meta["graph"]).read_text())
        by_handle = [n["label"] for n in g["nodes"]]
        labels, rels = set(by_handle), set(g["relations"])
        for f in sorted(rd.glob("*.jsonl")):
            for line in f.open():
                r = json.loads(line)
                for c in r["calls"]:
                    ncalls += 1
                    canon_tok += tok.encode(c["text"], add_special_tokens=False) == c.get("ids")
                    fn, args = c["fn"], c["args"]
                    vals = [("node", args[p]) for p in T.NODE_PARAMS.get(fn, []) if p in args]
                    vals += [("relation", args[p]) for p in T.REL_PARAMS.get(fn, []) if p in args]
                    if fn == "chase" and "legs" in args:
                        vals += [("relation", x) for x in legs_relations(args["legs"])]
                    for kind, v in vals:
                        cls, hit = classify(v, labels if kind == "node" else rels, by_handle if kind == "node" else None)
                        counts[kind][cls] += 1
                        if cls == "label+suffix":
                            suffixes[v.strip()[len(hit):].strip()] += 1
                        if cls not in ("exact", "handle") and len(ex[kind, cls]) < a.examples:
                            note = f" [{space_kind(v)}]" if cls == "space" else ""
                            ex[kind, cls].append(f"{v!r} -> {hit!r}{note}  ({g['name']} q{r['id']} {r['attn']})")
    print(f"calls: {ncalls}; token ids equal the tokenizer's encoding of the call text: {canon_tok}/{ncalls}\n")
    print(f"trailing words after a canonical name: {dict(suffixes.most_common())}\n")
    for kind in ("node", "relation"):
        tot = sum(counts[kind].values())
        res = sum(v for k, v in counts[kind].items() if k in RESOLVES)
        print(f"{kind} arguments: {tot} (resolve in the tool: {res})")
        print(f"  {'class':<13}{'count':>6}{'share':>8}")
        for cls in CLASSES:
            if counts[kind][cls]:
                print(f"  {cls:<13}{counts[kind][cls]:>6}{counts[kind][cls] / tot:>8.1%}")
        for cls in CLASSES:
            for e in ex[kind, cls]:
                print(f"    {cls}: {e}")
        print()


if __name__ == "__main__":
    main()
