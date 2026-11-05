#!/bin/zsh
# exam/AFTER.md S1 on the Mac, one map after the other, 12 workers at low priority beside the GPU job. No sealed data on the mini.
cd "<repo>"
X=$PWD
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1
export TOK_CKPT="<scratchpad>"
mkdir -p exam/results/o7
M=(python3 "$X/tools/memguard.py" --limit-gib 3 --log "$X/exam/mem7.log" --)
for m in nyc-cf nyc-relabelled; do
  B=$X/exam/items/sealed/${m}_b.graph.json
  "${M[@]}" $PY -B t8/fw/tokrun.py ../exam/sealed_items.py --name $m --out $X/exam/items/sealed/$m.json > exam/results/o7/items_$m.log 2>&1 || { echo "$(date +%T) STOP $m items"; exit 1; }
  ITEMS_GRAPH=$B ITEMS_BASE=$X/exam/items/sealed/$m.json "${M[@]}" $PY -B t8/fw/tokrun.py ../exam/items_all.py --out $X/exam/items/sealed/${m}_all.json > exam/results/o7/all_$m.log 2>&1 || { echo "$(date +%T) STOP $m all"; exit 1; }
  echo "$(date +%T) $m items done"
  for w in 1 2 3 4 5 6 7 8 9 10 11 12; do RUN_ALL_GRAPH=$B nice -n 5 "${M[@]}" $PY -B t8/fw/tokrun.py ../exam/run_all.py --items $X/exam/items/sealed/${m}_all.json --out $X/exam/results/s1_$m --limit-s 14400 > exam/results/o7/run_${m}_$w.log 2>&1 & done
  wait
  echo "$(date +%T) $m exam done"
done
echo s1 finished
