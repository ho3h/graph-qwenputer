#!/bin/zsh
# The stock window on New York's own calls, on the frozen writes.elf (exam/REGISTRATION.md, Coverage and stock). T8_R1 stays off.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
unset T8_R1
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_WRITES=1 T8_NOUN=on
R=exam/results; W=$R/nyc_window; P=$R/plan_nyc.json
until grep -q "pick finished" $R/pick.log; do /bin/sleep 20; done
cut -c1-1500 $R/pick.log
timeout 13200 python3 tools/memguard.py --limit-gib 32 --log exam/mem.log -- $PY -B t8/fw/tokrun.py stock_trace.py --plan $PWD/$P --outdir $PWD/$W --hours 3.5 > $R/nyc_window_trace.log 2>&1; echo "$(date +%T) window code $?"
timeout 900 python3 tools/memguard.py --limit-gib 12 --log exam/mem.log -- $PY -B t8/fw/tokrun.py check_trace.py --trace $PWD/$W --plan $PWD/$P --out $PWD/$R/nyc_window_check.json > $R/nyc_window_check.log 2>&1; echo "$(date +%T) check code $?"
timeout 900 python3 tools/memguard.py --limit-gib 12 --log exam/mem.log -- $PY -B t8/fw/tokrun.py check_trace.py --trace $PWD/$W --plan $PWD/$P --flip-trace seed:0:8 --out $PWD/$R/nyc_window_flip.json > $R/nyc_window_flip.log 2>&1; echo "$(date +%T) flip code $?"
timeout 300 $PY -B t8/fw/tokrun.py ../t8/fw/cov.py trace --firmware writes --trace $W --plan $P --out t8/fw/results/cov/nyc_window > $R/nyc_window_cov.log 2>&1; echo "$(date +%T) cov code $?"
echo x_nyc finished
