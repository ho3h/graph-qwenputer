"""The frozen worked turns teach a closure the old way, with the train running through. On the blocking rule, the same two turns show what the firmware now prints. t8/fw/worked.py stays as a freeze hashes it."""
STOPPED = "Stopped early on leg 1: after 0 steps at {}, no further step along this relation exists. The journey did not finish."
SWAPS = (("closed @7 Elm Sq\n@9 Birch Av", "closed @7 Elm Sq\n" + STOPPED.format("@3 Ash Rd"), "Birch Av", "The train stops early at Ash Rd."),
         ("closed @5 Oak Av\n@3 Ash Rd", "closed @5 Oak Av\n" + STOPPED.format("@9 Birch Av"), "Ash Rd", "The train stops early at Birch Av."))


def blocking(history):
    """The same turns, with the two closure results and their replies on the blocking rule."""
    out = [dict(m) for m in history]
    for old, new, old_reply, new_reply in SWAPS:
        i = next(j for j, m in enumerate(out) if m["role"] == "tool" and m["content"] == old)
        assert out[i + 1]["role"] == "assistant" and out[i + 1]["content"] == old_reply
        out[i], out[i + 1] = dict(out[i], content=new), dict(out[i + 1], content=new_reply)
    return out
