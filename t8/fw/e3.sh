#!/bin/zsh
# After E2's executor rows and W1: W2, W3, then F3's read runs. One GPU process at a time. Stops if W1 didn't pass.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
R=t8/fw/results
G="python3 tools/memguard.py --limit-gib 32 --log t8/fw/mem.log --"
while pgrep -f "t8/fw/edit.py --out t8/fw/results/edit2 " > /dev/null; do /bin/sleep 10; done
echo edit2 ended
until grep -q "w1 finished" $R/w1.log || grep -qE "end [a-z0-9]+ code [1-9]" $R/w1.log; do /bin/sleep 15; done
grep -q "w1 finished" $R/w1.log || { echo "W1 did not pass; W2 not started"; }
if grep -q "w1 finished" $R/w1.log; then
T8_WRITES=1 timeout 5100 ${=G} env T8_WRITES=1 $PY -B t8/fw/tokrun.py ../t8/fw/edit.py --out $R/writes --draw $R/edit3_draw.json --deadline-s 5000 > $R/writes.log 2>&1; echo writes $?
$PY -B t8/fw/writes_pick.py
T8_WRITES=1 timeout 2900 ${=G} env T8_WRITES=1 $PY -B t8/fw/tokrun.py ../t8/fw/edit.py --out $R/writes_stock --draw $R/writes_stock_draw.json --verify-first 3 --deadline-s 2800 --question-limit-s 1400 > $R/writes_stock.log 2>&1; echo writes_stock $?
fi
for set in dev hard; do
timeout 14000 ${=G} $PY -B t8/fw/chain.py --set $set --flow read-one --out $R/chain_read_$set --stock 2 --deadline-s 9450 > $R/chain_read_$set.log 2>&1; echo read_$set $?
done
echo e3 finished
