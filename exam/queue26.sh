#!/bin/zsh
# Theo, 5 Nov: about 45 minutes on the Mac. S2 on nyc-cf is running; then S4 on both maps; nothing after. Everything stops by 10:44 ET.
cd "<repo>"
X=$PWD
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1
G=(python3 "$X/tools/memguard.py" --limit-gib 32 --log "$X/exam/mem.log" --)
A=exam/results/after
while pgrep -f "edit_run_b.py --out .*s2_nyc-cf" >/dev/null; do /bin/sleep 5; done
echo "$(date +%T) s2 nyc-cf ended"
for m in nyc-relabelled nyc-cf; do
  [ $(date +%H%M) -lt 1036 ] || { echo "$(date +%T) s4 $m not started, out of time"; continue; }
  ALONE_MAP=$m timeout 420 "${G[@]}" $PY -B exam/alone.py --out $X/$A/s4_$m.jsonl --deadline-s 400 > $A/s4_$m.log 2>&1
  echo "$(date +%T) s4 $m code $?"
done
echo queue26 finished
