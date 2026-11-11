"""What flow changes would do to chain3's records, by arithmetic on the saved tokens. No model. Run: python3 flowsim.py

For each question, tokens that Qwen's layers would still see under each flow, at chain3's fitted cost per token. Also what final line each gives, where the records can say.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "..", "rvc", "results", "chain3", "all.jsonl")
LIMIT = re.compile(r"^(?:leg \d+: )?(END|MULTI|NOCHANGE|CLOSED|NOPATH)\b")
ERROR = re.compile(r"^(?:leg \d+: )?(NORELATION|NONE|AMBIGUOUS|BADARG|END|MULTI|NOCHANGE|CLOSED|NOPATH|NOFUNCTION|OVERFLOW|TOOLONG)\b")
SEC_PER_TOKEN = 0.104     # chain3, text_seconds over qwen + echo tokens, executor questions, shared
rs = [json.loads(line) for line in open(P)]
ex = [r for r in rs if not r["verified_positions"]]


def tokens(r, limit_stop=False, cap=None, lazy=False):
    """Text steps through Qwen's layers, and the final line, under the flow. Prose before a call in an attempt isn't saved per attempt; the question's prose is taken as one attempt where there are 2 calls or a no_call, and spread evenly over the retries at 3 calls."""
    calls = r["calls"]
    prose = r["qwen_tokens"] - sum(len(c["ids"]) + 2 for c in calls)
    first = calls[0]
    # attempt list: (prose before this call, call tokens, echo)
    atts = []
    nc = r["status"] == "no_call"
    retries = len(calls) - 1
    for i, c in enumerate(calls):
        pre = 0 if i == 0 else (prose // retries if retries else 0)
        atts.append((pre, len(c["ids"]) + 2, c["echo"], c.get("result", "")))
    tail = prose if nc else 0                               # the prose attempt that never called
    steps = 0
    final = None
    for i, (pre, ct, echo, line) in enumerate(atts):
        if cap is not None and pre + ct > cap:              # this attempt is cut: it never calls, and the turn ends with the last line
            steps += cap
            return steps, final, True
        steps += pre + ct
        final = line
        clean = not ERROR.match(line)
        stop = clean or i == 2 or (limit_stop and LIMIT.match(line))
        if lazy and stop:
            return steps, final, False
        steps += echo
        if stop:
            return steps, final, False
    if tail:
        steps += min(tail, cap) if cap is not None else tail
    return steps, final, False


def row(name, **kw):
    t = lost = changed = 0
    for r in ex:
        s, f, cut = tokens(r, **kw)
        t += s
        if f != r["final"]:
            changed += 1
            if r["correct"]:
                lost += 1
    base = sum(r["qwen_tokens"] + r["echo_tokens"] for r in ex)
    return {"flow": name, "text_steps": t, "of": base, "share": round(t / base, 3), "seconds_per_question_text": round(t * SEC_PER_TOKEN / len(ex), 1), "finals_changed": changed, "correct_lost": lost}


out = [row("chain3"), row("limit lines end the turn", limit_stop=True), row("cap 768 (same)", cap=768), row("cap 320", cap=320), row("cap 256", cap=256), row("cap 96", cap=96), row("limit stop + cap 256", limit_stop=True, cap=256), row("limit stop + cap 96", limit_stop=True, cap=96),
       row("print: no echo after the last line", lazy=True), row("limit stop + cap 320 + no last echo", limit_stop=True, cap=320, lazy=True), row("limit stop + cap 256 + no last echo", limit_stop=True, cap=256, lazy=True), row("limit stop + cap 96 + no last echo", limit_stop=True, cap=96, lazy=True)]
clean = [r for r in ex if r["status"] == "answered" and r["n_calls"] == 1]
res = {"questions": len(ex), "sec_per_token_shared": SEC_PER_TOKEN, "flows": out, "clean_one_call": {"n": len(clean), "qwen_mean": round(sum(r["qwen_tokens"] for r in clean) / len(clean), 1), "echo_mean": round(sum(r["echo_tokens"] for r in clean) / len(clean), 1), "s_mean": round(sum(r["seconds"] for r in clean) / len(clean), 1)}, "note": "arithmetic on chain3's saved tokens, shared GPU; prose per attempt is not saved, so 3-call questions spread it evenly"}
json.dump(res, open(os.path.join(HERE, "results", "flowsim.json"), "w"), indent=1)
for x in out:
    print(x)
print(res["clean_one_call"])
