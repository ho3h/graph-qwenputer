#!/bin/zsh
# Step C1, one at a time, CPU only. Stops at the first failure.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv"
R=t8/fw/results
step() { name=$1; lim=$2; shift 2; echo "$(date '+%T') start $name"; timeout $lim python3 tools/memguard.py --limit-gib 12 --log t8/fw/mem.log -- "$@" > $R/$name.log 2>&1; c=$?; echo "$(date '+%T') end $name code $c"; tail -1 $R/$name.log | cut -c1-300; return $c; }
step awkward 190 $PY -B t8/fw/test_clean.py --part awkward --workers 1 || exit 1
step m1_on 1100 env T8_NOUN=on $PY -B t8/fw/test_m1.py --workers 4 || exit 1
step labels 2160 $PY -B t8/fw/test_clean.py --part labels --workers 4 || exit 1
step fuzzfw 585 $PY -B t8/fw/test_clean.py --part fuzzfw --workers 4
echo c1 finished code $?
