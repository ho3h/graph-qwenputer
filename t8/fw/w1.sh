#!/bin/zsh
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_WRITES=1 T8_NOUN=on
R=t8/fw/results
step() { name=$1; lim=$2; shift 2; echo "$(date '+%T') start $name"; timeout $lim python3 tools/memguard.py --limit-gib 12 --log t8/fw/mem.log -- "$@" > $R/w_$name.log 2>&1; c=$?; echo "$(date '+%T') end $name code $c"; return $c; }
step writes 900 $PY -B t8/fw/test_clean.py --part writes --workers 4 || exit 1
step count 480 $PY -B t8/fw/count.py || exit 1
step stops 400 $PY -B t8/fw/test_clean.py --part stops --workers 1 || exit 1
step awkward 300 $PY -B t8/fw/test_clean.py --part awkward --workers 1 || exit 1
step fuzz 400 $PY -B t8/fw/test_clean.py --part fuzz --workers 4 || exit 1
step m1 1100 $PY -B t8/fw/test_m1.py --workers 4 || exit 1
echo w1 finished
