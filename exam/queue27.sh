#!/bin/zsh
# exam/AFTER.md round 18. Theo, 9 Nov: the GPU is mine from about 2am. Starts 02:15 ET on 10 Nov. One GPU process at a time. Everything ends by 08:00 ET.
# Launch from the X2.10 folder as: nohup zsh exam/queue27.sh > exam/results/after/queue27.log 2>&1 &     (exam/stop_q27.sh matches that form)
cd "<repo>"
X=$PWD
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1
G=(python3 "$X/tools/memguard.py" --limit-gib 32 --log "$X/exam/mem.log" --)
A=exam/results/after
caffeinate -is -w $$ &          # the Mac stays awake until this script ends
now() { date +%Y%m%d%H%M }
until [ "$(now)" -ge 202611100215 ]; do /bin/sleep 30; done
[ "$(now)" -ge 202611100800 ] && { echo "started too late: nothing run"; exit 1; }
n=0
while pgrep -f "lineage.designed.distill train" >/dev/null; do
  n=$((n+1)); [ $n -gt 60 ] && { echo "$(date +%T) another project still training after an hour: nothing started"; exit 1; }
  /bin/sleep 60
done
echo "$(date +%T) queue27 starts. The busiest processes now:"; ps -axo pcpu,rss,comm | sort -nr | head -5
mkdir -p $A/think
# One arm: a fresh process every 25 questions, restarted after a crash at most 3 times, inside one deadline.
arm() {
  local a=$1 dl=$2 guard=$3 t0=$SECONDS fails=0 c left
  [ "$(now)" -le $guard ] || { echo "$(date +%T) think $a not started, out of time"; return; }
  while (( SECONDS - t0 < dl - 60 )); do
    left=$(( dl - (SECONDS - t0) ))
    timeout $(( left + 100 )) "${G[@]}" $PY -B exam/think.py --arm $a --out $X/$A/think/$a.jsonl --chunk 25 --deadline-s $left >> $A/think/$a.log 2>&1
    c=$?
    tail -3 $A/think/$a.log | grep -q "arm finished" && break
    (( c == 3 )) && { echo "$(date +%T) think $a reached its deadline"; break; }
    (( c == 0 )) || { fails=$((fails+1)); echo "$(date +%T) think $a code $c, failure $fails"; (( fails >= 3 )) && break; }
  done
  echo "$(date +%T) think $a done, $(wc -l < $A/think/$a.jsonl 2>/dev/null || echo 0) rows"
}
# Each step needs its whole hard stop before 08:00 ET.
arm M 7500 202611100552
arm A 4500 202611100642
python3 exam/score_think.py $A/think > $A/think/score.log 2>&1; echo "$(date +%T) think scored, code $?"
m=nyc-cf
if [ "$(now)" -le 202611100657 ]; then
  timeout 3700 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/edit_run_b.py --out $X/$A/s2_$m --draw $X/$A/s2_${m}_draw.json --set conversations --deadline-s 3600 --question-limit-s 300 > $A/s2_${m}_c.log 2>&1
  echo "$(date +%T) s2 $m code $?"
else echo "$(date +%T) s2 $m not started, out of time"; fi
if [ "$(now)" -le 202611100639 ]; then
  J_REOPEN=1 timeout 4800 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/journeys_run.py --out $X/$A/s5 --draw $X/$A/s5_draw.json --set conversations --verify-first 1 --question-limit-s 4700 --deadline-s 4700 > $A/s5.log 2>&1
  echo "$(date +%T) s5 code $?"
else echo "$(date +%T) s5 not started, out of time"; fi
echo "$(date +%T) queue27 finished"
