#!/bin/zsh
# exam/AFTER.md, Theo, 5 Nov: resume the GPU exams, most useful first. One GPU process at a time. S2 resumes from its saved rows.
cd "<repo>"
X=$PWD
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1
G=(python3 "$X/tools/memguard.py" --limit-gib 32 --log "$X/exam/mem.log" --)
A=exam/results/after
m=nyc-cf
timeout 6750 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/edit_run_b.py --out $X/$A/s2_$m --draw $X/$A/s2_${m}_draw.json --set conversations --deadline-s 6700 --question-limit-s 300 > $A/s2_${m}_b.log 2>&1
echo "$(date +%T) s2 $m code $?"
for m in nyc-relabelled nyc-cf; do
  ALONE_MAP=$m timeout 900 "${G[@]}" $PY -B exam/alone.py --out $X/$A/s4_$m.jsonl --deadline-s 880 > $A/s4_$m.log 2>&1
  echo "$(date +%T) s4 $m code $?"
done
echo s4 finished
J_REOPEN=1 timeout 4800 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/journeys_run.py --out $X/$A/s5 --draw $X/$A/s5_draw.json --set conversations --verify-first 1 --question-limit-s 4700 --deadline-s 4700 > $A/s5.log 2>&1
echo "$(date +%T) s5 code $?"
echo s5 finished
for m in nyc-relabelled nyc-cf; do
  timeout 3600 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/edit_run_b.py --out $X/$A/s3_$m --draw $X/$A/s3_${m}_draw.json --set both --deadline-s 3550 --question-limit-s 600 > $A/s3_$m.log 2>&1
  echo "$(date +%T) s3 $m code $?"
done
echo s3 finished
timeout 14400 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/edit_run_b.py --out $X/$A/e6w_conv --draw $X/$A/e6_draw.json --set conversations --verify-first 40 --deadline-s 14300 --question-limit-s 3000 > $A/e6w_conv.log 2>&1
echo "$(date +%T) e6w conversations code $?"
timeout 5100 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/edit_run_b.py --out $X/$A/e6w_plain --draw $X/$A/e6_draw.json --set plain --verify-first 30 --deadline-s 5050 --question-limit-s 3000 > $A/e6w_plain.log 2>&1
echo "$(date +%T) e6w plain code $?"
echo queue25 finished
