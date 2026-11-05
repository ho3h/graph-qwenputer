"""Run the host-tool baseline on a question file, under one or more attention implementations.

    python run.py --graph G.graph.json --questions Q.questions.json --out DIR [--attn eager sdpa] [--limit N]
    python run.py --serve JOBDIR      # load the model once, then run each JOBDIR/*.json job (same keys as the flags)

Each attention implementation writes DIR/<attn>.jsonl (one record per question, appended as it finishes) and the run
writes DIR/meta.json. The loop modules (harness, tools, score) are reloaded for every served job; the weights stay.
Never reads anything under a data/heldout/ directory.
"""

import argparse
import hashlib
import importlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def guard(p) -> Path:
    p = Path(p).resolve()
    if "heldout" in p.parts:
        raise SystemExit(f"refused: {p} is held-out data")
    return p


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_job(qwen, job: dict) -> dict:
    import harness
    import reflib
    import score
    import tools
    for m in (reflib, tools, score, harness):
        importlib.reload(m)
    gpath, qpath = guard(job["graph"]), guard(job["questions"])
    out = Path(job["out"])
    out.mkdir(parents=True, exist_ok=True)
    gjson, qfile = json.loads(gpath.read_text()), json.loads(qpath.read_text())
    assert qfile["graph"] == gjson["name"], (qfile["graph"], gjson["name"])
    if qfile.get("graph_sha256"):
        assert qfile["graph_sha256"] == sha(gpath), "graph_sha256 mismatch"
    qs = qfile["questions"]
    if job.get("ids") is not None:
        qs = [q for q in qs if q["id"] in set(job["ids"])]
    qs = qs[: job.get("limit") or len(qs)]
    attns, think, arm = job.get("attn") or ["sdpa"], bool(job.get("think")), job.get("arm") or "base"
    meta = {"graph": str(gpath), "graph_sha256": sha(gpath), "questions": str(qpath),
            "questions_sha256": sha(qpath), "n": len(qs), "attn": attns, "think": think, "arm": arm,
            "reflib_sha256": sha(Path(reflib.__file__)),
            "model": qwen.path, "tools_sha256": tools.tools_sha256(arm), "system_prompt": tools.system_prompt(gjson),
            "max_calls": harness.MAX_CALLS, "load_seconds": qwen.load_seconds, "env": qwen.env,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (out / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    files = {a: open(out / f"{a}.jsonl", "a", encoding="utf-8") for a in attns}
    summary = {a: {"n": 0, "correct": 0, "seconds": 0.0} for a in attns}
    for q in qs:
        for a in attns:
            qwen.set_attn(a)
            r = harness.run_question(qwen, gjson, q, think=think, arm=arm)
            files[a].write(json.dumps(r, ensure_ascii=False) + "\n")
            files[a].flush()
            s = summary[a]
            s["n"] += 1
            s["correct"] += bool(r["correct"])
            s["seconds"] += r["seconds"]
            print(f"q{q['id']} {a}: {r['status']} calls={r['n_calls']} correct={r['correct']} "
                  f"{r['seconds']}s peak={r['peak_driver_bytes'] / 2**30:.2f}GiB | {(r['final'] or '')[:100]!r}",
                  flush=True)
    for f in files.values():
        f.close()
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    meta["summary"] = summary
    (out / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    return summary


def serve(qwen, jobdir: Path):
    jobdir.mkdir(parents=True, exist_ok=True)
    print(f"serving {jobdir} (model loaded in {qwen.load_seconds}s)", flush=True)
    while True:
        if (jobdir / "stop").exists():
            (jobdir / "stop").unlink()
            print("stopped", flush=True)
            return
        jobs = sorted(jobdir.glob("*.json"))
        if not jobs:
            time.sleep(2)
            continue
        j = jobs[0]
        job = json.loads(j.read_text())
        j.rename(j.with_suffix(".running"))
        try:
            res = {"ok": True, "summary": run_job(qwen, job)}
        except Exception as e:  # keep serving; the job records its error
            import traceback
            res = {"ok": False, "error": traceback.format_exc()}
            print(res["error"], flush=True)
        j.with_suffix(".running").rename(j.with_suffix(".done"))
        j.with_suffix(".result").write_text(json.dumps(res, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph")
    ap.add_argument("--questions")
    ap.add_argument("--out")
    ap.add_argument("--attn", nargs="+", default=["eager", "sdpa"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--arm", default="base", choices=["base", "clear"])
    ap.add_argument("--serve")
    ap.add_argument("--device", default="mps")
    a = ap.parse_args()
    from model import Qwen
    qwen = Qwen(device=a.device, attn=a.attn[0])
    if a.serve:
        serve(qwen, Path(a.serve))
    else:
        run_job(qwen, {"graph": a.graph, "questions": a.questions, "out": a.out, "attn": a.attn,
                       "limit": a.limit, "think": a.think, "arm": a.arm})


if __name__ == "__main__":
    main()
