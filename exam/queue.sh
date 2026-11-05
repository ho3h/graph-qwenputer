#!/bin/zsh
# exam/AFTER.md: one GPU process at a time.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_WRITES=1
R=exam/results; A=$R/after; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
until grep -q "wordings finished" $R/tonight.log; do /bin/sleep 3; done
pkill -f "exam/tonight.sh"; pkill -f "exam/d1m_stock.py"; /bin/sleep 5; pkill -f "exam/d1m_stock.py"; /bin/sleep 3
echo "$(date +%T) wordings finished; tonight.sh stopped"
step() { n=$1; lim=$2; shift 2; timeout $lim ${=G} "$@" > $A/$n.log 2>&1; echo "$(date +%T) $n code $?" }
step control_plainc 3900 $PY -B exam/controls.py plainc --out $A/control_plainc.jsonl --deadline-s 3600
step control_plaind 1800 $PY -B exam/controls.py plaind --out $A/control_plaind.jsonl --deadline-s 1500
echo plain finished
step map_out 2100 $PY -B t8/fw/tokrun.py ../exam/map_out.py
echo map finished
step lines 7000 $PY -B t8/fw/tokrun.py ../exam/lines_run.py --out $PWD/$A/lines --draw $PWD/$A/lines_draw.json --set conversations --verify-first 2 --deadline-s 5700
echo lines finished
step gaslight 2500 $PY -B t8/fw/tokrun.py ../exam/edit_run.py --out $PWD/$A/gaslight --draw $PWD/$A/gaslight_draw.json --set conversations --verify-first 2 --deadline-s 2300
python3 exam/edit_score.py $A/gaslight | cut -c1-300
timeout 1100 python3 tools/memguard.py --limit-gib 16 --log exam/mem.log -- $PY -B exam/gaslight_map.py $A/gaslight_map.jsonl 900 > $A/gaslight_map.log 2>&1; echo "$(date +%T) gaslight map code $?"
echo gaslight finished
step control_zeroed 900 $PY -B exam/controls.py zeroed --out $A/control_zeroed.jsonl --deadline-s 600
echo controls finished
for k in 0 1 2; do
  rm -rf $A/stock_d1m$k
  timeout 11800 ${=G} $PY -B exam/d1m_stock.py --part $k --out $A/stock_d1m$k --limit-s 11550 > $A/stock_d1m$k.log 2>&1; c=$?; echo "$(date +%T) stock part $k code $c"; tail -1 $A/stock_d1m$k.log | cut -c1-300
  (( c == 0 )) || { echo STOP stock part $k; exit 1 }
done
echo tonight finished
