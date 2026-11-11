#!/bin/zsh
# exam/AFTER.md Z2 on r5. One GPU process at a time.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_WRITES=1 R3_PATH=1
A=exam/results/after; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
timeout 8100 ${=G} $PY -B t8/fw/tokrun.py ../exam/lines_run.py --out $PWD/$A/r5long --draw $PWD/$A/r4long_draw.json --set conversations --verify-first 2 --question-limit-s 2400 --deadline-s 7800 > $A/r5long.log 2>&1
echo "$(date +%T) r5long code $?"
echo z2 finished
