"""Round-2 reporting over saved rows, recomputed, nothing rerun; the graded answer is not changed.

    python chain4_report.py results/chain3 results/chain4/prefill ...    # prints a table, writes <dir>/report.json

Outcomes: correct (host/score.py); limit line on a wrong query (END, MULTI or NOCHANGE and not correct: a reader takes it at face value); silent wrong (another clean line);
loud (any other error line, or no line). Qwen's own text after the machine's last line, scored apart: right (host/score.py on the text finds the gold), misread (a finished statement that does not),
none (no finished statement: cut at a budget, or the runner stopped there). Handles the 7 c0xx rows as they were saved.
"""
import hashlib
import json
import os
import re
import sys

X210 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(X210, "host"))
import score as SC  # noqa: E402

LIMIT = {"END", "MULTI", "NOCHANGE"}
ERR = re.compile(r"^(?:leg \d+: )?(NORELATION|NONE|AMBIGUOUS|BADARG|END|MULTI|NOCHANGE|CLOSED|NOPATH|NOFUNCTION|OVERFLOW|TOOLONG)\b")
QS, GS = {}, {}


def qg(graph, i):
    if graph not in GS:
        GS[graph] = json.load(open(os.path.join(X210, "data", "dev", graph + ".graph.json")))
        QS[graph] = {x["id"]: x for x in json.load(open(os.path.join(X210, "data", "dev", graph + ".questions.json")))["questions"]}
    return QS[graph][i], [n["label"] for n in GS[graph]["nodes"]]


def outcome3(r):
    if r["correct"]:
        return "correct"
    m = ERR.match(r["final"] or "")
    if m and m.group(1) in LIMIT:
        return "limit on wrong query"
    return "loud" if (r["final"] is None or m) else "silent"


def own_text(r, q, labels):
    if r.get("readback_end"):
        text, done = r["readback_text"], r["readback_end"] == "stop"
        why = {"stop": "", "cap": "cut at the cap", "tool_call": "called again"}[r["readback_end"]]
    elif r["status"] == "no_call":
        text = r["no_call_text"] or ""
        done = text.endswith(("<|im_end|>", "<|endoftext|>"))
        why = "" if done else "cut at the budget"
    else:
        text, done, why = None, False, "runner stopped at the line"
    if not done or not (text or "").replace("<|im_end|>", "").replace("<|endoftext|>", "").strip():
        return "none", why or "empty", None
    t = text.replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()
    return ("right" if SC.score(t, q, labels) else "misread"), "", t[-120:]


def report(d):
    p = os.path.join(d, "all.jsonl")
    raw = open(p, "rb").read()
    rows = [json.loads(x) for x in raw.decode().splitlines() if x.strip()]
    out = {"dir": d, "sha256_all_jsonl": hashlib.sha256(raw).hexdigest(), "n": len(rows), "correct": 0, "correct_not_canonical": 0, "limit on wrong query": 0, "silent": 0, "loud": 0,
           "own_text": {"right": 0, "misread": 0, "none": 0}, "own_none_why": {}, "misread_rows": [], "right_where_line_wrong": 0, "misread_where_line_right": 0, "limit_wrong_rows": [], "silent_rows": [],
           "rescued": 0, "first_correct": 0, "calls": sum(r["n_calls"] for r in rows), "lock_errors": sum(r["lock_error"] is not None for r in rows), "by_set": {}}
    for r in rows:
        q, labels = qg(r["graph"], r["id"])
        o = outcome3(r)
        out["correct" if o == "correct" else o] += 1
        out["correct_not_canonical"] += o == "correct" and r["final"] != q["answer_text"]
        out["first_correct"] += bool(r["outcome"]["first_correct"])
        out["rescued"] += bool(o == "correct" and not r["outcome"]["first_correct"])
        k, why, t = own_text(r, q, labels)
        out["own_text"][k] += 1
        if k == "none":
            out["own_none_why"][why] = out["own_none_why"].get(why, 0) + 1
        if k == "misread":
            out["misread_rows"].append([r["graph"], r["id"], o, t])
            out["misread_where_line_right"] += o == "correct"
        if k == "right" and o != "correct":
            out["right_where_line_wrong"] += 1
        if o == "limit on wrong query":
            out["limit_wrong_rows"].append([r["graph"], r["id"], (r["final"] or "")[:60], q["answer_text"][:50]])
        if o == "silent":
            out["silent_rows"].append([r["graph"], r["id"], [(c["args"].get("start"), c["args"].get("legs"), c.get("result", "")[:40]) for c in r["calls"]], q["answer_text"][:50]])
        s = out["by_set"].setdefault(r["graph"].split("/")[0], {"n": 0, "correct": 0})
        s["n"] += 1
        s["correct"] += o == "correct"
    out["selection_score"] = out["correct"] - 3 * out["silent"]
    out["selection_score_if_limit_lines_silent"] = out["correct"] - 3 * (out["silent"] + out["limit on wrong query"])
    json.dump(out, open(os.path.join(d, "report.json"), "w"), indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    print("dir | n | correct | first | rescued | limit-wrong | silent | loud | calls | own right/misread/none | lock | score | score, limit as silent")
    for d in sys.argv[1:]:
        o = report(d)
        print(f"{d} | {o['n']} | {o['correct']} | {o['first_correct']} | {o['rescued']} | {o['limit on wrong query']} | {o['silent']} | {o['loud']} | {o['calls']} | "
              f"{o['own_text']['right']}/{o['own_text']['misread']}/{o['own_text']['none']} | {o['lock_errors']} | {o['selection_score']} | {o['selection_score_if_limit_lines_silent']} | {o['sha256_all_jsonl'][:12]}")
