#!/bin/zsh
# exam/R1.md: the proofs again on build_r1/writes.elf, CPU, reference machine and tables. Stops at the first failure.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_WRITES=1 T8_NOUN=on T8_R1=1
R=t8/fw/results/r1; mkdir -p $R
step() { name=$1; lim=$2; shift 2; echo "$(date '+%T') start $name"; timeout $lim python3 tools/memguard.py --limit-gib 12 --log t8/fw/mem.log -- "$@" > $R/$name.log 2>&1; c=$?; echo "$(date '+%T') end $name code $c"; tail -1 $R/$name.log | cut -c1-260; return $c; }
step r1 900 $PY -B t8/fw/test_clean.py --part r1 --workers 4 || exit 1
step writes 900 $PY -B t8/fw/test_clean.py --part writes --workers 4 || exit 1
step stops 400 $PY -B t8/fw/test_clean.py --part stops --workers 1 || exit 1
step awkward 300 $PY -B t8/fw/test_clean.py --part awkward --workers 1 || exit 1
step fuzz 400 $PY -B t8/fw/test_clean.py --part fuzz --workers 4 || exit 1
step m1 1100 $PY -B t8/fw/test_m1.py --workers 4 || exit 1
step tablecheck 900 $PY -B t8/fw/tokrun.py ../t8/fw/tablecheck.py --label r1 --out $R/tablecheck.json
step labels 2400 $PY -B t8/fw/test_clean.py --part labels --workers 4
step fuzzfw 2400 $PY -B t8/fw/test_clean.py --part fuzzfw --workers 4
step closures 2400 $PY -B t8/fw/closures.py --workers 4 --out $R/closures.json
echo r1 finished
