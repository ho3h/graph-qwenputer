#!/usr/bin/env python3
"""The chain's four outcomes, from saved rows only, on the exact line (T6), after split_reading. Beside the same questions' machine lines against reflib. No model. Writes results/chain_score.json."""
import json
import math
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(X210, "t8"), os.path.join(X210, "ci")]
import arms as A  # noqa: E402

reflib = A.reflib


def wilson(k, n, z=1.96):
    if not n:
        return [0.0, 0.0]
    p, d = k / n, 1 + z * z / n
    c, h = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(max(0.0, (c - h) / d), 4), round(min(1.0, (c + h) / d), 4)]


out = {}
sys.path.insert(0, os.path.join(X210, "ctrl"))
from transformers import AutoTokenizer  # noqa: E402

tok = AutoTokenizer.from_pretrained(os.path.expanduser("~/Models/x210/Qwen3.5-4B"))
FAILED = re.compile(r"(?i)stopped|did not finish|didn't finish|not finish|no further|\bNONE\b|no node|not found|does not exist|doesn't exist|unable|cannot|can't|error|not unique|ambiguous")
PRE = sys.argv[1] if len(sys.argv) > 1 else "chain"
for mode in ("print", "read"):
    for name in ("dev", "hard"):
        p = os.path.join(HERE, "results", f"{PRE}_{mode}_{name}", "all.jsonl")
        if not os.path.exists(p):
            continue
        c, kinds, starts, q = Counter(), Counter(), Counter(), Counter()
        ex = {"right": [], "loud": [], "limit": [], "silent": []}
        for ln in open(p):
            r = json.loads(ln)
            gold = reflib.reword(r.get("gold_text"))
            calls = r.get("calls") or []
            # the machine's line: the first clean line, or the last line if none is clean, printout's rule
            line, res = None, None
            for call in calls:
                readings, l = reflib.split_reading(call.get("result") or "")
                l = l.split("\n")[-1]                        # the result is the last line (SPEC 3)
                stated = re.search(r"(?i)clos|shut|reopen", r["text"])          # a setup's closure stated in the question isn't unasked
                c["closed_field_asked"] += "closed" in (call.get("args") or {}) and bool(stated)
                c["unasked_closed_field"] += "closed" in (call.get("args") or {}) and not stated
                c["unasked_reopened_field"] += "reopened" in (call.get("args") or {}) and not stated
                c["toolong"] += l == "TOOLONG"
                if line is None or not A.LOUD_LINE.match(l):
                    pass
                line, res = l, call.get("result")
                if not A.LOUD_LINE.match(l):
                    break
            o = A.outcome(line, gold)
            c[o] += 1
            kinds[("cities" if r["tag"][0].startswith("cities") else "random") + "_" + o] += 1
            rd = reflib.split_reading(res)[0] if res else []
            c["name_read"] += bool(rd)
            c["name_read_right"] += bool(rd) and o == "right"
            c["machine_equals_reflib"] += sum(bool(x.get("same_as_host")) for x in calls)
            c["machine_lines"] += len(calls)
            c["calls"] += r["n_calls"]
            for k in ("qwen_tokens", "echo_tokens", "chip_tokens", "seconds"):
                c[k] += r.get(k) or 0
            c["lock_or_flag"] += r["status"] in ("lock", "engine_flag", "verify_mismatch")
            c["status_" + r["status"]] += 1
            start = str(((calls[0].get("args") if calls else None) or {}).get("start", ""))
            starts["handle" if start.startswith("@") else ("ends_station" if start.rstrip(".,;:!? ").endswith(" station") else "plain")] += 1
            # refused names still printed in bytes: pieces' question
            for x in calls:
                for lnx in (x.get("result") or "").split("\n"):
                    if lnx.startswith("NONE ") or lnx.startswith("NORELATION ") or lnx.startswith("BADARG "):
                        c["echoed_lines"] += 1
                        c["echoed_tokens_as_bytes"] += len(lnx.encode())
                        c["echoed_tokens_if_normal"] += len(tok.encode(lnx, add_special_tokens=False))
            if mode == "read":
                f = r.get("final")
                last = [x for x in (f or "").split("\n") if x.strip()][-1:] or [""]
                qo = "right" if r.get("correct") else ("none" if not f else ("says_failed" if FAILED.search(f) else "silent_wrong"))
                q[qo] += 1
                q["exact_line_quoted"] += bool(f) and line is not None and line in f
                if gold.startswith("Stopped early"):
                    q["gold_limit"] += 1
                    q["gold_limit_says_stopped"] += bool(f) and bool(FAILED.search(f))
                if o == "right" and qo != "right":
                    q["line_right_sentence_wrong"] += 1
                if o != "right" and qo == "right":
                    q["line_wrong_sentence_right"] += 1
            if len(ex[o]) < 6 or (rd and len(ex[o]) < 12):
                ex[o].append({"text": r["text"], "calls": [{"args": x.get("args"), "result": x.get("result")} for x in calls], "final": r.get("final"), "gold": gold})
        n = sum(c[y] for y in ex)
        out[f"{mode}_{name}"] = {"n": n, "counts": dict(c), "by_kind": dict(kinds), "starts": dict(starts), "wilson": {x: wilson(c[x], n) for x in ex}, "qwen_own_words": dict(q) if mode == "read" else None, "examples": ex}
json.dump(out, open(os.path.join(HERE, "results", f"{PRE}_score.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: {a: b for a, b in v.items() if a != "examples"} for k, v in out.items()}, ensure_ascii=False)[:3500])
