#!/bin/zsh
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
R=t8/fw/results
G="python3 tools/memguard.py --limit-gib 32 --log t8/fw/mem.log --"
while pgrep -f "t8/fw/edit.py --out t8/fw/results/writes_stock " > /dev/null; do /bin/sleep 10; done
echo writes_stock ended
T8_WRITES=1 timeout 1300 ${=G} env T8_WRITES=1 $PY -B t8/fw/tokrun.py ../t8/fw/edit.py --out $R/writes_stock2 --draw $R/writes_stock2_draw.json --verify-first 1 --deadline-s 1200 --question-limit-s 1200 > $R/writes_stock2.log 2>&1; echo writes_stock2 $?
for set in dev hard; do
timeout 14000 ${=G} $PY -B t8/fw/chain.py --set $set --flow read-one --out $R/chain_read_$set --stock 2 --deadline-s 9450 > $R/chain_read_$set.log 2>&1; echo read_$set $?
done
echo e4 finished
