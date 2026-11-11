#!/usr/bin/env python3
"""Sampling as Qwen3.5-4B's model card recommends for thinking mode (README.md lines 835 and 836 of the model folder):
general tasks:        temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0
precise coding tasks: temperature=0.6, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0, repetition_penalty=1.0

The presence penalty is taken from the logit of every token already in the reply, as vLLM applies it (the reply only, not the
prompt). Then temperature, then the 20 most likely tokens, then the smallest set of those that holds 0.95 of the probability.

    python3 exam/card_sample.py      (the checks below, no model)
"""
import torch

TOP_P, TOP_K = 0.95, 20
PROFILES = {"general": (1.0, 1.5), "precise": (0.6, 0.0)}           # name: (temperature, presence penalty)


def pick(logits, seen, gen, profile="general"):
    """One token id from one row of logits. `seen` is the set of ids already in the reply. `gen` is a CPU torch.Generator."""
    temperature, presence = PROFILES[profile]
    z = logits.detach().float().clone()
    if seen and presence:
        z[torch.tensor(sorted(seen), device=z.device)] -= presence
    v, i = torch.topk(z / temperature, TOP_K)                       # sorted, most likely first
    p = torch.softmax(v.cpu(), -1)
    keep = (torch.cumsum(p, -1) - p) < TOP_P                        # every token before the one that carries the sum past TOP_P, and that one
    p = p * keep
    return int(i.cpu()[torch.multinomial(p / p.sum(), 1, generator=gen)])


if __name__ == "__main__":
    g = lambda s=0: torch.Generator().manual_seed(s)  # noqa: E731
    n = 1000
    z = torch.zeros(n)
    z[7] = 30.0
    assert all(pick(z, set(), g(s)) == 7 for s in range(50)), "one dominant token"
    z = torch.arange(n, dtype=torch.float) * 0.01                   # nearly flat: the 20 largest are ids 980..999
    draws = [pick(z, set(), g(s)) for s in range(400)]
    assert min(draws) >= n - TOP_K and len(set(draws)) > 10, "top-k keeps exactly the 20 most likely"
    z = torch.full((n,), -50.0)
    z[1], z[2], z[3] = torch.log(torch.tensor([0.96, 0.03, 0.01]))
    assert all(pick(z, set(), g(s)) == 1 for s in range(300)), "top-p: 0.96 alone passes 0.95, so the tail is cut"
    z[1], z[2], z[3] = torch.log(torch.tensor([0.90, 0.07, 0.03]))
    draws = [pick(z, set(), g(s)) for s in range(600)]
    assert set(draws) == {1, 2}, ("top-p: 0.90 + 0.07 passes 0.95, so the third token is cut", set(draws))
    assert 0.88 < draws.count(1) / 600 < 0.97, draws.count(1) / 600   # 0.90 / 0.97 = 0.928
    z = torch.full((n,), -50.0)
    z[4], z[5] = 1.0, 1.0
    free = [pick(z, set(), g(s)) for s in range(600)].count(4) / 600
    pen = [pick(z, {4}, g(s)) for s in range(600)].count(4) / 600
    assert 0.44 < free < 0.56 and 0.14 < pen < 0.23, (free, pen)       # e^-1.5 / (1 + e^-1.5) = 0.182
    a, b = g(5), g(5)
    z = torch.randn(n, generator=g(9))
    assert [pick(z, set(), a) for _ in range(30)] == [pick(z, set(), b) for _ in range(30)], "the same seed gives the same draws"
    zb = z.to(torch.bfloat16)
    before = zb.clone()
    pick(zb, {1, 2, 3}, g())
    assert torch.equal(zb, before), "the caller's logits are not changed"
    z = torch.full((n,), -50.0)
    z[4], z[5] = 1.0, 0.4                                           # at temperature 0.6 the gap of 0.6 becomes 1.0: 0.731 to 0.269
    cold = [pick(z, {4}, g(s), "precise") for s in range(800)].count(4) / 800
    assert 0.69 < cold < 0.77, cold                                 # and "precise" has no presence penalty, so `seen` changes nothing
    print("card_sample: 9 checks pass")
