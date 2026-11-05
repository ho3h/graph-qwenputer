"""X2.10 reference library: the tool functions of SPEC.md section 3, computed directly in Python.

This is the ground truth that the host-tool baseline prints and that the C library on the graph coprocessor (and
later the circuit) must equal byte for byte. It knows nothing about any domain: nodes, labels, relations, weights.
Closed nodes are transparent for splice relations (a walk passes through them) and absent otherwise; nothing is
rewritten, so close and reopen commute and are exactly reversible.
"""

import heapq
import inspect
import json
import os
import re
import unicodedata

MAX_STEPS, MAX_LEGS, MAX_W = 255, 16, 65535
TRAILING = ".,;:!?"                                            # SPEC 4: what the cleaner removes from a name's end, with whitespace
READING = "name read as "                                      # SPEC 4: the line that states a reading
UNFINISHED = " The journey did not finish."                    # SPEC 3: the end of a limit line of follow or chase


def norm(s):
    return unicodedata.normalize("NFC", s).strip()


def clean_tail(s):
    while s and (s[-1] in TRAILING or s[-1].isspace()):
        s = s[:-1]
    return s


def stop_line(kind, h_text, leg=None, k=None, s=None):
    """SPEC 3's limit lines for a graph with the noun field. kind END, MULTI or NOCHANGE; h_text '@h label'."""
    head = f"Stopped early on leg {leg}: " if leg else "Stopped early: "
    if kind == "END":
        return f"{head}after {s} steps at {h_text}, no further step along this relation exists.{UNFINISHED}"
    if kind == "NOCHANGE":
        return f"{head}at {h_text}, no change leads to that leg's relation.{UNFINISHED}"
    return f"{head}after {s} steps at {h_text}, there are {k} possible next steps, so the way on isn't unique.{UNFINISHED}"


OLD_STOP = re.compile(r"^(?:leg (\d+): )?(?:(END)|(MULTI) (\d+)|(NOCHANGE)) at (@\d+ .*?)(?: after (\d+) steps)?$", re.S)


def reword(line):
    """A saved line in the old form, in SPEC 3's form; any other line unchanged. For goldens written before the wording, so they rebuild mechanically."""
    m = OLD_STOP.match(line)
    if not m:
        return line
    return stop_line(m.group(2) or m.group(3) or m.group(5), m.group(6), m.group(1), m.group(4), m.group(7))


def split_reading(response):
    """SPEC 4: (the handles' lines read, the result without them). A response opens with its reading lines, if any; a result never starts with READING."""
    lines = response.split("\n")
    i = 0
    while i < len(lines) and lines[i].startswith(READING):
        i += 1
    return lines[:i], "\n".join(lines[i:])


