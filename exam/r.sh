#!/bin/zsh
# Runs the machine exam on items $1 into $2, $3 workers, limit $4 s, under memguard; optional $5 --only list.
cd "/Users/tedsandtads/computing field/xseries/X2.10"
PY=/Users/tedsandtads/Documents/GitHub/qwenputer/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_WRITES=1 T8_NOUN=on
mkdir -p $2
for w in $(seq 1 $3); do
  python3 tools/memguard.py --limit-gib 6 --log exam/mem.log -- $PY -B t8/fw/tokrun.py ../exam/run_machine.py --items $1 --out $2 --limit-s $4 --only "$5" > $2/worker$w.log 2>&1 &
done
wait
echo finished
