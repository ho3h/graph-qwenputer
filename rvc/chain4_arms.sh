#!/bin/bash
cd "<repo>/vendor/qwenputer-riscv"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.3 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.25 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
run() { timeout "$2" python3 ../../tools/memguard.py --limit-gib 32 --log ../../rvc/mem.log -- $PY ../../rvc/chain4.py --arm "$1" --questions wrong27 --out "../../rvc/results/chain4/$1" $3 > "../../rvc/results/chain4_$1.log" 2>&1; }
run prefill 3400
run note 3400
run both 4300 "--stock cities/c006:192"
run both_q 3400
