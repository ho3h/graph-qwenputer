#!/bin/zsh
# exam/AFTER.md S2, S3, S4, one GPU process at a time, after queue21's E6.
cd "<repo>"
until grep -q "e6 finished" exam/results/queue21.log 2>/dev/null; do /bin/sleep 20; done
X=$PWD
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1
G=(python3 "$X/tools/memguard.py" --limit-gib 32 --log "$X/exam/mem.log" --)
A=exam/results/after
T="<scratchpad>"
(
  export HOME=$(mktemp -d)
  python3 exam/t2_run.py "$T/repo" <home>/Models/x210/x210-tok $PY > $A/t2.log 2>&1
  echo "$(date +%T) t2 code $?"
)
echo t2 finished
(
  cd "$T/fresh"; export HOME=$(mktemp -d)
  .venv/bin/python gq.py ask packages.graph.json --model model --examples examples/packages.examples.json --tools neighbours,path,close,add_node,link "What does web depend on?" "How does app reach libc? Show the shortest chain." "The crypto package has been removed. How does auth reach libc now?" "We added a new package, logger, and web now depends on logger." "What does web depend on now?" > "$X/$A/f1/ask.txt" 2>&1
  echo "$(date +%T) f1 ask $?"
)
for m in nyc-relabelled nyc-cf; do
  timeout 6750 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/edit_run_b.py --out $X/$A/s2_$m --draw $X/$A/s2_${m}_draw.json --set conversations --deadline-s 6700 --question-limit-s 300 > $A/s2_$m.log 2>&1
  echo "$(date +%T) s2 $m code $?"
done
echo s2 finished
for m in nyc-relabelled nyc-cf; do
  timeout 3600 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/edit_run_b.py --out $X/$A/s3_$m --draw $X/$A/s3_${m}_draw.json --set both --deadline-s 3550 --question-limit-s 600 > $A/s3_$m.log 2>&1
  echo "$(date +%T) s3 $m code $?"
done
echo s3 finished
for m in nyc-relabelled nyc-cf; do
  ALONE_MAP=$m timeout 900 "${G[@]}" $PY -B exam/alone.py --out $X/$A/s4_$m.jsonl --deadline-s 880 > $A/s4_$m.log 2>&1
  echo "$(date +%T) s4 $m code $?"
done
echo s4 finished
