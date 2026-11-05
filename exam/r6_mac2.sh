#!/bin/zsh
# exam/AFTER.md r6a's split: more Mac workers, one thread each, normal-ish priority, same claims, same hard stop.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1
export RUN_ALL_GRAPH=$PWD/exam/items/nyc_b.graph.json
LIM=$(( $(date -j -f "%Y-%m-%d %H:%M:%S" "2026-11-04 16:10:00" +%s) - $(date +%s) ))
for w in 1 2 3 4 5; do nice -n 5 python3 tools/memguard.py --limit-gib 3 --log exam/mem6.log -- $PY -B t8/fw/tokrun.py ../exam/run_all.py --items exam/items/nyc_b_all.json --out $PWD/exam/results/r6_all_mac --only all3,all4 --limit-s $LIM > exam/results/o6/b$w.log 2>&1 & done
wait
echo "$(date +%T) extra Mac workers done"
