#!/bin/zsh
# round 11 critic: r5 aimed without the slow reference engine, so it finishes; closure-cost rows
cd "<repo>"
R=exam/results/after/round11
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_WRITES=1
run() { n=$1; shift; nice -n 15 python3 tools/memguard.py --limit-gib 6 --log $R/$n.mem -- $PY t8/fw/tokrun.py ../exam/results/after/round11/attack.py --out "$PWD/$R/$n.jsonl" "$@" > $R/$n.log 2>&1 }
( run r5_aimed_noref --aimed --no-ref ) &
( run r5_capclosed --capclosed --no-ref ) &
wait
