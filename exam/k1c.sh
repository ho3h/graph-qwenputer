#!/bin/zsh
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_WRITES=1
R=exam/results
for m in plainc plaind; do
  timeout 3900 python3 tools/memguard.py --limit-gib 32 --log exam/mem.log -- $PY -B exam/controls.py $m --out $R/after/control_$m.jsonl --deadline-s 3600 > $R/after/control_$m.log 2>&1 &
done
wait
echo k1c finished
