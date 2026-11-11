#!/bin/zsh
# exam/AFTER.md Z3b. One GPU process at a time.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_WRITES=1 R3_PATH=1
A=exam/results/after; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
timeout 5700 ${=G} $PY -B t8/fw/tokrun.py ../exam/lines_run.py --out $PWD/$A/z3c --draw $PWD/$A/z3c_draw.json --set conversations --verify-first 999 --question-limit-s 5400 --deadline-s 5400 > $A/z3c.log 2>&1
echo "$(date +%T) z3c code $?"
echo z3c finished
