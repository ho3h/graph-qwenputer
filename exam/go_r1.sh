#!/bin/zsh
# exam/R1.md, in order. Stops at the first bar missed. GPU part; go_r1a.sh comes first.
cd "/Users/tedsandtads/computing field/xseries/X2.10"
PY=/Users/tedsandtads/Documents/GitHub/qwenputer/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_WRITES=1
R=exam/results; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
ELF=ad1abcc6cec073b52e088c4d0d1752dd9908f6f77d39d950ff0d5a5e70c41fe0
[[ "$(shasum -a 256 t8/fw/build_r1/writes.elf | cut -d' ' -f1)" == $ELF ]] || { echo STOP elf; exit 1 }
python3 t8/fw/r1_check.py || { echo STOP proofs; exit 1 }
python3 exam/check_freeze.py FREEZE_r1.json || { echo STOP freeze hashes; exit 1 }
python3 -c "import json,sys;d=json.load(open('$R/nyc_r1_score.json'));sys.exit(0 if d['D2m_pass'] and d['D4m_pass'] else 1)" || { echo STOP machine; exit 1 }
$PY -B exam/stock_r1.py $R/plan_r1.json
timeout 2400 ${=G} $PY -B t8/fw/tokrun.py stock_trace.py --plan $PWD/$R/plan_r1.json --outdir $PWD/$R/nyc_r1_stock --hours 0.58 > $R/nyc_r1_stock.log 2>&1; echo "$(date +%T) stock code $?"
timeout 600 python3 tools/memguard.py --limit-gib 12 --log exam/mem.log -- $PY -B t8/fw/tokrun.py check_trace.py --trace $PWD/$R/nyc_r1_stock --plan $PWD/$R/plan_r1.json --out $PWD/$R/nyc_r1_stock_check.json > $R/nyc_r1_stock_check.log 2>&1; echo "$(date +%T) stock check code $?"
python3 -c "import json,sys;d=json.load(open('$R/nyc_r1_stock_check.json'));j=d['jobs'];print(len(j),sum(x['positions'] for x in j),sum(x['positions_differing'] for x in j));sys.exit(0 if len(j)==3 and all(x['finished'] and not x['positions_differing'] and not x['stock_wrong'] for x in j) else 1)" || { echo STOP stock; exit 1 }
timeout 7200 ${=G} $PY -B exam/d1m.py --name nyc --n 200 --out $R/nyc_r1_d1m --stock 4 --stock-limit-s 3000 --deadline-s 4050 > $R/nyc_r1_d1m.log 2>&1; echo "$(date +%T) d1m code $?"
timeout 3300 python3 tools/memguard.py --limit-gib 16 --log exam/mem.log -- $PY -B exam/host.py --name nyc --n 200 --out $R/nyc_r1_host.jsonl --deadline-s 3150 > $R/nyc_r1_host.log 2>&1; echo "$(date +%T) host code $?"
python3 exam/score_d1m.py --n 300 --rows $R/nyc_r1_d1m --host $R/nyc_r1_host.jsonl --out $R/nyc_r1_d1m_score.json > $R/nyc_r1_d1m_score.log; cut -c1-1000 $R/nyc_r1_d1m_score.log
python3 -c "import json,sys;d=json.load(open('$R/nyc_r1_d1m_score.json'));sys.exit(0 if d['bar']['pass'] and d['machine']['machine_equals_host_tool']==300 else 1)" || { echo D1m bar missed, void or a row differing from the host; exit 1 }
echo d1m passed
timeout 4800 ${=G} $PY -B exam/d1m.py --name nyc --n 200 --flow read-writes --out $R/nyc_r1_d1r --stock 0 --deadline-s 4500 > $R/nyc_r1_d1r.log 2>&1; echo "$(date +%T) d1r code $?"
python3 exam/score_reply.py --rows $R/nyc_r1_d1r --out $R/nyc_r1_d1r_score.json --md $R/nyc_r1_d1r_replies.md | cut -c1-600
python3 exam/edit_draw.py --name nyc --out $R/nyc_r1_edit_draw.json
timeout 7000 ${=G} $PY -B t8/fw/tokrun.py ../exam/edit_run.py --out $R/nyc_r1_edit --draw $R/nyc_r1_edit_draw.json --verify-first 2 --deadline-s 6800 > $R/nyc_r1_edit.log 2>&1; echo "$(date +%T) edit code $?"
python3 exam/edit_score.py $R/nyc_r1_edit | cut -c1-1000
echo go_r1 finished
