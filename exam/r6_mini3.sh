#!/bin/bash
cd <mini> || exit 1
[ "$(diskutil info /Volumes/attic | awk '/Volume UUID/{print $3}')" = "7F9CEBB9-5477-4998-B519-D725B3A871CD" ] || { echo wrong drive; exit 1; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$HOME/x210-d/pylib:$PWD/vendor/qwenputer-riscv EDITS_META=<mini> EDITS_CC=/usr/bin/clang TOK_CKPT=<mini> T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
M="/usr/bin/python3 tools/memguard.py --limit-gib 3 --log results/mem.log --"
P="$HOME/computing-field-venv/bin/python -B t8/fw/tokrun.py"
mkdir -p results/o
echo "$(date) r6c2"
for k in 0 1 2 3 4 5 6 7; do R6C_SKIP=exam/results/r6_routes_done.json $M $P ../exam/r6_routes.py --shard $k/8 --out $PWD/results/r6_routes2 --limit-s 3600 > results/o/r6c2_$k.log 2>&1 & done
wait
echo "$(date) r6c2 finished"
for w in 1 2 3 4 5 6 7 8; do $M $P ../exam/run_limits.py --items exam/items/limits.json --out results/r6_limits --limit-s 7000 > results/o/u6_$w.log 2>&1 & done
wait
echo "$(date) u6 finished"
echo "r6 mini3 finished $(date)"
