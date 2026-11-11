#!/bin/bash
# The M3 sample on the merged checkpoint with compacted chip layers, one process per graph, each bounded and guarded.
cd "<repo>/vendor/qwenputer-riscv"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.3 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.25 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
run() { timeout 5400 python3 ../../tools/memguard.py --limit-gib 32 --log ../../rvc/mem.log -- $PY ../../rvc/drive.py --compact --graph "$1" --transcript "../../host/out/dev2/$2/sdpa.jsonl" --out "../../rvc/results/m3_compact/$2.jsonl" --only "$3" --question-limit-s 2400; }
run tiny tiny 0,1,2,4,5,6,11
run random/r001 r001 0,8,17,23,25,28,29,40,44,46
run cities/c024 c024 100,201
