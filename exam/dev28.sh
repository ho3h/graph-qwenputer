#!/bin/zsh
# exam/AFTER.md round 18, the revision's practice runs (10 Nov). Two practice questions that are in no exam (exam/think.py --dev).
# Order: plain prompt with the precise setting, plain prompt greedy, list prompt with the precise setting (cut at 6,000 tokens, the rule's line).
# A second question runs only if the first finished, because a prompt and a decoding qualify only when both finish.
cd "<repo>"
X=$PWD
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
G=(python3 "$X/tools/memguard.py" --limit-gib 32 --log "$X/exam/mem.log" --)
D=exam/results/after/think2_dev
caffeinate -is -w $$ &
one() {   # arm decode cap
  local f=$X/$D/$1-$2.jsonl n
  for n in 1 2; do
    echo "$(date +%T) practice $1 $2 question $n starts"
    timeout 700 "${G[@]}" $PY -B exam/think.py --arm $1 --dev --decode $2 --limit $n --cap $3 --out $f --deadline-s 650 >> $D/dev.log 2>&1
    echo "$(date +%T) practice $1 $2 question $n code $?"
    python3 -c "
import json,sys
r=[json.loads(l) for l in open('$f')]
x=r[-1]; print('   ', '$1', '$2', x['id'], 'new', x['new_tokens'], 'thought', x['thought_tokens'], 'stopped', x['stopped'], 'tok/s', round(x['new_tokens']/x['seconds'],1))
sys.exit(0 if len(r)==$n and x['stopped'] and x['thought_tokens'] is not None else 1)" || { echo "    $1 $2 does not qualify"; return; }
  done
  echo "    $1 $2 finished both"
}
one P precise 8192
one P greedy 8192
one M precise 6000
echo "$(date +%T) practice done"
