#!/bin/bash
cd <mini> || exit 1
[ "$(diskutil info /Volumes/attic | awk '/Volume UUID/{print $3}')" = "7F9CEBB9-5477-4998-B519-D725B3A871CD" ] || { echo wrong drive; exit 1; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$HOME/x210-d/pylib:$PWD/vendor/qwenputer-riscv EDITS_META=<mini> EDITS_CC=/usr/bin/clang TOK_CKPT=<mini> T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1
export RUN_ALL_GRAPH=$PWD/exam/items/nyc_b.graph.json
M="/usr/bin/python3 tools/memguard.py --limit-gib 3 --log results/mem.log --"
P="$HOME/computing-field-venv/bin/python -B t8/fw/tokrun.py"
echo "$(date) r6 exam"
for w in 1 2 3 4 5 6 7 8; do $M $P ../exam/run_all.py --items exam/items/nyc_b_all.json --out results/r6_all --only base,fuzz,longest,blackout,all0,all1,all2 --limit-s 11000 > results/o/r6a_$w.log 2>&1 & done
wait
echo "r6 mini finished $(date)"
