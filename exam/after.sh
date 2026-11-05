#!/bin/zsh
# exam/AFTER.md, in order. GPU one process at a time. A stock difference stops what's after it.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_WRITES=1
R=exam/results; A=$R/after; mkdir -p $A/pick; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
ELF=ad1abcc6cec073b52e088c4d0d1752dd9908f6f77d39d950ff0d5a5e70c41fe0
[[ "$(shasum -a 256 t8/fw/build_r1/writes.elf | cut -d' ' -f1)" == $ELF ]] || { echo STOP elf; exit 1 }
for k in 0 1 2 3; do
  timeout 1500 python3 tools/memguard.py --limit-gib 4 --log $R/mem.log -- $PY -B t8/fw/tokrun.py ../exam/pick_after.py run --shard $k/4 --out $A/pick > $A/pick/log$k.txt 2>&1 &
done
timeout 3800 ${=G} $PY -B exam/alone.py --out $A/alone.jsonl --deadline-s 3600 > $A/alone.log 2>&1; echo "$(date +%T) alone code $?"
python3 exam/score_after.py $A/alone.jsonl $A/alone_score.json
timeout 4300 ${=G} $PY -B exam/other.py machine --out $A/other --flow print-writes --stock 4 --deadline-s 4050 > $A/other.log 2>&1; echo "$(date +%T) other code $?"
timeout 3300 python3 tools/memguard.py --limit-gib 16 --log exam/mem.log -- $PY -B exam/other.py host --out $A/other_host.jsonl --deadline-s 3150 > $A/other_host.log 2>&1; echo "$(date +%T) host code $?"
python3 exam/score_d1m.py --n 300 --rows $A/other --host $A/other_host.jsonl --out $A/other_score.json > $A/other_score.log; cut -c1-1000 $A/other_score.log
python3 -c "import json,sys;d=json.load(open('$A/other_score.json'));sys.exit(0 if d['stock']['passed'] and not d['stock']['mismatches'] else 1)" || { echo STOP stock sample; exit 1 }
timeout 4800 ${=G} $PY -B exam/other.py machine --out $A/other_r --flow read-writes --stock 0 --deadline-s 4500 > $A/other_r.log 2>&1; echo "$(date +%T) reply code $?"
python3 exam/score_reply.py --rows $A/other_r --out $A/other_r_score.json --md $A/other_r_replies.md | cut -c1-600
timeout 400 ${=G} $PY -B exam/other.py stops --out $A/stops --deadline-s 300 > $A/stops.log 2>&1; echo "$(date +%T) stops code $?"
python3 exam/score_reply.py --rows $A/stops --out $A/stops_score.json --md $A/stops_replies.md | cut -c1-400
wait
python3 exam/pick_after.py choose --dir $A/pick --budget 338000 --out $A/plan.json | tee $A/choose.log | cut -c1-500
timeout 11000 ${=G} $PY -B t8/fw/tokrun.py stock_trace.py --plan $PWD/$A/plan.json --outdir $PWD/$A/window --hours 3 > $A/window.log 2>&1; echo "$(date +%T) window code $?"
timeout 900 python3 tools/memguard.py --limit-gib 12 --log exam/mem.log -- $PY -B t8/fw/tokrun.py check_trace.py --trace $PWD/$A/window --plan $PWD/$A/plan.json --out $PWD/$A/window_check.json > $A/window_check.log 2>&1; echo "$(date +%T) check code $?"
timeout 900 python3 tools/memguard.py --limit-gib 12 --log exam/mem.log -- $PY -B t8/fw/tokrun.py check_trace.py --trace $PWD/$A/window --plan $PWD/$A/plan.json --flip-trace seed:0:8 --out $PWD/$A/window_flip.json > $A/window_flip.log 2>&1; echo "$(date +%T) flip code $?"
timeout 300 $PY -B t8/fw/tokrun.py ../t8/fw/cov.py trace --firmware writes --trace $A/window --plan $A/plan.json --out t8/fw/results/cov/after_window > $A/window_cov.log 2>&1; echo "$(date +%T) cov code $?"
echo after finished
