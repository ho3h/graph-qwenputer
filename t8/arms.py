"""T8's five fixes and the comparison rule, as an overlay on reflib. reflib, SPEC and firmware are not touched. No model here."""
import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT / "host"), str(ROOT / "lib")]
import reflib  # noqa: E402
import tools as HT  # noqa: E402

assert Path(HT.__file__).parent.name == "host", HT.__file__
CHAIN3 = json.load(open(ROOT / "rvc" / "results" / "chain3" / "meta.json"))
EXTRA, TOLD = CHAIN3["extra"], CHAIN3["told"]
CHASE = [t for t in HT.tools_for("base") if t["function"]["name"] == "chase"][0]
assert CHASE == CHAIN3["tool"]
LOUD = r"NORELATION|NONE|AMBIGUOUS|BADARG|NOFUNCTION|TOOLONG|BADQUERY"
LIMIT = r"END|MULTI|NOCHANGE|CLOSED|NOPATH|OVERFLOW"
LOUD_LINE = re.compile(rf"^(?:leg \d+: )?({LOUD})\b")
LIMIT_LINE = re.compile(rf"^(?:(?:leg \d+: )?({LIMIT})\b|Stopped early\b)")   # SPEC 3's words too


def system(g):
    """chain3's system message, unchanged: the told sentence stays in though nothing is spelled out here, as ctrl's a1_told and a4_host."""
    return HT.system_prompt(g) + EXTRA + TOLD


# --- Arm 1: clear syntax with worked examples. Made-up names; `panels_check` below confirms none is a label on any dev graph or in pool 1.
A1_CONTRAST = ("the start node: its handle such as @12, or its name alone. Format, with examples: start: Mill Lane, not Mill Lane station. "
               "start: Oskar Hill-9 Av, not Oskar Hill-9 Av with a full stop after it. start: Tarn Rd, not Out of Tarn Rd.")
A1_FORMAT = (" Format: start holds the name only, and legs holds 'relation n' parts joined by semicolons. Examples: "
             "'Start at Mill Lane station. Ride the K train 2 stops northbound.' gives start: Mill Lane, legs: K northbound 2. "
             "'Leave from Oskar Hill-9 Av. Take Z north for one hop, then R south for 3.' gives start: Oskar Hill-9 Av, legs: Z north 1; R south 3. "
             "'Out of Tarn Rd, Q east for 4 stops.' gives start: Tarn Rd, legs: Q east 4.")


def tool(variant=None):
    t = copy.deepcopy(CHASE)
    if variant == "C":
        t["function"]["parameters"]["properties"]["start"]["description"] = A1_CONTRAST
    elif variant == "B":
        t["function"]["description"] += A1_FORMAT
    else:
        assert variant is None
    return t


# --- The comparison: the broad rule, ctrl/classes.py's words. Longest label appearing as whole words inside the written name, if only one and it names one node.
def read_broad(graph, written):
    words = reflib.norm(str(written)).split()
    for size in range(len(words), 0, -1):
        found = {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)} & set(graph.by_label)
        if found:
            if len(found) > 1:
                return None
            label = found.pop()
            return label if len(graph.by_label[label]) == 1 else None
    return None


def read_broad_recount(graph, written):
    """t8/recount.py's reading, the one behind the 38 right, 19 wrong: whole words by regex, so a full stop or hyphen ends a word. Longest label inside the name, if only one of that length."""
    w = [l for l in graph.by_label if re.search(r"(?<!\w)" + re.escape(l) + r"(?!\w)", reflib.norm(str(written)))]
    if not w:
        return None
    m = max(map(len, w))
    w = [l for l in w if len(l) == m]
    return w[0] if len(w) == 1 and len(graph.by_label[w[0]]) == 1 else None


# --- Arm 3: the strict cleaner. Only trailing punctuation and the graph's own noun for a node (one boot value), then an exact match.
TRAIL = ".,;:!?"
NOUN = {"cities": "station", "random": None}


def noun_of(g):
    """The per-graph boot value. Cities: 'station'. Random graphs have no noun for a node."""
    return NOUN["cities"] if g["name"].startswith("c") else NOUN["random"]


def read_strict(graph, written, noun):
    s = reflib.norm(str(written)).rstrip(TRAIL).rstrip()
    if noun and s.endswith(" " + noun):
        s = s[: -len(noun) - 1].rstrip().rstrip(TRAIL).rstrip()
    hs = graph.by_label.get(s, [])
    return s if len(hs) == 1 else None


def overlay(graph, args, line, read):
    """(the response text, the graded line, the reading or None). `read` runs only on NONE for the written start of a chase. The response states the reading."""
    start, legs = args.get("start"), args.get("legs")
    if start is None or legs is None or line != f"NONE {reflib.norm(str(start))}":
        return line, line, None
    label = read(graph, start)
    if label is None:
        return line, line, None
    res = graph.chase(label, legs)
    return f'read "{reflib.norm(str(start))}" as "{label}"\n{res}', res, label


