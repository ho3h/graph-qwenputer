#!/usr/bin/env python3
"""exam/AFTER.md round 18 from saved rows: the reasoning-on baselines, beside the reasoning-off rows of the same questions.

    python3 exam/score_think.py DIR   (reads DIR/A.jsonl, DIR/M.jsonl and DIR/P.jsonl, writes DIR/score.json)

Arm A is Qwen alone, arm M has the map and the list-each-stop instruction, arm P (10 Nov) has the map and the plain question.

right, wrong, unfinished: the normalised marking, registered 10 Nov before any row of the revision. It drives the page rules.
    Normalising removes * ` quotation marks and angle brackets, a final "station" and a final full stop, and ignores case.
    Arm M: the answer is the rest of the last line that holds "answer:". Arms A and P: the answer is the first or the last line.
    A row is right when Qwen closed its reasoning and the answer equals the station's name. A row that isn't right is wrong when
    Qwen closed its reasoning and stopped by itself (and, on arm M, wrote an answer line). Otherwise it is unfinished.
strict_*: the marking of 9 Nov. Arm A as score_after.py marks Qwen alone, arm M as score_mapped.py marks M1.
generous: the name appears in the reply (arms A and P) or in the 'Answer:' line (arm M).
"""
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AFTER = os.path.join(HERE, "results", "after")
LINE = re.compile(r"(?i)answer\s*[:：]\s*(.*)$")


def norm(s):
    s = re.sub(r"\s+", " ", re.sub(r"[*`\"'“”‘’<>]", "", s)).strip()
    s = re.sub(r"\.$", "", s).strip()
    s = re.sub(r"(?i)\s+station$", "", s).strip()
    return re.sub(r"\.$", "", s).strip().casefold()


def answers(text, arm):
    """The candidate answers in a reply. Arm M: what follows the last 'answer:'. Arms A and P: the first and the last line."""
    lines = [x for x in (y.strip() for y in text.replace("*", "").replace("`", "").split("\n")) if x]
    if arm == "M":
        hits = [m.group(1) for m in (LINE.search(x) for x in lines) if m]
        return hits[-1:]
    return [LINE.search(x).group(1) if LINE.search(x) else x for x in (lines[:1] + lines[-1:])]


def mark(text, arm, want, closed, stopped):
    a = answers(text, arm) if closed else []
    if any(norm(x) == norm(want) for x in a):
        return "right"
    return "wrong" if closed and stopped and a else "unfinished"


def rows(p):
    out = []
    for line in open(p, encoding="utf-8"):
        try:
            out.append(json.loads(line))
        except ValueError:                                          # a last line cut short by a kill
            pass
    return out


def loops(ids, n=64):
    """The last n token ids already occur earlier in the row: Qwen was repeating itself when the cap came."""
    if len(ids) < 2 * n:
        return False
    tail, first = ids[-n:], ids[-n]
    return any(ids[i] == first and ids[i:i + n] == tail for i in range(len(ids) - n))


def off_rows():
    """The reasoning-off rows of the chart, marked the same way. Qwen alone was cut at 40 tokens, the map arm at 1,024."""
    cut = set(json.load(open(os.path.join(AFTER, "alone_cut40.json")))["cut_ids"])
    a = {r["id"]: mark(r["final"], "A", r["gold_text"].split(" ", 1)[1], True, r["id"] not in cut) for r in rows(os.path.join(AFTER, "alone.jsonl"))}
    m = {r["id"]: mark(r["text_out"], "M", r["gold"].split(" ", 1)[1], True, r["new_tokens"] < 1024) for r in rows(os.path.join(AFTER, "mapped", "M1.jsonl"))}
    return a, m


