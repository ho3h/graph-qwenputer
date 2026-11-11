#!/bin/zsh
# exam/AFTER.md N2, after W. One GPU process at a time.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_WRITES=1
A=exam/results/after; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
until ! pgrep -f "exam/queue10.sh" >/dev/null; do /bin/sleep 15; done
timeout 7300 ${=G} $PY -B t8/fw/tokrun.py ../exam/edit_run.py --out $PWD/$A/gaslight2 --draw $PWD/$A/gaslight2_draw.json --set conversations --verify-first 2 --deadline-s 7000 > $A/gaslight2.log 2>&1
echo "$(date +%T) n2 code $?"
echo n2 finished
