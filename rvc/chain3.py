"""The told-only chain on about 100 dev chase questions: chain2.run_question with told on and no rule, fw/'s firmware, exec/'s engine.

    python chain3.py --out results/chain3      # from the vendored folder, under tools/memguard.py and timeout

Questions run in the draw's order (results/chain3_draw.json); one JSON line each; a restart skips finished ones. Stock-and-executor lockstep on the draw's stock_sample.
"""
import argparse, json, os, re, sys, time
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import box as X
FW = os.path.join(X.X210, "fw", "build", "fw.elf")
X.ELF = FW
X.build_elf = lambda: FW
import chain2 as C2
import decode as D
import reflib
import score as SC
import torch

CASE = lambda g, q: q.get("case") or f"city kind {q['id'] // 100}"


def classify(g, q, r):
    """Outcome of one record, against the scorer and the canonical line."""
    gold, final = q["answer_text"], r["final"]
    labels = [n["label"] for n in g["nodes"]]
    calls = [c for c in r["calls"] if "result" in c]
    first = calls[0]["result"] if calls else None
    err = lambda s: bool(s is not None and C2.ERROR.match(s))
    o = {"case": CASE(g, q), "first_correct": SC.score(first, q, labels) if first is not None else False, "first_error": err(first), "final_error": err(final),
         "exact": final == gold, "gold_is_limit_line": err(gold), "retries": max(0, len(r["calls"]) - 1), "no_call": r["status"] == "no_call", "status": r["status"]}
    if r["correct"]:
        o["outcome"] = "correct"
    elif final is None or err(final):
        o["outcome"] = "loud"
    else:
        o["outcome"] = "silent"
    o["kind"] = None
    if o["outcome"] != "correct":
        G = reflib.Graph(g)
        for s in q.get("setup") or []:
            G.call(s["fn"], s["args"])
        cr = q["call"]["args"]
        if o["outcome"] == "silent":
            a = calls[-1]["args"]
            sa, _ = G.node(str(a.get("start", "")))
            sb, _ = G.node(cr["start"])
            la = re.sub(r"\s+", " ", str(a.get("legs", ""))).strip()
            lb = re.sub(r"\s+", " ", cr["legs"]).strip()
            o["kind"] = "right call, other answer" if sa == sb and la == lb else ("wrong start" if sa != sb and la == lb else ("wrong legs" if sa == sb else "wrong start and legs"))
        else:
            word = "no call at all" if final is None else re.sub(r"^leg \d+: ", "", final).split()[0]
            o["kind"] = word + (" then prose" if r["status"] == "no_call" else " after retries" if len(r["calls"]) > 1 else "")
    return o


