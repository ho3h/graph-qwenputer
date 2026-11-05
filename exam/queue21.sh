#!/bin/zsh
# exam/AFTER.md tonight: T3, then E6, one GPU process at a time. An empty home folder for T3, as a stranger has.
cd "<repo>"
X=$PWD
PY=<qwenputer>/experimental/riscv/.venv/bin/python
Q="<scratchpad>"
M=$HOME/Models/x210/x210-tok
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
A=exam/results/after; mkdir -p $A/t3
G=(python3 "$X/tools/memguard.py" --limit-gib 32 --log "$X/exam/mem.log" --)
(
  cd "$Q"; export HOME=$(mktemp -d)
  python3 gq.py import examples/packages.csv -o /tmp/t3-packages.graph.json >/dev/null
  python3 gq.py import examples/flights.csv --both flight -o /tmp/t3-flights.graph.json >/dev/null
  timeout 900 "${G[@]}" $PY gq.py ask /tmp/t3-packages.graph.json --whole --model $M --python $PY --examples examples/packages.examples.json --tools neighbours,path,close,add_node,link "What does web depend on?" "How does app reach libc? Show the shortest chain." "The crypto package has been removed. How does auth reach libc now?" "We added a new package, logger, and web now depends on logger." "What does web depend on now?" > "$X/$A/t3/packages.txt" 2>&1; echo "$(date +%T) t3 packages $?"
  timeout 900 "${G[@]}" $PY gq.py ask /tmp/t3-flights.graph.json --whole --model $M --python $PY --examples examples/flights.examples.json --tools cheapest,path,close,reopen "What's the cheapest way from Lisbon to Warsaw?" "Paris airport has closed. What's the cheapest way from Lisbon to Warsaw now?" "Paris airport has reopened. What's the cheapest way from Lisbon to Warsaw now?" > "$X/$A/t3/flights.txt" 2>&1; echo "$(date +%T) t3 flights $?"
)
echo t3 finished
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1
timeout 3600 "${G[@]}" $PY -B t8/fw/tokrun.py ../exam/edit_run_b.py --out $PWD/$A/e6 --draw $PWD/$A/e6_draw.json --set both --deadline-s 3500 --question-limit-s 600 > $A/e6.log 2>&1
echo "$(date +%T) e6 code $?"
echo e6 finished
