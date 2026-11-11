#!/bin/zsh
# exam/AFTER.md K2 and I, after the wordings: k.sh without K1, which Theo asked to bring forward.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_WRITES=1
R=exam/results; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
until grep -q "wordings finished" $R/tonight.log; do /bin/sleep 3; done
pkill -f "exam/tonight.sh"; pkill -f "exam/d1m_stock.py"; /bin/sleep 5; pkill -f "exam/d1m_stock.py"; /bin/sleep 3
echo "$(date +%T) stopped tonight.sh before stock"
until grep -q "plain finished" $R/k1.log; do /bin/sleep 10; done
timeout 900 ${=G} $PY -B exam/controls.py zeroed --out $R/after/control_zeroed.jsonl --deadline-s 600 > $R/after/control_zeroed.log 2>&1; echo "$(date +%T) zeroed code $?"
echo k finished
for k in 0 1 2; do
  rm -rf $R/after/stock_d1m$k
  timeout 11800 ${=G} $PY -B exam/d1m_stock.py --part $k --out $R/after/stock_d1m$k --limit-s 11550 > $R/after/stock_d1m$k.log 2>&1; c=$?; echo "$(date +%T) stock part $k code $c"; tail -1 $R/after/stock_d1m$k.log | cut -c1-300
  (( c == 0 )) || { echo STOP stock part $k; exit 1 }
done
echo tonight finished