class Graph:
    def __init__(self, g):
        assert g["format"] == "x210-graph/1"
        self.name = g["name"]
        self.labels = [n["label"] for n in g["nodes"]]
        self.props = [n.get("prop", 0) for n in g["nodes"]]
        self.rels = list(g["relations"])
        self.rix = {r: i for i, r in enumerate(self.rels)}
        self.splice = {self.rix[r] for r in g.get("splice", [])}
        self.change = self.rix[g["change"]] if g.get("change") else None
        self.out, self.inn = {}, {}
        for a, r, b, w in g["edges"]:
            self.out.setdefault((a, r), []).append((b, w))
            self.inn.setdefault((b, r), []).append((a, w))
        for d in (self.out, self.inn):
            for k in d:
                d[k].sort()
        self.by_label = {}
        for h, lab in enumerate(self.labels):
            self.by_label.setdefault(norm(lab), []).append(h)
        self.closed = set()
        self.cleaner = "noun" in g                              # SPEC 3 and 4: a graph file without the field keeps exact matching and the old limit lines
        self.noun = g.get("noun")
        self.reads = []

    @classmethod
    def load(cls, path):
        return cls(json.load(open(path)))

    def fmt(self, h):
        return f"@{h} {self.labels[h]}"

    # effective edges: closed nodes are passed through along splice relations and dropped otherwise
    def eff(self, h, r, d="out"):
        raw = self.out if d == "out" else self.inn
        best, seen = {}, set()
        pq = [(w, y) for y, w in raw.get((h, r), [])]         # cheapest first: weights through closed nodes are minimal
        heapq.heapify(pq)
        while pq:
            w, y = heapq.heappop(pq)
            if y not in self.closed:
                best.setdefault(y, w)
                continue
            if r not in self.splice or y in seen:
                continue
            seen.add(y)
            for z, v in raw.get((y, r), []):
                heapq.heappush(pq, (w + v, z))
        return sorted(best.items())

    def cleaned(self, arg):
        """SPEC 4, in order: the name without trailing punctuation, then also without the graph's noun as its last word."""
        c = clean_tail(arg)
        if c and c != arg:
            yield c
        n = self.noun
        if n and c.endswith(n) and len(c) > len(n) and c[-len(n) - 1].isspace():
            d = clean_tail(c[:-len(n)])
            if d:
                yield d

    def read_name(self, arg, match):
        """SPEC 4, only after `arg` matched nothing. The first cleaned form that matches anything decides: one node is the reading, several stay NONE."""
        if self.cleaner:
            for name in self.cleaned(arg):
                hs = match(name)
                if hs:
                    if len(hs) > 1:
                        return None
                    self.reads.append(hs[0])
                    return hs[0]
        return None

    def node(self, arg, has=None):
        """(handle, None) or (None, error line)."""
        arg = norm(arg)
        m = re.fullmatch(r"@(\d+)(?:\s+(.+))?", arg)          # "@h", or "@h label" as a response line prints it
        if m:
            h = int(m.group(1))
            if h >= len(self.labels) or (m.group(2) and m.group(2) != norm(self.labels[h])):
                return None, f"NONE {arg}"
            if h in self.closed:
                return None, f"CLOSED {self.fmt(h)}"
            return h, None
        hs = [h for h in self.by_label.get(arg, []) if h not in self.closed]
        if has is not None:
            hs = [h for h in hs if self.eff(h, has)]
        if not hs:
            h = self.read_name(arg, lambda name: [x for x in self.by_label.get(name, []) if x not in self.closed and (has is None or self.eff(x, has))])
            return (None, f"NONE {arg}") if h is None else (h, None)
        if len(hs) > 1:
            return None, f"AMBIGUOUS {len(hs)}: " + " | ".join(self.fmt(h) for h in hs)
        return hs[0], None

    def rel(self, name):
        name = norm(name)
        return (self.rix[name], None) if name in self.rix else (None, f"NORELATION {name}")

    # --- tool functions (SPEC 3); each returns the result text ---
    def find(self, name, has=None):
        r = None
        if has is not None:
            r, e = self.rel(has)
            if e:
                return e
        h, e = self.node(name, r)
        return e or self.fmt(h)

    def _follow(self, h, r, steps, leg=None):
        for s in range(steps):
            nxt = self.eff(h, r)
            if not nxt:
                if self.cleaner:
                    return h, stop_line("END", self.fmt(h), leg, None, s)
                return h, f"END at {self.fmt(h)} after {s} steps"
            if len(nxt) > 1:
                if self.cleaner:
                    return h, stop_line("MULTI", self.fmt(h), leg, len(nxt), s)
                return h, f"MULTI {len(nxt)} at {self.fmt(h)} after {s} steps"
            h = nxt[0][0]
        return h, None

    @staticmethod
    def steps_arg(x):
        try:
            n = int(str(x).strip())
        except ValueError:
            return None
        return n if 1 <= n <= MAX_STEPS else None

    def follow(self, node, relation, steps):
        r, e = self.rel(relation)
        if e:
            return e
        n = self.steps_arg(steps)
        if n is None:
            return f"BADARG steps {steps}"
        h, e = self.node(node)
        if e:
            return e
        h, e = self._follow(h, r, n)
        return e or self.fmt(h)

    def chase(self, start, legs, closed=None, reopened=None):
        if (closed is not None or reopened is not None) and not self.cleaner:
            return "BADARG chase"
        parts = [p.strip() for p in str(legs).split(";") if p.strip()]
        if not 1 <= len(parts) <= MAX_LEGS:
            return f"BADARG legs {legs}"
        plan = []
        for p in parts:
            m = re.fullmatch(r"(.+?)\s+(\d+)", p)
            if not m:
                return f"BADARG legs {legs}"
            r, e = self.rel(m.group(1))
            if e:
                return e
            n = self.steps_arg(m.group(2))
            if n is None:
                return f"BADARG legs {legs}"
            plan.append((r, n))
        if closed is not None or reopened is not None:
            head = []
            for verb, field in ((self.close, closed), (self.reopen, reopened)):      # SPEC 3: in order, each stated; a refused name ends the call there
                for name in str(field or "").split(";"):
                    if norm(name):
                        self.reads = []
                        line = verb(norm(name))
                        head += [f"{READING}{self.fmt(x)}" for x in self.reads]
                        head.append(line)
                        if line.startswith(("NONE ", "AMBIGUOUS ")):
                            self.reads = []
                            return "\n".join(head)
            self.reads = []
            rest = self.chase(start, legs)
            head += [f"{READING}{self.fmt(x)}" for x in self.reads]
            self.reads = []
            return "\n".join(head + [rest])
        h, e = self.node(start)
        if e and e.startswith("AMBIGUOUS ") and os.environ.get("T8_R1") == "1":      # exam/R1.md
            on = [x for x in self.by_label.get(norm(start), []) if x not in self.closed and self.eff(x, plan[0][0])]
            if len(on) == 1:
                h, e = on[0], None
        if e:
            return e
        for i, (r, n) in enumerate(plan, 1):
            if i > 1 and not self.eff(h, r):
                cand = [y for y, _ in self.eff(h, self.change)] if self.change is not None else []
                cand = [y for y in cand if self.eff(y, r)]
                if not cand:
                    return stop_line("NOCHANGE", self.fmt(h), i) if self.cleaner else f"leg {i}: NOCHANGE at {self.fmt(h)}"
                if len(cand) > 1:
                    return stop_line("MULTI", self.fmt(h), i, len(cand), 0) if self.cleaner else f"leg {i}: MULTI {len(cand)} at {self.fmt(h)} after 0 steps"
                h = cand[0]
            h, e = self._follow(h, r, n, i)
            if e:
                return e if self.cleaner else f"leg {i}: {e}"
        return self.fmt(h)

    def neighbours(self, node, relation, direction="out"):
        r, e = self.rel(relation)
        if e:
            return e
        if direction not in ("out", "in"):
            return f"BADARG direction {direction}"
        h, e = self.node(node)
        if e:
            return e
        ys = self.eff(h, r, direction)
        return "\n".join(self.fmt(y) for y, _ in ys) if ys else "NONE"

    def _all_out(self, h):
        """Effective out-edges over every relation: {target: min weight}."""
        best = {}
        for r in range(len(self.rels)):
            for y, w in self.eff(h, r):
                if y not in best or w < best[y]:
                    best[y] = w
        return best

    def _joined(self, hs):                                                  # exam/AFTER.md P, T8_R2
        if os.environ.get("T8_R2") != "1" or not 2 <= len(hs) <= 8 or self.change is None:
            return False
        out = {y for y, _ in self.out.get((hs[0], self.change), [])}
        return all(h in out for h in hs[1:])

    def _station(self, arg):
        arg = norm(arg)
        if re.fullmatch(r"@(\d+)(?:\s+(.+))?", arg):
            return None
        hs = [h for h in self.by_label.get(arg, []) if h not in self.closed]
        return hs if self._joined(hs) else None

    def _path_multi(self, A, B):
        common = sorted(set(A) & set(B))
        if common:
            return f"0 steps: {self.fmt(common[0])}"
        dist, level = {a: 0 for a in A}, sorted(A)
        while level and not set(B) & set(dist):
            nxt = set()
            for x in level:
                for y in self._all_out(x):
                    if y not in dist:
                        nxt.add(y)
            for y in nxt:
                dist[y] = dist[level[0]] + 1
            level = sorted(nxt)
        hit = [b for b in B if b in dist]
        if not hit:
            return "NOPATH"
        b = min(hit)
        seq = [b]
        while dist[seq[-1]] > 0:
            y = seq[-1]
            seq.append(min(x for x, d in dist.items() if d == dist[y] - 1 and y in self._all_out(x)))
        seq.reverse()
        return f"{dist[b]} steps: " + " > ".join(self.fmt(h) for h in seq)

    def path(self, frm, to):
        sa, sb = self._station(frm), None
        if sa is None:
            x, e = self.node(frm)
            if e:
                return e
            sa = [x]
        sb = self._station(to)
        if sb is None:
            x, e = self.node(to)
            if e:
                return e
            sb = [x]
        if len(sa) > 1 or len(sb) > 1:
            return self._path_multi(sa, sb)
        a, e = self.node(frm)
        if e:
            return e
        b, e = self.node(to)
        if e:
            return e
        dist, level = {a: 0}, [a]
        while level and b not in dist:
            nxt = set()
            for x in level:
                for y in self._all_out(x):
                    if y not in dist:
                        nxt.add(y)
            for y in nxt:
                dist[y] = dist[level[0]] + 1
            level = sorted(nxt)
        if b not in dist:
            return "NOPATH"
        seq = [b]
        while seq[-1] != a:                                    # lowest-handle predecessor in the previous level
            y = seq[-1]
            seq.append(min(x for x, d in dist.items() if d == dist[y] - 1 and y in self._all_out(x)))
        seq.reverse()
        return f"{dist[b]} steps: " + " > ".join(self.fmt(h) for h in seq)

    def cheapest(self, frm, to):
        a, e = self.node(frm)
        if e:
            return e
        b, e = self.node(to)
        if e:
            return e
        best, pred, done, pq = {a: 0}, {a: None}, set(), [(0, a)]
        while pq:
            c, x = heapq.heappop(pq)
            if x in done:
                continue
            done.add(x)
            for y, w in self._all_out(x).items():               # only finalised nodes relax: pred stays acyclic
                if y in done:
                    continue
                cy = c + w
                if y not in best or cy < best[y]:
                    best[y], pred[y] = cy, x
                    heapq.heappush(pq, (cy, y))
                elif cy == best[y] and x < pred[y]:
                    pred[y] = x
        if b not in best:
            return "NOPATH"
        if best[b] > MAX_W:
            return "OVERFLOW"
        seq = [b]
        while pred[seq[-1]] is not None:
            seq.append(pred[seq[-1]])
        seq.reverse()
        return f"cost {best[b]}: " + " > ".join(self.fmt(h) for h in seq)

    def close(self, node):
        hs = self._station(node)
        if hs:
            self.closed.update(hs)
            return "closed " + " | ".join(self.fmt(h) for h in hs)
        h, e = self.node(node)
        if e:
            return f"already closed {e[7:]}" if e.startswith("CLOSED ") else e
        self.closed.add(h)
        return f"closed {self.fmt(h)}"

    def reopen(self, node):
        m = re.fullmatch(r"@(\d+)(?:\s+(.+))?", norm(node))
        if m:
            h = int(m.group(1))
            hs = [h] if h < len(self.labels) and (not m.group(2) or m.group(2) == norm(self.labels[h])) else []
        else:
            every = self.by_label.get(norm(node), [])
            hs = [h for h in every if h in self.closed] or every
        if len(hs) > 1 and not m and self._joined(hs):
            if not any(h in self.closed for h in hs):
                return f"not closed {self.fmt(hs[0])}"
            self.closed.difference_update(hs)
            return "reopened " + " | ".join(self.fmt(h) for h in hs)
        if len(hs) > 1:
            return f"AMBIGUOUS {len(hs)}: " + " | ".join(self.fmt(h) for h in hs)
        if not hs and not m:
            def match(name):
                every = self.by_label.get(name, [])
                return [x for x in every if x in self.closed] or every
            h = self.read_name(norm(node), match)
            hs = [] if h is None else [h]
        if not hs:
            return f"NONE {norm(node)}"
        h = hs[0]
        if h not in self.closed:
            return f"not closed {self.fmt(h)}"
        self.closed.discard(h)
        return f"reopened {self.fmt(h)}"

    def link(self, frm, relation, to, weight="0"):
        r, e = self.rel(relation)
        if e:
            return e
        try:
            w = int(str(weight).strip())
        except ValueError:
            return f"BADARG weight {weight}"
        if not 0 <= w <= MAX_W:
            return f"BADARG weight {weight}"
        a, e = self.node(frm)
        if e:
            return e
        b, e = self.node(to)
        if e:
            return e
        if any(y == b for y, _ in self.out.get((a, r), [])):
            return f"already linked {self.fmt(a)} > {self.rels[r]} > {self.fmt(b)}"
        self.out.setdefault((a, r), []).append((b, w))
        self.out[(a, r)].sort()
        self.inn.setdefault((b, r), []).append((a, w))
        self.inn[(b, r)].sort()
        return f"linked {self.fmt(a)} > {self.rels[r]} > {self.fmt(b)}"

    def add_node(self, name):                                               # exam/AFTER.md P, T8_R2
        t = norm(str(name))
        if not t or len(t.encode()) > 31 or t.startswith("@"):
            return "BADARG name"
        hs = self.by_label.get(t)
        if hs:
            return f"already exists {self.fmt(hs[0])}"
        if getattr(self, "n_new", 0) >= 16 or len(self.labels) >= 1024:
            return "FULL"
        self.n_new = getattr(self, "n_new", 0) + 1
        h = len(self.labels)
        self.labels.append(t)
        self.props.append(0)
        self.by_label.setdefault(t, []).append(h)
        return f"added {self.fmt(h)}"

    def unlink(self, frm, relation, to):
        r, e = self.rel(relation)
        if e:
            return e
        a, e = self.node(frm)
        if e:
            return e
        b, e = self.node(to)
        if e:
            return e
        if not any(y == b for y, _ in self.out.get((a, r), [])):
            return f"not linked {self.fmt(a)} > {self.rels[r]} > {self.fmt(b)}"
        self.out[(a, r)] = [(y, w) for y, w in self.out[(a, r)] if y != b]
        self.inn[(b, r)] = [(x, w) for x, w in self.inn[(b, r)] if x != a]
        return f"unlinked {self.fmt(a)} > {self.rels[r]} > {self.fmt(b)}"

    def call(self, fn, args):
        f = {"find": self.find, "follow": self.follow, "chase": self.chase, "neighbours": self.neighbours,
             "path": self.path, "cheapest": self.cheapest, "close": self.close, "reopen": self.reopen,
             "link": self.link, "unlink": self.unlink, **({"add_node": self.add_node} if os.environ.get("T8_R2") == "1" else {})}.get(fn)
        if f is None:
            return f"NOFUNCTION {fn}"
        args = {("frm" if k == "from" else k): v for k, v in args.items()}
        try:
            inspect.signature(f).bind(**args)
        except TypeError:
            return f"BADARG {fn}"
        self.reads = []
        out = f(**args)
        return "".join(f"{READING}{self.fmt(h)}\n" for h in self.reads) + out
