#!/bin/zsh
# Step V, then step X: the redraft's panels, then the stock window. One GPU process at a time (t8/REGISTRATION.md).
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
R=t8/fw/results; V=$R/wvar; mkdir -p $V
G="python3 tools/memguard.py --limit-gib 32 --log t8/fw/mem.log --"
v() { arm=$1; panel=$2; mode=$3; n=${arm}_${panel}_$mode; timeout 1300 ${=G} $PY -B t8/fw/wvar.py --arm $arm --panel $panel --mode $mode --out $V/$n --deadline-s 1200 > $V/$n.log 2>&1; echo "$(date +%T) $n code $?"; }
v base edits print
v r edits print
v r hard1 print
v r hard2 print
v r easy1 print
v r easy2 print
v r easy2 read
v r hard2 read
echo v finished
W=$R/window
T8_WRITES=1 timeout 14000 ${=G} env T8_WRITES=1 T8_NOUN=on $PY -B t8/fw/tokrun.py stock_trace.py --plan t8/fw/plan_window.json --outdir $W --hours 3.81 > $R/window_trace.log 2>&1; echo "$(date +%T) window code $?"
T8_WRITES=1 timeout 900 python3 tools/memguard.py --limit-gib 12 --log t8/fw/mem.log -- env T8_WRITES=1 T8_NOUN=on $PY -B t8/fw/tokrun.py check_trace.py --trace $W --plan t8/fw/plan_window.json --out $R/window_check.json > $R/window_check.log 2>&1; echo "$(date +%T) check code $?"
T8_WRITES=1 timeout 900 python3 tools/memguard.py --limit-gib 12 --log t8/fw/mem.log -- env T8_WRITES=1 T8_NOUN=on $PY -B t8/fw/tokrun.py check_trace.py --trace $W --plan t8/fw/plan_window.json --flip-trace seed:0:8 --out $R/window_flip.json > $R/window_flip.log 2>&1; echo "$(date +%T) flip code $?"
echo x finished
