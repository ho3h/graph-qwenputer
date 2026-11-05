#!/bin/zsh
# round 11 critic: the aimed sections the slow runs hadn't reached, on r5 (rng order unchanged, so same sequences)
cd "<repo>"
R=exam/results/after/round11
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_WRITES=1
nice -n 15 python3 tools/memguard.py --limit-gib 6 --log $R/r5_tail.mem -- $PY t8/fw/tokrun.py ../exam/results/after/round11/attack.py --out "$PWD/$R/r5_tail.jsonl" --aimed --only swap,walkback,newstops,closewrite,station,stale --no-ref > $R/r5_tail.log 2>&1
