"""What the machine would print for a response line, in Qwen's tokens: parts joined by a fixed rule, no tokenizer on the line.

A line is a list of parts:
  ("lit", s)     a fixed word of the firmware, tokenized once at build
  ("num", n)     digits, one digit token each
  ("fmt", h)     @h label: `@` or ` @`, digits, then the label's stored tokens (tokenized once at boot with a leading space)
  ("rel", r)     a relation's stored tokens, the same way
  ("arg", b)     bytes echoed from the call: one byte token each, because the machine holds a call's bytes, not its token ids

A space before a part is held back ("pending") and joins the part, as the tokenizer's regex joins it: ` @`, ` find`, a label's own
leading space. Before digits and bytes it stays a space token.
"""
import re

HEAD = "<|im_end|>\n<|im_start|>user\n<tool_response>\n"
TAIL = "\n</tool_response><|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
ARG_PREFIX = ("NORELATION ", "NOFUNCTION ", "NONE ", "BADARG steps ", "BADARG legs ", "BADARG direction ", "BADARG weight ")
AT = re.compile(r"@(\d+) ")


class Frag:
    def __init__(self, tok, printable_bytes):
        """tok: tokenizers.Tokenizer; printable_bytes: byte value -> the byte's token id (bridge.Text.printable[:256])."""
        self.tok, self.b = tok, printable_bytes
        self.cache = {}
        self.SP = printable_bytes[32]

    def enc(self, s):
        v = self.cache.get(s)
        if v is None:
            v = self.tok.encode(s, add_special_tokens=False).ids
            self.cache[s] = v
        return v

    def digits(self, n):
        return [self.b[c] for c in str(n).encode()]

    def label(self, s):
        return self.enc(" " + s)

    def tokens(self, parts, labels, rels):
        out, pending = [], False
        for kind, v in parts:
            if kind == "lit":
                s = v
                strip = s.endswith(" ")
                if strip:
                    s = s[:-1]
                if s:
                    out += self.enc((" " if pending else "") + s)
                    pending = strip
                else:
                    pending = True
            elif kind == "num":
                if pending:
                    out.append(self.SP)
                    pending = False
                out += self.digits(v)
            elif kind == "fmt":
                out += self.enc(" @" if pending else "@") + self.digits(v) + self.label(labels[v])
                pending = False
            elif kind == "rel":
                out += self.label(rels[v])
                pending = False
            elif kind == "arg":
                if pending:
                    out.append(self.SP)
                    pending = False
                out += [self.b[c] for c in v]
        assert not pending, parts
        return out

    def wrapped(self, parts, labels, rels):
        return self.enc(HEAD) + self.tokens(parts, labels, rels) + self.enc(TAIL)


def parse(line, labels, relmap):
    """The parts of one result line (a machine or host line, possibly several joined by newlines); None if it has no reading."""
    for p in ARG_PREFIX:
        if line.startswith(p):
            return [("lit", p), ("arg", line[len(p):].encode("utf-8", "surrogateescape"))]
    parts = []
    for li, one in enumerate(line.split("\n")):
        if li:
            parts.append(("lit", "\n"))
        i = 0
        while i < len(one):
            m = AT.match(one, i)
            if m and int(m[1]) < len(labels) and one.startswith(labels[int(m[1])], m.end()):
                parts.append(("fmt", int(m[1])))
                i = m.end() + len(labels[int(m[1])])
                continue
            n = AT.search(one, i + 1)
            lit = one[i: n.start() if n else len(one)]
            if not _literal(lit, parts, relmap):
                return None
            i += len(lit)
    return parts


NUM_LIT = re.compile(r"(\d+)")


def _literal(lit, parts, relmap):
    """Fixed words and numbers; ` > relation > ` of a link line. Words stay as the firmware would hold them, split at numbers."""
    m = re.fullmatch(r" > (.+) > ", lit)
    if m and m[1] in relmap:
        parts += [("lit", " > "), ("rel", relmap[m[1]]), ("lit", " > ")]
        return True
    for piece in NUM_LIT.split(lit):
        if not piece:
            continue
        if piece.isdigit():
            parts.append(("num", int(piece)))
        else:
            parts.append(("lit", piece))
    return True
