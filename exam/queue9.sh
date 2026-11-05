#!/bin/zsh
# exam/AFTER.md V: after queue8's stock parts. One GPU process at a time.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_WRITES=1
R=exam/results; A=$R/after; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
until ! pgrep -f "exam/queue8.sh" >/dev/null; do /bin/sleep 20; done
until ! pgrep -f "d1m_stock.py" >/dev/null; do /bin/sleep 20; done
step() { n=$1; lim=$2; shift 2; timeout $lim ${=G} "$@" > $A/$n.log 2>&1; echo "$(date +%T) $n code $?" }
step lines3 8100 $PY -B t8/fw/tokrun.py ../exam/lines_run.py --out $PWD/$A/lines3 --draw $PWD/$A/lines3_draw.json --set conversations --verify-first 2 --question-limit-s 2400 --deadline-s 7800
echo lines3 finished
step recommend 2600 $PY -B t8/fw/tokrun.py ../exam/journeys_run.py --out $PWD/$A/recommend --draw $PWD/$A/recommend_draw.json --set conversations --verify-first 2 --question-limit-s 800 --deadline-s 2320
echo v finished
