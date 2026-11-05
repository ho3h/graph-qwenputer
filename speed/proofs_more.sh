#!/bin/zsh
# S17 P4 and P5. Runs after P1.
cd "${0:A:h}"; D=results/proofs
until grep -q . $D/p1.json 2>/dev/null; do sleep 20; done
python3 prove.py pairs-draw ../rvc/results/chain4_draw.json 16 0 $D/p4_q0.json
python3 prove.py pairs-draw ../rvc/results/chain4_draw.json 16 16 $D/p4_q1.json
python3 prove.py pairs-draw ../rvc/results/chain3_draw.json 16 0 $D/p5_a.json
python3 - <<'P'
import json
a=json.load(open("results/proofs/p4_q0.json"))+json.load(open("results/proofs/p4_q1.json"))
json.dump(a,open("results/proofs/p4_all.json","w"))
P
r() { name=$1; lim=$2; gib=$3; shift 3; ./run.sh $lim $gib fast.py "$@" > $D/$name.log 2>&1; echo "$(date +%T) $name code $?"; }
r p4_slow_0 1000 32 --machine tok --flow print-chain4 --questions $D/p4_q0.json --out $D/p4_slow_0 --force slow --stock 0
r p4_fast_0 500 28 --machine tok --flow print-chain4 --questions $D/p4_q0.json --out $D/p4_fast_0 --force fast --stock 0
r p4_fast_1 1300 32 --machine tok --flow print-chain4 --questions $D/p4_q1.json --out $D/p4_fast_1 --force fast --stock 2 --stock-limit-s 800
r p4_slow_1 1000 32 --machine tok --flow print-chain4 --questions $D/p4_q1.json --out $D/p4_slow_1 --force slow --stock 0
python3 prove.py compare $D/p4_fast_0,$D/p4_fast_1 --ref $D/p4_slow_0,$D/p4_slow_1 --out $D/p4.json --add p4 | cut -c1-500
r p5a 900 32 --machine fw --flow print-chain3 --questions $D/p5_a.json --out $D/p5a --force fast --stock 1 --stock-limit-s 500
python3 prove.py compare $D/p5a --ref-chain3 --out $D/p5a.json --add p5a | cut -c1-500
r p5b 1800 32 --machine fw --flow print-chain4 --readback 96 --questions $D/p4_all.json --out $D/p5b --force fast --stock 1 --stock-limit-s 500
python3 prove.py compare $D/p5b --ref-chain4 --out $D/p5b.json --add p5b | cut -c1-500
echo more done
