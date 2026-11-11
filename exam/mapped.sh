#!/bin/zsh
# exam/AFTER.md E. One GPU process at a time, fresh process every 25 questions.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
A=exam/results/after/mapped; mkdir -p $A
for arm in M1:3700 M2:1480 M3:1110; do
  n=${arm%%:*}; b=${arm##*:}; t0=$SECONDS
  while (( SECONDS - t0 < b )); do
    python3 tools/memguard.py --limit-gib 16 --log exam/mem.log -- $PY -B exam/mapped.py --arm $n --out $A/$n.jsonl --limit 25 --deadline-s $(( b - (SECONDS - t0) )) >> $A/$n.log 2>&1
    c=$?
    tail -3 $A/$n.log | grep -q "arm finished" && break
    (( c == 0 )) || { echo "$(date +%T) $n code $c"; break }
  done
  echo "$(date +%T) $n done $(wc -l < $A/$n.jsonl) rows"
done
python3 exam/score_mapped.py $A | cut -c1-900
echo mapped finished
