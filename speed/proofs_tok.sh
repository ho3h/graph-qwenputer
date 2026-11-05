#!/bin/zsh
# S17 P2, P3 on the normal-token firmware: alternate fast and slow, same questions, then flags.
cd "${0:A:h}"; D=results/proofs
one() { ./run.sh $1 $2 fast.py --machine tok --flow print-chain3 --questions $D/p2_q$3.json --out $D/p2_$4_$3 --force $4 --stock $5 > $D/p2_$4_$3.log 2>&1; echo "$(date +%T) p2 $4 $3 code $?"; }
one 500 32 0 slow 0
for r in 1 2 3; do
  python3 prove.py pairs-draw ../rvc/results/chain3_draw.json 8 $((r*8)) $D/p2_q$r.json
  if [ $((r%2)) = 1 ]; then one 500 32 $r slow 0; one 500 28 $r fast 0; else one 500 28 $r fast 0; one 500 32 $r slow 0; fi
done
python3 - <<'P'
import json
a=[]
for i in range(4): a+=json.load(open(f"results/proofs/p2_q{i}.json"))
json.dump(a,open("results/proofs/p2_all.json","w"))
P
# stock sample for the print flow: resumes the finished records of round 0, runs nothing new but the sample
./run.sh 900 32 fast.py --machine tok --flow print-chain3 --questions $D/p2_q0.json --out $D/p2_fast_0 --force fast --stock 2 --stock-limit-s 800 > $D/p2_stock.log 2>&1; echo "$(date +%T) stock code $?"
python3 prove.py compare $D/p2_fast_0,$D/p2_fast_1,$D/p2_fast_2,$D/p2_fast_3 --ref $D/p2_slow_0,$D/p2_slow_1,$D/p2_slow_2,$D/p2_slow_3 --out results/proofs/p2.json --add p2
./run.sh 500 28 fast.py --machine tok --flow print-chain3 --speed-flags --questions $D/p2_all.json --out $D/p3_fast --force fast --stock 0 > $D/p3.log 2>&1; echo "$(date +%T) p3 code $?"
python3 prove.py compare $D/p3_fast --ref $D/p2_slow_0,$D/p2_slow_1,$D/p2_slow_2,$D/p2_slow_3 --first-lines --out results/proofs/p3.json
echo chain done
