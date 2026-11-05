#!/bin/zsh
# exam/R1.md, CPU exams: names, D4m, D2m. Stops at the first miss.
cd "/Users/tedsandtads/computing field/xseries/X2.10"
PY=/Users/tedsandtads/Documents/GitHub/qwenputer/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_WRITES=1
R=exam/results; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
ELF=ad1abcc6cec073b52e088c4d0d1752dd9908f6f77d39d950ff0d5a5e70c41fe0
[[ "$(shasum -a 256 t8/fw/build_r1/writes.elf | cut -d' ' -f1)" == $ELF ]] || { echo STOP elf; exit 1 }
python3 exam/check_freeze.py FREEZE_r1.json || { echo STOP freeze hashes; exit 1 }
timeout 4300 python3 tools/memguard.py --limit-gib 6 --log exam/mem.log -- $PY -B t8/fw/tokrun.py ../exam/r1_pairs.py --out $R/nyc_r1_pairs.json > $R/nyc_r1_pairs.log 2>&1; c=$?; echo "$(date +%T) names code $c"; tail -1 $R/nyc_r1_pairs.log | cut -c1-400
[[ $c == 0 ]] || { echo STOP names; exit 1 }
timeout 900 exam/r.sh exam/items/nyc.json $R/nyc_r1 6 700 "paths" > $R/nyc_r1_d4m.log 2>&1; echo "$(date +%T) d4m code $?"
python3 exam/score_machine.py --items exam/items/nyc.json --rows $R/nyc_r1 --out $R/nyc_r1_score.json > $R/nyc_r1_score.log; cut -c1-700 $R/nyc_r1_score.log
python3 -c "import json,sys;d=json.load(open('$R/nyc_r1_score.json'));sys.exit(0 if d['D4m_pass'] else 1)" || { echo STOP D4m bar; exit 1 }
timeout 7400 exam/r.sh exam/items/nyc.json $R/nyc_r1 6 7000 "base,close" > $R/nyc_r1_d2m.log 2>&1; echo "$(date +%T) d2m code $?"
python3 exam/score_machine.py --items exam/items/nyc.json --rows $R/nyc_r1 --out $R/nyc_r1_score.json > $R/nyc_r1_score.log; cut -c1-700 $R/nyc_r1_score.log
python3 -c "import json,sys;d=json.load(open('$R/nyc_r1_score.json'));sys.exit(0 if d['D2m_pass'] and d['D4m_pass'] else 1)" || { echo STOP D2m bar; exit 1 }
python3 -c "import json,glob,sys;b=[p for p in glob.glob('$R/nyc_r1/*.json') if 'cov-' not in p and json.load(open(p)).get('elf_sha256')!='$ELF' and 'finished' in json.load(open(p))];print('units on another elf',b);sys.exit(1 if b else 0)" || { echo STOP elf; exit 1 }
echo machine passed
echo go_r1a finished
