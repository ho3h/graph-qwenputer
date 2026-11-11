#!/bin/zsh
# exam/AFTER.md round 18, the one revision, 10 Nov: the map arm (M with the list instruction, or P with the plain question), then arm A,
# at 8,192 new tokens with the decoding named on the command line. One GPU process at a time, under memguard at 32 GiB. Nothing else is in this queue.
# Launch from the X2.10 folder as: nohup zsh exam/queue28.sh precise P > exam/results/after/queue28.log 2>&1 &     (exam/stop_q28.sh matches that form)
cd "<repo>"
X=$PWD
DEC=$1
MAP=$2
[[ $DEC == (greedy|general|precise) && $MAP == (M|P) ]] || { echo "usage: queue28.sh greedy|general|precise M|P"; exit 2 }
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
G=(python3 "$X/tools/memguard.py" --limit-gib 32 --log "$X/exam/mem.log" --)
A=exam/results/after
caffeinate -is -w $$ &          # holds an open, plugged-in Mac awake. A closed lid on battery still sleeps, as on the night of 10 Nov.
pgrep -f "lineage.designed.distill train" >/dev/null && { echo "$(date +%T) another project is training: nothing started"; exit 1 }
pgrep -f "exam/think.py" >/dev/null && { echo "$(date +%T) another exam/think.py is running: nothing started"; exit 1 }
pmset -g batt | head -1 | grep -q "AC Power" || { echo "$(date +%T) the Mac is on battery: nothing started"; exit 1 }
[ -z "$(ls $A/think2 2>/dev/null)" ] || { echo "$(date +%T) $A/think2 is not empty: nothing started"; exit 1 }
echo "$(date +%T) queue28 starts, decode $DEC, map arm $MAP. $(pmset -g batt | head -1). The busiest processes now:"; ps -axo pcpu,rss,comm | sort -nr | head -5
mkdir -p $A/think2
# One arm: a fresh process every 25 questions, restarted after a crash at most 3 times, inside one deadline.
# The hard stop is the deadline plus 700 s, so that a question started just inside the deadline can reach 8,192 tokens at 12 tokens a second.
arm() {
  local a=$1 dl=$2 t0=$SECONDS fails=0 c left
  while (( SECONDS - t0 < dl - 60 )); do
    left=$(( dl - (SECONDS - t0) ))
    timeout $(( left + 700 )) "${G[@]}" $PY -B exam/think.py --arm $a --decode $DEC --cap 8192 --out $X/$A/think2/$a.jsonl --chunk 25 --deadline-s $left >> $A/think2/$a.log 2>&1
    c=$?
    tail -3 $A/think2/$a.log | grep -q "arm finished" && break
    (( c == 3 )) && { echo "$(date +%T) think $a reached its deadline"; break; }
    (( c == 0 )) || { fails=$((fails+1)); echo "$(date +%T) think $a code $c, failure $fails"; (( fails >= 3 )) && break; }
  done
  echo "$(date +%T) think $a done, $(wc -l < $A/think2/$a.jsonl 2>/dev/null || echo 0) rows. Last question started: $(grep '^start ' $A/think2/$a.log | tail -1)"
}
arm $MAP 8500
arm A 4100
python3 exam/score_think.py $A/think2 > $A/think2/score.log 2>&1; echo "$(date +%T) think2 scored, code $?"
echo "$(date +%T) queue28 finished"
