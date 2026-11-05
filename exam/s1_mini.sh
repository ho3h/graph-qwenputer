#!/bin/bash
cd <mini> || exit 1
[ "$(diskutil info /Volumes/attic | awk '/Volume UUID/{print $3}')" = "7F9CEBB9-5477-4998-B519-D725B3A871CD" ] || { echo wrong drive; exit 1; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$HOME/x210-d/pylib:$PWD/vendor/qwenputer-riscv EDITS_META=<mini> EDITS_CC=/usr/bin/clang TOK_CKPT=<mini> T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
M="/usr/bin/python3 tools/memguard.py --limit-gib 3 --log results/mem.log --"
P="$HOME/computing-field-venv/bin/python -B t8/fw/tokrun.py"
mkdir -p results/o
echo "$(date) s1 nyc-cf tail"
for w in 1 2 3 4 5 6 7 8 9; do RUN_ALL_GRAPH=$PWD/exam/items/sealed/nyc-cf_b.graph.json $M $P ../exam/run_all.py --items exam/items/sealed/nyc-cf_all.json --out results/s1_nyc-cf --only all415,all416,all417,all418,all419,all42,all43,all44,all45,all46,all47,all48,all49 --limit-s 14400 > results/o/s1cf_$w.log 2>&1 & done
wait
echo "$(date) s1 nyc-cf tail finished"
until [ -s exam/items/sealed/nyc-relabelled_all.json ] && [ -f exam/items/sealed/RELABELLED_READY ]; do sleep 20; done
echo "$(date) s1 nyc-relabelled"
for w in 1 2 3 4 5 6 7 8 9; do RUN_ALL_GRAPH=$PWD/exam/items/sealed/nyc-relabelled_b.graph.json $M $P ../exam/run_all.py --items exam/items/sealed/nyc-relabelled_all.json --out results/s1_nyc-relabelled --limit-s 14400 > results/o/s1rl_$w.log 2>&1 & done
wait
echo "s1 mini finished $(date)"
