#!/bin/zsh
# exam/AFTER.md M, N on the GPU, alongside what's running.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2 T8_NOUN=on T8_R1=1 T8_WRITES=1
R=exam/results/after; G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
python3 exam/draw_gaslight.py
timeout 2100 ${=G} $PY -B t8/fw/tokrun.py ../exam/map_out.py > $R/map_out.log 2>&1 &
timeout 2500 ${=G} $PY -B t8/fw/tokrun.py ../exam/edit_run.py --out $PWD/$R/gaslight --draw $PWD/$R/gaslight_draw.json --set conversations --verify-first 2 --deadline-s 2300 > $R/gaslight.log 2>&1 &
timeout 1100 python3 tools/memguard.py --limit-gib 16 --log exam/mem.log -- $PY -B exam/gaslight_map.py $R/gaslight_map.jsonl 900 > $R/gaslight_map.log 2>&1 &
wait
python3 exam/edit_score.py $R/gaslight | cut -c1-300
echo mn finished
