#!/bin/zsh
H="<repo>/host/out/dev2"
mkdir -p "<repo>/tok/results/t5b_stock"
cd "<repo>"
tok/run.sh t5b_tiny 625 tok/drive.py --graph tiny --transcript "$H/tiny/sdpa.jsonl" --only 0 --verify all --question-limit-s 600 --out tok/results/t5b_stock/tiny.jsonl
tok/run.sh t5b_c024 625 tok/drive.py --graph cities/c024 --transcript "$H/c024/sdpa.jsonl" --only 0 --verify all --question-limit-s 600 --out tok/results/t5b_stock/c024.jsonl
tok/run.sh t5b_r001 1800 tok/drive.py --graph random/r001 --transcript "$H/r001/sdpa.jsonl" --only 0,17,25 --verify all --question-limit-s 1200 --out tok/results/t5b_stock/r001.jsonl
