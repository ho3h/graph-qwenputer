#!/bin/zsh
# The rest of F3's print, the stated-edit test, its lockstep, then F3's read runs. One after another.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
R=t8/fw/results
G="python3 tools/memguard.py --limit-gib 32 --log t8/fw/mem.log --"
while pgrep -f "t8/fw/chain.py --set dev --flow print-one" > /dev/null; do /bin/sleep 10; done
echo print_dev ended
timeout 8000 ${=G} $PY -B t8/fw/chain.py --set hard --flow print-one --out $R/chain_print_hard --stock 2 --deadline-s 5430 > $R/chain_print_hard.log 2>&1; echo print_hard $?
timeout 7200 ${=G} $PY -B t8/fw/tokrun.py ../t8/fw/edit.py --out $R/edit2 --draw $R/edit2_draw.json --deadline-s 7000 > $R/edit2.log 2>&1; echo edit2 $?
$PY -B t8/fw/edit_pick.py
timeout 4050 ${=G} $PY -B t8/fw/tokrun.py ../t8/fw/edit.py --out $R/edit2_stock --draw $R/edit2_stock_draw.json --verify-first 3 --deadline-s 4000 --question-limit-s 1500 > $R/edit2_stock.log 2>&1; echo edit2_stock $?
for set in dev hard; do
timeout 14000 ${=G} $PY -B t8/fw/chain.py --set $set --flow read-one --out $R/chain_read_$set --stock 2 --deadline-s 9450 > $R/chain_read_$set.log 2>&1; echo read_$set $?
done
echo e2 finished
