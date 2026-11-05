#!/bin/zsh
H="<repo>/host/out/dev2"
mkdir -p "<repo>/tok/results/t6"
cd "<repo>"
tok/run.sh t6_tiny 2400 tok/drive.py --graph tiny --transcript "$H/tiny/sdpa.jsonl" --question-limit-s 600 --out tok/results/t6/tiny.jsonl
tok/run.sh t6_c024 2400 tok/drive.py --graph cities/c024 --transcript "$H/c024/sdpa.jsonl" --question-limit-s 600 --out tok/results/t6/c024.jsonl
tok/run.sh t6_c025 2400 tok/drive.py --graph cities/c025 --transcript "$H/c025/sdpa.jsonl" --question-limit-s 600 --out tok/results/t6/c025.jsonl
tok/run.sh t6_r001 2400 tok/drive.py --graph random/r001 --transcript "$H/r001/sdpa.jsonl" --question-limit-s 600 --out tok/results/t6/r001.jsonl
