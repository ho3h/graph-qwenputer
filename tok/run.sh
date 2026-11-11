#!/bin/zsh
# One stock-weights process at a time, memory read first. run.sh NAME TIMEOUT args...
cd "<repo>"
name=$1; lim=$2; shift 2
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
n=0
while true; do
  level=$(sysctl -n kern.memorystatus_level)
  [ "$level" -ge 30 ] && break
  n=$((n+1)); [ $n -gt 40 ] && { echo "$(date '+%F %T') $name not started, free ${level}%" >> tok/results/starts.log; exit 4; }
  python3 -c "import time;time.sleep(30)"
done
echo "$(date '+%F %T') start $name, system free ${level}%, timeout ${lim}s" >> tok/results/starts.log
timeout $lim python3 tools/memguard.py --limit-gib 32 --log tok/mem.log -- $PY -B "$@" > tok/results/$name.log 2>&1
code=$?
echo "$(date '+%F %T') end $name code $code" >> tok/results/starts.log
exit $code