def main(D):
    off_a, off_m = off_rows()
    out = {}
    for arm in ("A", "M", "P"):
        p = os.path.join(D, arm + ".jsonl")
        if not os.path.exists(p):
            continue
        c = {"n": 0, "right": 0, "wrong": 0, "unfinished": 0, "strict_right": 0, "strict_wrong": 0, "strict_unfinished": 0, "generous": 0,
             "never_closed_reasoning": 0, "hit_cap": 0, "unfinished_repeating": 0, "seconds": 0.0, "new_tokens": 0}
        off = {"right": 0, "wrong": 0, "unfinished": 0}
        pair, thought, new, meta, ids, disputed = {}, [], [], set(), [], []
        apart = {"right": 0, "wrong": 0, "unfinished": 0}             # without questions 103 and 108, whose map lines the practice questions used
        for r in rows(p):
            assert r["gold"].startswith("@") and r["arm"] == arm
            want = r["gold"].split(" ", 1)[1]
            meta.add((r.get("decode", "greedy"), r["cap"]))
            c["n"] += 1
            c["seconds"] += r["seconds"]
            c["new_tokens"] += r["new_tokens"]
            new.append(r["new_tokens"])
            closed = r["thought_tokens"] is not None
            c["never_closed_reasoning"] += not closed
            c["hit_cap"] += not r["stopped"]
            text = r["after_think"]
            if arm == "M":
                ans = text.rsplit("Answer:", 1)[1].replace("*", "").strip() if "Answer:" in text else ""
                fin = closed and r["stopped"] and "Answer:" in text
                strict = closed and ans.rstrip(".").strip() == want
            else:
                ans, fin = text.strip(), closed and r["stopped"]
                strict = fin and ans.rstrip(".").strip() == want
            c["strict_" + ("right" if strict else "wrong" if fin else "unfinished")] += 1
            now = mark(text, arm, want, closed, r["stopped"])
            c[now] += 1
            ids.append(r["id"])
            apart[now] += r["id"] not in (103, 108)
            if now != "right" and closed and r["stopped"] and want in text:
                disputed.append(r["id"])                            # stopped, holds the right name, not marked right: listed for a reader to judge
            c["generous"] += bool(closed and want in ans)
            c["unfinished_repeating"] += now == "unfinished" and loops(r.get("ids", []))
            if closed:
                thought.append(r["thought_tokens"])
            was = (off_a if arm == "A" else off_m)[r["id"]]
            off[was] += 1
            pair[was + " to " + now] = pair.get(was + " to " + now, 0) + 1
        thought.sort()
        new.sort()
        c["median_thought_tokens"] = statistics.median(thought) if thought else None   # until 10 Nov, 15:45 ET this took the upper middle value
        c["median_new_tokens"] = statistics.median(new) if new else None
        c["seconds"] = round(c["seconds"], 1)
        fin_n = c["right"] + c["wrong"]
        c["right_share_of_finished"] = round(c["right"] / fin_n, 3) if fin_n else None
        c["right_share"] = round(c["right"] / c["n"], 3) if c["n"] else None
        c["unfinished_share"] = round(c["unfinished"] / c["n"], 3) if c["n"] else None
        assert len(meta) <= 1 and len(set(ids)) == len(ids), (arm, meta, "two runs or a repeated question in one file")
        assert ids == list(range(100, 100 + len(ids))), (arm, "the rows are not the first questions in file order")
        c["decode_and_cap"] = sorted(meta)
        c["first_and_last_id"] = [ids[0], ids[-1]] if ids else None
        c["without_103_and_108"] = apart
        c["stopped_with_the_right_name_but_not_marked_right"] = disputed
        c["reasoning_off_same_questions"] = off
        c["reasoning_off_prompt"] = "the question alone, 40-token limit" if arm == "A" else "the map and the list-each-stop instruction, 1,024-token limit"
        c["off_to_on"] = dict(sorted(pair.items()))
        assert c["right"] + c["wrong"] + c["unfinished"] == c["n"] == c["strict_right"] + c["strict_wrong"] + c["strict_unfinished"]
        out[arm] = c
    return out


if __name__ == "__main__":
    if sys.argv[1] == "--check":
        a, m = off_rows()
        tally = lambda d: {k: sum(v == k for v in d.values()) for k in ("right", "wrong", "unfinished")}  # noqa: E731
        two = {q["id"] for q in json.load(open(os.path.join(HERE, "..", "data", "heldout", "nyc", "nyc.questions.json")))["questions"] if q["orig_kind"] == "two"}
        ta, tm = tally({k: v for k, v in a.items() if k in two}), tally(m)
        assert ta == {"right": 1, "wrong": 88, "unfinished": 11}, ta
        assert tm == {"right": 54, "wrong": 36, "unfinished": 10}, tm
        for text, arm, ok in (("**Answer**: Canal St", "M", 1), ("1. A\n2. B\n**Final Answer**: **Canal St**", "M", 1), ("answer: Canal St", "M", 1), ("Answer: `Canal St`", "M", 1),
                              ("Answer: <Canal St>", "M", 1), ("Answer: Canal St station.", "M", 1), ("Answer: Canal St\n\nThis is the stop.", "M", 1), ("Answer: Canal Street", "M", 0),
                              ("Answer: 14 St-Union Sq", "M", 0), ("Canal St", "A", 1), ("**Canal St**", "P", 1), ("Canal St.", "P", 1), ("Answer: Canal St", "P", 1),
                              ("The stops are A and B.\n\nCanal St", "P", 1), ("Canal St\n\n(3 stops on the 1 train)", "P", 1), ("You are at Canal St.", "P", 0), ("canal st station", "A", 1)):
            got = mark(text, arm, "Canal St", True, True)
            assert (got == "right") == bool(ok), (text, arm, got)
        assert mark("Answer: 14 St", "M", "14 St", False, True) == "unfinished" and mark("Houston St", "A", "Canal St", True, False) == "unfinished"
        assert mark("1. A\n2. B", "M", "Canal St", True, True) == "unfinished" and mark("Answer: Houston St", "M", "Canal St", True, True) == "wrong"
        print("score_think: reasoning off reproduces 1/88/11 and 54/36/10; 21 marking checks pass")
        sys.exit(0)
    res = main(sys.argv[1])
    json.dump(res, open(os.path.join(sys.argv[1], "score.json"), "w"), indent=1)
    print(json.dumps(res))
