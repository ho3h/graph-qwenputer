#!/bin/bash
cd <mini> || exit 1
[ "$(diskutil info /Volumes/attic | awk '/Volume UUID/{print $3}')" = "7F9CEBB9-5477-4998-B519-D725B3A871CD" ] || { echo wrong drive; exit 1; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$HOME/x210-d/pylib:$PWD/vendor/qwenputer-riscv EDITS_META=<mini> EDITS_CC=/usr/bin/clang TOK_CKPT=<mini> T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
M="/usr/bin/python3 tools/memguard.py --limit-gib 3 --log results/mem.log --"
P="$HOME/computing-field-venv/bin/python -B t8/fw/tokrun.py"
echo "$(date) relabelled items"
ITEMS_GRAPH=$PWD/exam/items/sealed/nyc-relabelled_b.graph.json ITEMS_BASE=$PWD/exam/items/sealed/nyc-relabelled.json $M $P ../exam/items_all_mini.py --out $PWD/exam/items/sealed/nyc-relabelled_all.json > results/o/items_rl.log 2>&1 || { echo "STOP items $(date)"; tail -3 results/o/items_rl.log; exit 1; }
echo "$(date) relabelled items done"
until grep -q "s1 nyc-cf tail finished" results_go18.log; do sleep 20; done
LEFT=$(cat exam/results/s1_cf_left.txt)
echo "$(date) s1 nyc-cf, the Mac's unfinished units"
for w in 1 2 3 4 5 6 7 8 9; do RUN_ALL_GRAPH=$PWD/exam/items/sealed/nyc-cf_b.graph.json $M $P ../exam/run_all.py --items exam/items/sealed/nyc-cf_all.json --out results/s1_nyc-cf --only "$LEFT" --limit-s 14400 > results/o/s1cf2_$w.log 2>&1 & done
wait
echo "$(date) s1 nyc-cf finished on the mini"
touch exam/items/sealed/RELABELLED_READY
echo "go19 finished $(date)"
