#!/bin/bash
cd "<repo>/vendor/qwenputer-riscv"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.3 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.25 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
timeout 3600 python3 ../../tools/memguard.py --limit-gib 32 --log ../../rvc/mem.log -- $PY ../../rvc/chain2.py --out ../../rvc/results/arm_rule --verify c024:1 --no-told --question-handles > ../../rvc/results/arm_rule.log 2>&1
timeout 3600 python3 ../../tools/memguard.py --limit-gib 32 --log ../../rvc/mem.log -- $PY ../../rvc/chain2.py --out ../../rvc/results/arm_told --verify c024:1 --no-rule > ../../rvc/results/arm_told.log 2>&1
