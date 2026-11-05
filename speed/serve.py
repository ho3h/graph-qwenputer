"""One process that holds the merged model, and runs each stage as a script dropped in cmd/, so a load is paid once. Development tool; each stage saves its own results.

    ./run.sh 14400 32 serve.py --cmd cmd                         # holds the model
    python3 -c "..."                                             # write cmd/NAME.py, wait for cmd/NAME.out and cmd/NAME.done

A stage runs with the namespace below (ec, chat, cx, np, torch, helpers from textlib). Stops on cmd/STOP.
"""
import argparse
import contextlib
import io
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
t00 = time.time()
import textlib as TL  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cmd", default="cmd")
    ap.add_argument("--no-load", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.cmd, exist_ok=True)
    ns = {"TL": TL, "t_import": time.time() - t00}
    if not a.no_load:
        ns["ctx"] = TL.load()
    print("ready", flush=True)
    while True:
        if os.path.exists(os.path.join(a.cmd, "STOP")):
            os.remove(os.path.join(a.cmd, "STOP"))
            return
        names = sorted(f[:-3] for f in os.listdir(a.cmd) if f.endswith(".py") and not os.path.exists(os.path.join(a.cmd, f[:-3] + ".done")))
        if not names:
            time.sleep(0.5)
            continue
        name = names[0]
        code = open(os.path.join(a.cmd, name + ".py")).read()
        t0 = time.time()
        with open(os.path.join(a.cmd, name + ".out"), "w", buffering=1) as f, contextlib.redirect_stdout(f):
            try:
                exec(compile(code, name, "exec"), ns)
            except BaseException:
                traceback.print_exc(file=f)
            print(f"[stage seconds {time.time() - t0:.1f}]", file=f, flush=True)
        open(os.path.join(a.cmd, name + ".done"), "w").write(str(time.time() - t0))


if __name__ == "__main__":
    main()