# --- Arm 2: "did you mean". A general measure: Dice on letter pairs, case folded. No word lists.
THRESHOLD, TOP = 0.5, 3


def pairs(s):
    s = s.casefold()
    return Counter(s[i:i + 2] for i in range(len(s) - 1))


def dice(a, b):
    pa, pb = pairs(a), pairs(b)
    if not pa or not pb:
        return 0.0
    return 2 * sum((pa & pb).values()) / (sum(pa.values()) + sum(pb.values()))


def closest(graph, written):
    """[(score, handle, label)], best first, ties by lowest handle, at most TOP with score >= THRESHOLD. A label several nodes share counts once per node."""
    w = reflib.norm(str(written))
    scored = sorted(((-dice(w, l), h) for h, l in enumerate(graph.labels)))
    return [(round(-s, 3), h, graph.labels[h]) for s, h in scored[:TOP] if -s >= THRESHOLD]


def did_you_mean(graph, line, written):
    """The response, or the plain line when nothing is close."""
    near = closest(graph, written)
    if not near:
        return line, near
    return line + "\nNo node has exactly that name. Closest: " + " | ".join(f"@{h} {l}" for _, h, l in near), near


RETRY_CAP = 40

# --- The comparison from rvc/chain4.py's `both`: its fixed note, word for word, and its list of query errors.
NOTE_G = "No node has exactly that name; call again with only the node's name, without any word that just describes it."
QUERY_ERRORS = {"NONE", "NORELATION", "AMBIGUOUS", "BADARG", "NOFUNCTION", "TOOLONG"}


def query_error(line):
    """The error word if the query itself failed, else None. Limit lines are results."""
    m = LOUD_LINE.match(line) if line else None
    return m.group(1) if m and m.group(1) in QUERY_ERRORS else None


# --- Arm 4: find the names first. Whole-word scan of the question, longest match wins where matches overlap; matches of equal length that overlap are both listed.
def scan(graph, text):
    """[(position, label)] in order of appearance, one entry per label."""
    hits = []
    for label in graph.by_label:
        for m in re.finditer(r"(?<![\w])" + re.escape(label) + r"(?![\w])", text):
            hits.append((m.start(), m.end(), label))
    keep = []
    for a in hits:
        if any(b is not a and b[0] <= a[0] and a[1] <= b[1] and (b[1] - b[0]) > (a[1] - a[0]) for b in hits):
            continue
        keep.append(a)
    seen, out = set(), []
    for s, _, label in sorted(keep):
        if label not in seen:
            seen.add(label)
            out.append((s, label))
    return out


def names_line(graph, text):
    """The one short line Qwen is given, or None when the scan finds nothing."""
    found = scan(graph, text)
    if not found:
        return None
    return "Names in this question: " + " | ".join(f"@{h} {label}" for _, label in found for h in graph.by_label[label])


# --- Arm 5: guided typing. Only in the start field: once the text exactly equals a complete label and no longer label continues it, the field ends.
class Guide:
    MARK = "<parameter=start>\n"

    def __init__(self, graph):
        self.labels = set(graph.by_label)
        self.continues = set()
        for label in self.labels:
            for i in range(1, len(label)):
                self.continues.add(label[:i])

    def field(self, text):
        i = text.rfind(self.MARK)
        if i < 0:
            return None
        rest = text[i + len(self.MARK):]
        return None if "\n" in rest or "</parameter>" in rest else rest

    def fires(self, text):
        f = self.field(text)
        return f is not None and f in self.labels and f not in self.continues


# --- Scoring
def strip_leg(s):
    return re.sub(r"^leg \d+: ", "", s) if s is not None else None


def outcome(line, gold):
    """Exact line, leg prefix ignored (T6, Theo: strict)."""
    if line is not None and strip_leg(line) == strip_leg(gold):
        return "right"
    if line is None or LOUD_LINE.match(line):
        return "loud"
    return "limit" if LIMIT_LINE.match(line) else "silent"


def route(args):
    """The written legs as [[relation, n]], or None if they do not read that way."""
    legs = (args or {}).get("legs")
    if legs is None:
        return None
    out = []
    for p in legs.split(";"):
        if not p.strip():
            continue
        m = re.fullmatch(r"(.+?)\s+(\d+)", p.strip())
        if not m:
            return None
        out.append([m.group(1), int(m.group(2))])
    return out


def graph_json(name):
    assert "heldout" not in name
    sub = "cities" if name.startswith("c") else "random"
    return json.load(open(ROOT / "data" / "dev" / sub / f"{name}.graph.json"))
