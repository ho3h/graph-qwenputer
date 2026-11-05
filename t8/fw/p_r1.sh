#!/bin/zsh
# exam/R1.md: the fast runner's proofs on build_r1/writes.elf: p.sh's method and limits. One GPU process at a time.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_WRITES=1 T8_NOUN=on T8_R1=1
R=t8/fw/results/r1; D=$R/proofs; mkdir -p $D
G="python3 tools/memguard.py --limit-gib 32 --log t8/fw/mem.log --"
pr() { n=$1; lim=$2; shift 2; timeout $lim ${=G} $PY -B t8/fw/prove_writes.py "$@" --out $D/$n > $D/$n.log 2>&1; echo "$(date +%T) $n code $?"; }
for fl in print-writes read-writes; do
  pr ${fl}_slow0 1800 --flow $fl --part 0 --path slow
  pr ${fl}_fast0 900 --flow $fl --part 0 --path fast
  pr ${fl}_fast1 2100 --flow $fl --part 1 --path fast --stock 2
  pr ${fl}_slow1 1800 --flow $fl --part 1 --path slow
  (cd speed; PYTHONDONTWRITEBYTECODE=1 python3 prove.py compare ../$D/${fl}_fast0,../$D/${fl}_fast1 --ref ../$D/${fl}_slow0,../$D/${fl}_slow1 --out ../$D/$fl.json --add r1-$fl | cut -c1-500)
done
echo p_r1 finished
