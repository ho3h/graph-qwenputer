#!/bin/zsh
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_WRITES=1 T8_NOUN=on
D=exam/results/nyc_pick; mkdir -p $D
for k in 0 1 2 3 4 5; do
  timeout 1500 python3 tools/memguard.py --limit-gib 4 --log exam/results/mem.log -- $PY -B t8/fw/tokrun.py ../exam/pick_nyc.py run --shard $k/6 --baseline t8/fw/results/cov_baseline_w.json --out $D > $D/log$k.txt 2>&1 &
done
wait
python3 exam/pick_nyc.py choose --dir $D --budget 336000 --out exam/results/plan_nyc.json | tee $D/choose.log
echo pick finished
