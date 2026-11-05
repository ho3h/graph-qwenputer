#!/bin/zsh
# exam/AFTER.md r6d, r6e, r6f. One GPU process at a time.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1 J_REOPEN=1
A=exam/results/after; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
step() { n=$1; lim=$2; shift 2; timeout $lim ${=G} "$@" > $A/$n.log 2>&1; echo "$(date +%T) $n code $?" }
step r6_alone 300 $PY -B exam/alone_walk.py --out $A/r6_alone.json
step r6_journeys 3000 $PY -B t8/fw/tokrun.py ../exam/journeys_run.py --out $PWD/$A/r6_journeys --draw $PWD/$A/r6_journeys_draw.json --set conversations --verify-first 0 --question-limit-s 600 --deadline-s 2800
echo journeys finished
step r6_walk 9300 $PY -B t8/fw/tokrun.py ../exam/journeys_run.py --out $PWD/$A/r6_walk --draw $PWD/$A/r6_walk_draw.json --set conversations --verify-first 1 --question-limit-s 3600 --deadline-s 9000
echo r6 gpu finished
