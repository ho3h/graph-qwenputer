#!/bin/zsh
# The exams, in registered order. Stops at the first bar missed. Needs exam/FROZEN.
cd "/Users/tedsandtads/computing field/xseries/X2.10"
[[ -f exam/FROZEN ]] || { echo no freeze; exit 2 }
PY=/Users/tedsandtads/Documents/GitHub/qwenputer/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on
R=exam/results; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
T8_WRITES=1 timeout 900 python3 tools/memguard.py --limit-gib 8 --log exam/mem.log -- env T8_WRITES=1 $PY -B t8/fw/tokrun.py ../exam/items.py --name nyc --out exam/items/nyc.json > $R/nyc_items.log 2>&1; c=$?; echo "$(date +%T) items code $c"; tail -1 $R/nyc_items.log | cut -c1-600
[[ $c == 0 ]] || { echo STOP items; exit 1 }
python3 exam/check_freeze.py || { echo STOP freeze hashes; exit 1 }
timeout 900 exam/r.sh exam/items/nyc.json $R/nyc 6 700 "paths" > $R/nyc_d4m.log 2>&1; echo "$(date +%T) d4m code $?"
python3 exam/score_machine.py --items exam/items/nyc.json --rows $R/nyc --out $R/nyc_score.json > $R/nyc_score.log; cut -c1-900 $R/nyc_score.log
python3 -c "import json,sys;d=json.load(open('$R/nyc_score.json'));sys.exit(0 if d['D4m_pass'] else 1)" || { echo STOP D4m bar; exit 1 }
echo d4m passed
timeout 7400 exam/r.sh exam/items/nyc.json $R/nyc 6 7000 "base,close" > $R/nyc_d2m.log 2>&1; echo "$(date +%T) d2m code $?"
python3 exam/score_machine.py --items exam/items/nyc.json --rows $R/nyc --out $R/nyc_score.json > $R/nyc_score.log; cut -c1-900 $R/nyc_score.log
python3 -c "import json,sys;d=json.load(open('$R/nyc_score.json'));sys.exit(0 if d['D2m_pass'] and d['D4m_pass'] else 1)" || { echo STOP D2m bar; exit 1 }
echo machine passed
timeout 6000 ${=G} $PY -B exam/d1m.py --name nyc --out $R/nyc_d1m --stock 4 --stock-limit-s 3000 --deadline-s 2700 > $R/nyc_d1m.log 2>&1; echo "$(date +%T) d1m code $?"
timeout 2300 python3 tools/memguard.py --limit-gib 16 --log exam/mem.log -- $PY -B exam/host.py --name nyc --out $R/nyc_host.jsonl --deadline-s 2100 > $R/nyc_host.log 2>&1; echo "$(date +%T) host code $?"
python3 exam/score_d1m.py --rows $R/nyc_d1m --host $R/nyc_host.jsonl --out $R/nyc_d1m_score.json > $R/nyc_d1m_score.log; cut -c1-1200 $R/nyc_d1m_score.log
python3 -c "import json,sys;d=json.load(open('$R/nyc_d1m_score.json'));sys.exit(0 if d['bar']['pass'] else 1)" || { echo D1m bar missed or void; exit 1 }
echo d1m passed
timeout 3300 ${=G} $PY -B exam/d1m.py --name nyc --flow read-writes --out $R/nyc_d1r --stock 0 --deadline-s 3000 > $R/nyc_d1r.log 2>&1; echo "$(date +%T) d1r code $?"
python3 exam/score_reply.py --rows $R/nyc_d1r --out $R/nyc_d1r_score.json --md $R/nyc_d1r_replies.md | cut -c1-800
python3 exam/edit_draw.py --name nyc --out $R/nyc_edit_draw.json
T8_WRITES=1 timeout 7000 ${=G} env T8_WRITES=1 $PY -B t8/fw/tokrun.py ../exam/edit_run.py --out $R/nyc_edit --draw $R/nyc_edit_draw.json --verify-first 2 --deadline-s 6800 > $R/nyc_edit.log 2>&1; echo "$(date +%T) edit code $?"
python3 exam/edit_score.py $R/nyc_edit | cut -c1-1200
echo go finished
