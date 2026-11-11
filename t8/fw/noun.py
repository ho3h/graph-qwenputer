"""The side copy of graph data for now: today's graph file plus the noun, in memory. No graph file is written. The rule is SPEC 1's, the builder's (data/build/common.py)."""
NOUN_BY_DOMAIN = {"transit": "station"}


def with_noun(g):
    g = dict(g)
    g["noun"] = NOUN_BY_DOMAIN.get(g.get("domain"))
    return g
