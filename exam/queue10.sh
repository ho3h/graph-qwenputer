#!/bin/zsh
# exam/AFTER.md W. One GPU process at a time.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_WRITES=1
A=exam/results/after; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
timeout 12400 ${=G} $PY -B t8/fw/tokrun.py ../exam/lines_run.py --out $PWD/$A/lines2_stock --draw $PWD/$A/lines2_draw.json --set conversations --verify-first 999 --limit 12 --question-limit-s 2400 --deadline-s 11800 > $A/lines2_stock.log 2>&1
echo "$(date +%T) w code $?"
echo w finished
