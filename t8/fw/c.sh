#!/bin/zsh
# Critic's item 2 and 1a on writes.elf, CPU: whole-table check, every label, fw's fuzz. Reference machine and tables.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_WRITES=1 T8_NOUN=on
R=t8/fw/results
step() { name=$1; lim=$2; shift 2; echo "$(date '+%T') start $name"; timeout $lim python3 tools/memguard.py --limit-gib 12 --log t8/fw/mem.log -- "$@" > $R/w_$name.log 2>&1; c=$?; echo "$(date '+%T') end $name code $c"; }
step labels 2400 $PY -B t8/fw/test_clean.py --part labels --workers 4
step fuzzfw 2400 $PY -B t8/fw/test_clean.py --part fuzzfw --workers 4
step closures 2400 $PY -B t8/fw/closures.py --workers 4
echo c finished
