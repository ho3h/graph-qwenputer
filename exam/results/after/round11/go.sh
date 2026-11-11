#!/bin/zsh
# round 11 critic: r4 and r2 on the same aimed and fuzz sequences, low priority, CPU only
cd "<repo>"
R=exam/results/after/round11
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_NOUN=on T8_R1=1 T8_R2=1 T8_WRITES=1
run() { # name args...
  n=$1; shift
  nice -n 15 python3 tools/memguard.py --limit-gib 6 --log $R/$n.mem -- $PY t8/fw/tokrun.py ../exam/results/after/round11/attack.py --out "$PWD/$R/$n.jsonl" "$@" > $R/$n.log 2>&1
}
( export T8_R3=1 T8_R4=1; run r4_aimed --aimed ) &
( run r2_aimed --aimed --no-ref ) &
( export T8_R3=1 T8_R4=1; run r4_fuzz --fuzz 100000 --seed round11a --limit-s 1200 --no-ref ) &
( run r2_fuzz --fuzz 100000 --seed round11a --limit-s 1200 --no-ref ) &
wait
