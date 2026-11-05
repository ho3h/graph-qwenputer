#!/bin/zsh
# Step X alone: the stock window, then its checks. Split from v.sh once step V closed on its fifth rule.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_WRITES=1 T8_NOUN=on
R=t8/fw/results; W=$R/window
G="python3 tools/memguard.py --limit-gib 32 --log t8/fw/mem.log --"
timeout 14000 ${=G} $PY -B t8/fw/tokrun.py stock_trace.py --plan t8/fw/plan_window.json --outdir $W --hours 3.81 > $R/window_trace.log 2>&1; echo "$(date +%T) window code $?"
timeout 900 python3 tools/memguard.py --limit-gib 12 --log t8/fw/mem.log -- $PY -B t8/fw/tokrun.py check_trace.py --trace $W --plan t8/fw/plan_window.json --out $R/window_check.json > $R/window_check.log 2>&1; echo "$(date +%T) check code $?"
timeout 900 python3 tools/memguard.py --limit-gib 12 --log t8/fw/mem.log -- $PY -B t8/fw/tokrun.py check_trace.py --trace $W --plan t8/fw/plan_window.json --flip-trace seed:0:8 --out $R/window_flip.json > $R/window_flip.log 2>&1; echo "$(date +%T) flip code $?"
echo x finished
