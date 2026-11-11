#!/bin/zsh
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
R=t8/fw/results
timeout 3700 python3 tools/memguard.py --limit-gib 32 --log t8/fw/mem.log -- $PY -B t8/fw/tokrun.py stock_trace.py --plan t8/fw/plan_clean.json --outdir $R/trace --hours 0.95 > $R/stock_trace.log 2>&1; echo stock code $?
timeout 400 python3 tools/memguard.py --limit-gib 12 --log t8/fw/mem.log -- $PY -B t8/fw/tokrun.py check_trace.py --trace $R/trace --plan t8/fw/plan_clean.json --out $R/check_trace.json > $R/check_trace.log 2>&1; echo check code $?
timeout 400 python3 tools/memguard.py --limit-gib 12 --log t8/fw/mem.log -- $PY -B t8/fw/tokrun.py check_trace.py --trace $R/trace --plan t8/fw/plan_clean.json --flip-trace seed:0:8 --out $R/check_flip.json > $R/check_flip.log 2>&1; echo flip code $?
echo f2 finished
