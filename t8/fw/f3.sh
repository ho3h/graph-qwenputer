#!/bin/zsh
# E's revision, then its lockstep, then F3, one after another.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
R=t8/fw/results
G="python3 tools/memguard.py --limit-gib 32 --log t8/fw/mem.log --"
export T8_EDIT_RULE=" When the user says a node is closed or has reopened, first call close or reopen on it, then answer."
timeout 7200 ${=G} $PY -B t8/fw/tokrun.py ../t8/fw/edit.py --out $R/edit_r1 --deadline-s 7000 > $R/edit_r1.log 2>&1; echo edit_r1 $?
$PY -B t8/fw/edit_pick.py
timeout 4050 ${=G} $PY -B t8/fw/tokrun.py ../t8/fw/edit.py --out $R/edit_r1_stock --draw $R/edit_stock_draw.json --verify-first 3 --deadline-s 4000 --question-limit-s 1500 > $R/edit_r1_stock.log 2>&1; echo edit_stock $?
unset T8_EDIT_RULE
for set in dev hard; do
timeout 8000 ${=G} $PY -B t8/fw/chain.py --set $set --flow print-one --out $R/chain_print_$set --stock 2 --deadline-s 5430 > $R/chain_print_$set.log 2>&1; echo print_$set $?
done
for set in dev hard; do
timeout 14000 ${=G} $PY -B t8/fw/chain.py --set $set --flow read-one --out $R/chain_read_$set --stock 2 --deadline-s 9450 > $R/chain_read_$set.log 2>&1; echo read_$set $?
done
echo f3 finished
