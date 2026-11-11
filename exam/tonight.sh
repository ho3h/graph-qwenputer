#!/bin/zsh
# exam/AFTER.md G, H, I. One GPU process at a time. A stock difference stops what's after it.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_WRITES=1
R=exam/results; A=$R/after/w; mkdir -p $A; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
[[ "$(shasum -a 256 t8/fw/build_r1/writes.elf | cut -d' ' -f1)" == ad1abcc6cec073b52e088c4d0d1752dd9908f6f77d39d950ff0d5a5e70c41fe0 ]] || { echo STOP elf; exit 1 }
timeout 1500 ${=G} $PY -B exam/wordings.py machine --out $A/print --flow print-writes --stock 4 --deadline-s 1350 > $A/print.log 2>&1; echo "$(date +%T) print code $?"
timeout 1200 python3 tools/memguard.py --limit-gib 16 --log exam/mem.log -- $PY -B exam/wordings.py host --out $A/host.jsonl --deadline-s 1050 > $A/host.log 2>&1; echo "$(date +%T) host code $?"
python3 exam/score_d1m.py --n 100 --rows $A/print --host $A/host.jsonl --out $A/print_score.json > $A/print_score.log; cut -c1-1000 $A/print_score.log
python3 -c "import json,sys;d=json.load(open('$A/print_score.json'));sys.exit(0 if d['stock']['passed'] and not d['stock']['mismatches'] else 1)" || { echo STOP stock sample; exit 1 }
timeout 1650 ${=G} $PY -B exam/wordings.py machine --out $A/reply --flow read-writes --stock 0 --deadline-s 1500 > $A/reply.log 2>&1; echo "$(date +%T) reply code $?"
python3 exam/score_reply.py --rows $A/reply --out $A/reply_score.json --md $A/reply_replies.md | cut -c1-500
python3 exam/draw_shared.py $R/after/shared_draw.json
timeout 2000 ${=G} $PY -B t8/fw/tokrun.py ../exam/edit_run.py --out $R/after/shared --draw $R/after/shared_draw.json --verify-first 0 --deadline-s 1800 > $R/after/shared.log 2>&1; echo "$(date +%T) shared code $?"
python3 exam/edit_score.py $R/after/shared | cut -c1-700
b=2430; t0=$SECONDS
while (( SECONDS - t0 < b )); do
  python3 tools/memguard.py --limit-gib 16 --log exam/mem.log -- $PY -B exam/mapped.py --arm M4 --out $R/after/mapped/M4.jsonl --limit 25 --deadline-s $(( b - (SECONDS - t0) )) >> $R/after/mapped/M4.log 2>&1
  c=$?; tail -3 $R/after/mapped/M4.log | grep -q "arm finished" && break
  (( c == 0 )) || { echo "M4 code $c"; break }
done
python3 exam/score_mapped.py $R/after/mapped | cut -c1-600
echo wordings finished
for k in 0 1 2; do
  timeout 11800 ${=G} $PY -B exam/d1m_stock.py --part $k --out $R/after/stock_d1m$k --limit-s 11550 > $R/after/stock_d1m$k.log 2>&1; c=$?; echo "$(date +%T) stock part $k code $c"; tail -1 $R/after/stock_d1m$k.log | cut -c1-300
  (( c == 0 )) || { echo STOP stock part $k; exit 1 }
done
echo tonight finished
