#!/bin/zsh
# The freeze's sequence on writes.elf: proofs, then the chain. One GPU process at a time.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
R=t8/fw/results; D=$R/proofs; mkdir -p $D
G="python3 tools/memguard.py --limit-gib 32 --log t8/fw/mem.log --"
until grep -q "e4 finished" $R/e4.log; do /bin/sleep 10; done
pr() { n=$1; lim=$2; shift 2; timeout $lim ${=G} $PY -B t8/fw/prove_writes.py "$@" --out $D/$n > $D/$n.log 2>&1; echo "$(date +%T) $n code $?"; }
ok=1
for fl in print-writes read-writes; do
  pr ${fl}_slow0 1800 --flow $fl --part 0 --path slow
  pr ${fl}_fast0 900 --flow $fl --part 0 --path fast
  pr ${fl}_fast1 2100 --flow $fl --part 1 --path fast --stock 2
  pr ${fl}_slow1 1800 --flow $fl --part 1 --path slow
  (cd speed; PYTHONDONTWRITEBYTECODE=1 python3 prove.py compare ../$D/${fl}_fast0,../$D/${fl}_fast1 --ref ../$D/${fl}_slow0,../$D/${fl}_slow1 --out ../$D/$fl.json --add writes-$fl | cut -c1-500)
done
for mode in print read; do for set in dev hard; do
  timeout 8000 ${=G} $PY -B t8/fw/chain.py --machine writes --draw chain2_draw.json --set $set --flow $mode-writes --out $R/chainw_${mode}_$set --stock 2 --deadline-s 6000 > $R/chainw_${mode}_$set.log 2>&1; echo "$(date +%T) chainw_${mode}_$set $?"
done; done
for set in dev hard; do
  timeout 3000 ${=G} $PY -B t8/fw/chain.py --machine writes --set $set --flow print-writes --out $R/chainw_same_print_$set --stock 0 --deadline-s 2800 > $R/chainw_same_print_$set.log 2>&1; echo "$(date +%T) chainw_same_$set $?"
done
echo p finished
