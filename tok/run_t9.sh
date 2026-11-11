#!/bin/zsh
H="<repo>/host/out/dev2"
mkdir -p "<repo>/tok/results/t9"
cd "<repo>"
python3 - <<'P'
import time
while 'end t5a_stock' not in open('tok/results/starts.log').read().split('start t5a_stock')[-1]:
    time.sleep(20)
P
tok/run.sh t9_c024_lock 900 tok/drive_pieces.py --graph cities/c024 --transcript "$H/c024/sdpa.jsonl" --only 1 --verify all --question-limit-s 800 --out tok/results/t9_lock/c024.jsonl
tok/run.sh t9_c024 1800 tok/drive_pieces.py --graph cities/c024 --transcript "$H/c024/sdpa.jsonl" --question-limit-s 600 --out tok/results/t9/c024.jsonl
tok/run.sh t9_c025 1800 tok/drive_pieces.py --graph cities/c025 --transcript "$H/c025/sdpa.jsonl" --question-limit-s 600 --out tok/results/t9/c025.jsonl
