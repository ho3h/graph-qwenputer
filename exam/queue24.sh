#!/bin/zsh
# exam/AFTER.md E6w and S5, whole on the real weights, after the sealed exams leave the CPU free. One GPU process at a time.
cd "<repo>"
until grep -q "s1 finished" exam/results/queue22.log 2>/dev/null && grep -q "s4 finished" exam/results/queue23.log 2>/dev/null; do /bin/sleep 60; done
X=$PWD
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1
G=(python3 "$X/tools/memguard.py" --limit-gib 32 --log "$X/exam/mem.log" --)
A=exam/results/after
echo "$(date +%T) overnight starts"
timeout 14400 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/edit_run_b.py --out $X/$A/e6w_conv --draw $X/$A/e6_draw.json --set conversations --verify-first 40 --deadline-s 14300 --question-limit-s 3000 > $A/e6w_conv.log 2>&1
echo "$(date +%T) e6w conversations code $?"
timeout 5100 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/edit_run_b.py --out $X/$A/e6w_plain --draw $X/$A/e6_draw.json --set plain --verify-first 30 --deadline-s 5050 --question-limit-s 3000 > $A/e6w_plain.log 2>&1
echo "$(date +%T) e6w plain code $?"
J_REOPEN=1 timeout 4800 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/journeys_run.py --out $X/$A/s5 --draw $X/$A/s5_draw.json --set conversations --verify-first 1 --question-limit-s 4700 --deadline-s 4700 > $A/s5.log 2>&1
echo "$(date +%T) s5 code $?"
echo overnight finished
