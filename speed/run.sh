#!/bin/zsh
# run.sh LIMIT_S LIMIT_GIB script args...: the speed/ environment, memguard, timeout. One process at a time.
# While the file HOLD exists, scripts that use the GPU don't start (lead's instruction, 2 Nov: wait for the normal-token and clean reading tests).
LIM=$1; GIB=$2; shift 2
HERE=${0:A:h}
case "$1" in
  fastrun.py|slowrun.py|s16_stockbatch.py|serve.py|kernels.py)
    if [ -e "$HERE/HOLD" ]; then echo "HELD: $1 not started; $(cat "$HERE/HOLD")" | tee -a "$HERE/mem.log"; exit 75; fi;;
esac
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 PYTHONDONTWRITEBYTECODE=1
PY=<qwenputer>/experimental/riscv/.venv/bin/python
exec timeout $LIM python3 ../tools/memguard.py --limit-gib $GIB --min-free-pct 25 --log mem.log -- $PY "$@"
