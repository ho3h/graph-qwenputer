"""Summary of host-baseline runs, and the eager/SDPA agreement noise floor.

    python report.py RUNDIR [RUNDIR ...]

Per attention implementation: accuracy, how questions ended, tool calls per question, functions called, the first
word of each tool result, seconds per question and peak MPS driver memory. Agreement: per question present under
both eager and sdpa, whether the whole token stream is identical (the transcript agreement of DESIGN's noise floor),
whether the final answers and the scores agree, and where the first difference falls.
"""

import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path


def result_kind(res):
    """'ok' for an answer, else the limit or error word (a chase leg's as 'leg:WORD')."""
    w = res.split()
    if not w:
        return "empty"
    if w[0] == "leg" and len(w) > 2:
        return "leg:" + w[2]
    if w[0].startswith("@") or w[0].isdigit() or w[0] in ("cost", "closed", "reopened", "linked", "unlinked"):
        return "ok"
    return w[0]


def load(dirs):
    recs = defaultdict(dict)                     # attn -> (run, id) -> record
    for d in map(Path, dirs):
        for f in sorted(d.glob("*.jsonl")):
            for line in f.open():
                r = json.loads(line)
                recs[r["attn"]][d.name, r["id"]] = r
    return recs


def main(dirs):
    recs = load(dirs)
    for attn, rs in sorted(recs.items()):
        v = list(rs.values())
        scored = [r for r in v if r["correct"] is not None]
        sec = [r["seconds"] for r in v]
        print(f"== {attn}: {len(v)} questions")
        print(f"  correct {sum(r['correct'] for r in scored)}/{len(scored)} scored")
        by = defaultdict(lambda: [0, 0])
        for r in scored:
            by[r["kind"]][0] += r["correct"]
            by[r["kind"]][1] += 1
        print("  by kind: " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in sorted(by.items())))
        print(f"  unscorable (empty gold): {sum(r['correct'] is None for r in v)}; stale gold: "
              f"{sum(bool(r.get('gold_stale')) for r in v)}; setup mismatches: "
              f"{sum(bool(r.get('setup_mismatch')) for r in v)}")
        print(f"  ended: {dict(Counter(r['status'] for r in v))}")
        print(f"  calls/question: mean {st.mean(r['n_calls'] for r in v):.2f}, "
              f"histogram {dict(sorted(Counter(r['n_calls'] for r in v).items()))}")
        calls = [c for r in v for c in r["calls"]]
        print(f"  functions: {dict(Counter(c['fn'] for c in calls))}")
        print(f"  results: {dict(Counter(result_kind(c['result']) for c in calls))}")
        print(f"  parse errors: {sum(1 for c in calls if c['parse_error'])}")
        print(f"  seconds/question: mean {st.mean(sec):.1f}, median {st.median(sec):.1f}, max {max(sec):.1f}; "
              f"generated tokens mean {st.mean(r['generated_tokens'] for r in v):.0f}, "
              f"prompt tokens {min(r['prompt_tokens'] for r in v)}-{max(r['prompt_tokens'] for r in v)}")
        print(f"  peak MPS driver memory: {max(r['peak_driver_bytes'] for r in v) / 2**30:.2f} GiB")
    if "eager" in recs and "sdpa" in recs:
        both = sorted(set(recs["eager"]) & set(recs["sdpa"]))
        same = final = corr = 0
        div = []
        for k in both:
            e, s = recs["eager"][k], recs["sdpa"][k]
            same += e["stream_ids"] == s["stream_ids"]
            final += e["final"] == s["final"]
            corr += e["correct"] == s["correct"]
            if e["stream_ids"] != s["stream_ids"]:
                i = next((i for i, (a, b) in enumerate(zip(e["stream_ids"], s["stream_ids"])) if a != b),
                         min(len(e["stream_ids"]), len(s["stream_ids"])))
                div.append((k, i - e["prompt_tokens"]))
        n = len(both)
        print(f"== agreement eager vs sdpa over {n} questions")
        print(f"  identical transcripts {same}/{n} ({same / n:.1%}); same final answer {final}/{n}; "
              f"same score {corr}/{n}")
        for k, i in div:
            print(f"  differs: {k[0]} q{k[1]} at generated token {i}")


if __name__ == "__main__":
    main(sys.argv[1:])
