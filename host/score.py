"""The one scoring rule of the host-tool baseline (and of every later run scored against it)."""

import re
import unicodedata


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def wants_handle(q: dict) -> bool:
    """A question asks for handles when its record says so (`answer_form: "handle"`); SPEC's question format has
    no such field yet, so absent means labels."""
    return q.get("answer_form") == "handle"


def score(final: str | None, q: dict, labels: list[str]) -> bool | None:
    """Correct when the final answer contains, for every gold handle h in q["answer"], the gold label labels[h]
    (case-sensitive, after NFC on both sides), or the handle written '@h' (not followed by another digit) when
    the question asks for handles. An occurrence inside a longer canonical label does not count: for gold
    "Falcon Av", the answer "Falcon Av/14 St" is wrong. Order is not checked, and each label needs to appear once
    even if the gold lists it twice. No final answer (cap, budget, no end of turn) is wrong. An empty gold list
    (NONE, NOPATH, BADARG and the like) cannot be scored by this rule and returns None."""
    gold = q.get("answer") or []
    if not gold:
        return None
    if final is None:
        return False
    text = nfc(final)
    canon = {nfc(x) for x in labels}
    for h in gold:
        if wants_handle(q):
            if not re.search(rf"@{h}(?!\d)", text):
                return False
            continue
        lab = nfc(labels[h])
        rest = text
        for longer in sorted((x for x in canon if lab in x and x != lab), key=len, reverse=True):
            rest = rest.replace(longer, "\0")
        if lab not in rest:
            return False
    return True
