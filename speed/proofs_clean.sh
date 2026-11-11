#!/bin/zsh
# S18: t8's final firmware, print-one and read-one. Alternating, same questions.
cd "${0:A:h}"; D=results/proofs/clean; mkdir -p $D
r() { n=$1; lim=$2; gib=$3; shift 3; ./run.sh $lim $gib prove_clean.py "$@" --out $D/$n > $D/$n.log 2>&1; echo "$(date +%T) $n code $?"; }
for fl in print-one read-one; do
  r ${fl}_slow0 1800 32 --flow $fl --part 0 --path slow
  r ${fl}_fast0 900 28 --flow $fl --part 0 --path fast
  r ${fl}_fast1 2100 32 --flow $fl --part 1 --path fast --stock 2
  r ${fl}_slow1 1800 32 --flow $fl --part 1 --path slow
  python3 prove.py compare $D/${fl}_fast0,$D/${fl}_fast1 --ref $D/${fl}_slow0,$D/${fl}_slow1 --out $D/$fl.json --add clean-$fl | cut -c1-600
done
echo clean done
