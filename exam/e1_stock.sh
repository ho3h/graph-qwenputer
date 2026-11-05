#!/bin/zsh
# exam/AFTER.md F. Waits for E; one GPU process at a time; a difference stops the next run.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_WRITES=1
R=exam/results; O=$R/nyc_r1_edit_stock; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
until grep -q "mapped finished" $R/after_mapped.log; do /bin/sleep 20; done
[[ "$(shasum -a 256 t8/fw/build_r1/writes.elf | cut -d' ' -f1)" == ad1abcc6cec073b52e088c4d0d1752dd9908f6f77d39d950ff0d5a5e70c41fe0 ]] || { echo STOP elf; exit 1 }
for run in 20:7770 40:7770 70:5850; do
  n=${run%%:*}; b=${run##*:}
  timeout $(( b + 300 )) ${=G} $PY -B t8/fw/tokrun.py ../exam/edit_run.py --out $O --draw $R/nyc_r1_edit_draw.json --verify-first 999 --limit $n --deadline-s $b >> $R/nyc_r1_edit_stock.log 2>&1
  c=$?; echo "$(date +%T) through $n code $c $(wc -l < $O/all.jsonl) rows"
  (( c == 0 )) || { echo STOP run $n code $c; exit 1 }
done
python3 exam/edit_score.py $O | cut -c1-600
echo e1_stock finished
