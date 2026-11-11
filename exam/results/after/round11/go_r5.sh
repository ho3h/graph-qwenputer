#!/bin/zsh
# round 11 critic, r5 added mid-review: same aimed and fuzz seed, a second seed, and the near-full edit table on r4 and r5
cd "<repo>"
R=exam/results/after/round11
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_WRITES=1
run() { n=$1; shift; nice -n 15 python3 tools/memguard.py --limit-gib 6 --log $R/$n.mem -- $PY t8/fw/tokrun.py ../exam/results/after/round11/attack.py --out "$PWD/$R/$n.jsonl" "$@" > $R/$n.log 2>&1 }
( export T8_R5=1; run r5_aimed --aimed ) &
( export T8_R5=1; run r5_fuzz --fuzz 100000 --seed round11a --limit-s 1200 --no-ref ) &
( export T8_R5=1; run r5_fuzzb --fuzz 100000 --seed round11b --limit-s 1200 --no-ref ) &
( export T8_R5=1; run r5_cap --cap --no-ref ) &
( run r4_cap --cap --no-ref ) &
wait
