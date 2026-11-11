#!/bin/zsh
# exam/AFTER.md r6e's one revision, with the registered limit. One GPU process at a time.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1 J_REOPEN=1
A=exam/results/after; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
timeout 9000 ${=G} $PY -B t8/fw/tokrun.py ../exam/journeys_run.py --out $PWD/$A/r6_walk --draw $PWD/$A/r6_walk_draw.json --set conversations --verify-first 1 --question-limit-s 8800 --deadline-s 8800 > $A/r6_walk.log 2>&1
echo "$(date +%T) r6_walk code $?"
echo r6 walk finished