def tally(out, draw):
    rows, per = [], Counter()
    rs = [json.loads(l) for l in open(os.path.join(out, "all.jsonl"))] if os.path.exists(os.path.join(out, "all.jsonl")) else []
    for r in rs:
        rows.append(r["outcome"])
    n = len(rows)
    c = lambda f: sum(1 for x in rows if f(x))
    t = {"questions": n, "correct": c(lambda x: x["outcome"] == "correct"), "first_correct": c(lambda x: x["first_correct"]), "loud": c(lambda x: x["outcome"] == "loud"), "silent": c(lambda x: x["outcome"] == "silent"),
         "first_line_errors": c(lambda x: x["first_error"]), "first_error_not_correct": c(lambda x: x["first_error"] and not x["first_correct"]),
         "rescued": c(lambda x: not x["first_correct"] and x["first_error"] and x["outcome"] == "correct"), "lost_by_retry": c(lambda x: x["first_correct"] and x["outcome"] != "correct"),
         "correct_but_not_canonical_line": c(lambda x: x["outcome"] == "correct" and not x["exact"]), "correct_on_a_limit_line": c(lambda x: x["outcome"] == "correct" and x["final_error"]),
         "no_call": c(lambda x: x["no_call"]), "status": dict(Counter(x["status"] for x in rows)), "failure_kinds": dict(Counter(x["kind"] for x in rows if x["kind"])),
         "calls": sum(r["n_calls"] for r in rs), "machine_lines_equal_host_tool": sum(bool(k.get("same_as_host")) for r in rs for k in r["calls"]),
         "machine_lines": sum("result" in k for r in rs for k in r["calls"]), "lock_errors": sum(r["lock_error"] is not None for r in rs), "head_mismatch": sum(r["head_mismatch"] for r in rs),
         "own_ok": sum(r["own_ok"] for r in rs), "chip_tokens": sum(r["chip_tokens"] for r in rs), "qwen_tokens": sum(r["qwen_tokens"] for r in rs), "echo_tokens": sum(r["echo_tokens"] for r in rs),
         "seconds_over_questions": round(sum(r["seconds"] for r in rs), 1), "text_seconds": round(sum(r["text_seconds"] for r in rs), 1), "chip_seconds": round(sum(r["chip_seconds"] for r in rs), 1),
         "verified_positions": sum(r["verified_positions"] for r in rs), "max_cap": max((k["cap"] for r in rs for k in r["calls"]), default=0),
         "by_case": {}, "by_set": {}}
    for r in rs:
        for key, name in (("by_case", r["outcome"]["case"]), ("by_set", r["graph"].split("/")[0])):
            b = t[key].setdefault(name, {"n": 0, "correct": 0, "first_correct": 0, "loud": 0, "silent": 0})
            b["n"] += 1
            b[r["outcome"]["outcome"]] = b.get(r["outcome"]["outcome"], 0) + 1
            b["first_correct"] += r["outcome"]["first_correct"]
    json.dump(t, open(os.path.join(out, "tally.json"), "w"), indent=1, ensure_ascii=False)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--question-limit-s", type=float, default=1800)
    a = ap.parse_args()
    d = json.load(open(os.path.join(HERE, "results", "chain3_draw.json")))
    assert __import__("hashlib").sha256(open(FW, "rb").read()).hexdigest() == d["firmware_sha256"]
    assert C2.TOLD in open(os.path.join(X.X210, "rb", "delivery.py")).read()
    sys.path.append(os.path.join(X.X210, "exec"))
    from chat import ExecChat
    from transformers import AutoTokenizer
    nq = len(AutoTokenizer.from_pretrained(X.MODEL))
    t0 = time.time()
    ec = ExecChat(D.CKPT)
    load_s = round(time.time() - t0, 1)
    tool = C2.chase_tool("")
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "all.jsonl")
    done = {(json.loads(l)["graph"], json.loads(l)["id"]) for l in open(path)} if os.path.exists(path) else set()
    json.dump({"ckpt": D.CKPT, "firmware": FW, "firmware_sha256": d["firmware_sha256"], "engine": ec.cx.lib_hash, "told": C2.TOLD, "extra": C2.EXTRA, "rule": False, "tool": tool, "retries": C2.RETRIES, "turn": C2.TURN,
               "stock_sample": d["stock_sample"], "load_seconds": load_s, "question_limit_s": a.question_limit_s, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "attn": ec.chat.model.config._attn_implementation},
              open(os.path.join(a.out, "meta.json"), "w"), indent=1, ensure_ascii=False)
    print(f"loaded {load_s}s {D.mem()} engine {ec.cx.lib_hash}", flush=True)
    stock = {tuple(k) for k in d["stock_sample"]}
    with open(path, "a", encoding="utf-8") as f:
        for gname, i in map(tuple, d["draw"]):
            if (gname, i) in done:
                continue
            gp, qp = D.graph_path(gname)
            g = json.load(open(gp))
            q = {x["id"]: x for x in json.load(open(qp))["questions"]}[i]
            r = C2.run_question(ec, g, q, nq, a.question_limit_s, tool, verify=(gname, i) in stock, question_handles=False, told=True, rule=False)
            r["graph"] = gname
            r["outcome"] = classify(g, q, r)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{gname} q{i}: {r['outcome']['outcome']} {r['outcome']['kind']} on {r['ran_on']} status={r['status']} calls={r['n_calls']} {r['seconds']}s chip={r['chip_tokens']} qwen={r['qwen_tokens']} echo={r['echo_tokens']} "
                  f"lock={r['lock_error']} head_bad={r['head_mismatch']} verified={r['verified_positions']} mismatch={r['verify_mismatch']} | {(r['final'] or '')[:50]!r}", flush=True)
            torch.mps.empty_cache()
            tally(a.out, d)
            if r["status"] in ("verify_mismatch", "engine_flag"):
                print("STOP: the executor disagreed; this run's results do not count until explained", flush=True)
                sys.exit(3)
    print(json.dumps({k: v for k, v in tally(a.out, d).items()}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
