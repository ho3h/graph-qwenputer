"""A drive.py run against the host transcripts: scores, tokens against the real tokenizer on forced_text, and whether the whole question equals the host's.

    python tok/compare_host.py --in tok/results/t6 --out tok/results/t6_compare.json
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X210 = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(X210, "host"), os.path.join(X210, "vendor", "qwenputer-riscv"), HERE]
from tokenizers import Tokenizer  # noqa: E402
import fragments as FR  # noqa: E402

T = Tokenizer.from_file(os.path.expanduser("~/Models/x210/Qwen3.5-4B/tokenizer.json"))
HOST = os.path.join(X210, "host", "out", "dev2")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="d", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = {"rows": [], "n": 0}
    tot = dict(correct=0, scored=0, answered=0, cap=0, budget=0, calls=0, same_as_host_line=0, lines=0, tokens_real=0, arg_lines=0, identical_to_host=0, lock_errors=0, head_mismatch=0, chip=0, qwen=0, echo=0, seconds=0.0, first_call_same=0, own_im_end=0)
    for p in sorted(glob.glob(os.path.join(a.d, "*.jsonl"))):
        name = os.path.basename(p)[:-6]
        host = {}
        hp = os.path.join(HOST, name, "sdpa.jsonl")
        for ln in open(hp):
            r = json.loads(ln)
            host[r["id"]] = r
        for ln in open(p):
            r = json.loads(ln)
            h = host[r["id"]]
            tot["n"] = tot.get("n", 0) + 1
            tot["scored"] += r["correct"] is not None
            tot["correct"] += r["correct"] is True
            tot[r["status"] if r["status"] in ("answered", "cap", "budget") else "budget"] += r["status"] in ("answered", "cap", "budget")
            tot["calls"] += r["n_calls"]
            tot["lock_errors"] += r["lock_error"] is not None
            tot["head_mismatch"] += r["head_mismatch"]
            tot["chip"] += r["chip_tokens"]
            tot["qwen"] += r["qwen_tokens"]
            tot["echo"] += r["echo_tokens"]
            tot["seconds"] += r["seconds"]
            bad = 0
            for c in r["calls"]:
                tot["lines"] += 1
                tot["same_as_host_line"] += c["same_as_host"]
                want = T.encode(FR.HEAD + c["result"] + FR.TAIL, add_special_tokens=False).ids
                arg = c["result"].startswith(FR.ARG_PREFIX)
                tot["arg_lines"] += arg
                ok = c["response_ids"] == want
                tot["tokens_real"] += ok
                bad += not ok and not arg
            mine = [s["ids"] for s in r["segments"]]
            theirs = [s["ids"] for s in h["segments"] if s["by"] != "prompt"]
            same = mine == theirs
            # the host's stream starts a tool segment after its own </tool_call>, as this one does
            tot["identical_to_host"] += same
            first_same = bool(r["calls"]) and bool(h["calls"]) and r["calls"][0]["ids"] == h["calls"][0]["ids"]
            tot["first_call_same"] += first_same
            ended = r["status"] == "answered" and r["segments"][-1]["ids"][-1:] == [248046]
            tot["own_im_end"] += ended
            res["rows"].append({"graph": name, "id": r["id"], "status": r["status"], "correct": r["correct"], "host_correct": h["correct"], "calls": r["n_calls"], "host_calls": h["n_calls"], "identical": same, "first_call_same": first_same,
                                "bad_response_tokens": bad, "final": r["final"], "host_final": h["final"], "gold": r.get("gold_text"), "seconds": r["seconds"], "chip": r["chip_tokens"], "qwen": r["qwen_tokens"], "echo": r["echo_tokens"], "ran_on": r["ran_on"]})
    res["totals"] = tot
    json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(tot)
    for x in res["rows"][:60]:
        print(x["graph"], x["id"], x["status"], x["correct"], x["host_correct"], x["calls"], x["host_calls"], "same" if x["identical"] else "", repr(x["final"])[:70])


if __name__ == "__main__":
    main()
