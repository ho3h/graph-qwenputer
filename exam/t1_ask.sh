#!/bin/zsh
# exam/AFTER.md T1, through the toolkit a stranger would use, once r6e has the GPU no more.
cd "<repo>"
until grep -q "r6 walk finished" exam/results/queue20.log 2>/dev/null; do /bin/sleep 30; done
R=exam/results/after/t1; mkdir -p $R
PY=<qwenputer>/experimental/riscv/.venv/bin/python
Q="<scratchpad>"
M=$HOME/Models/x210/x210-tok
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.25 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.2
export HOME=$(mktemp -d)                                           # the way a stranger runs it (exam/AFTER.md, the toolkit review)
G="python3 tools/memguard.py --limit-gib 32 --log exam/mem.log --"
cd "$Q"
python3 gq.py import examples/packages.csv -o /tmp/t1-packages.graph.json >/dev/null
python3 gq.py import examples/flights.csv --both flight -o /tmp/t1-flights.graph.json >/dev/null
O="<repo>/$R"
timeout 900 $PY gq.py ask /tmp/t1-packages.graph.json --model $M --python $PY --examples examples/packages.examples.json --tools neighbours,path,close,add_node,link "What does web depend on?" "How does app reach libc? Show the shortest chain." "The crypto package has been removed. How does auth reach libc now?" "We added a new package, logger, and web now depends on logger." "What does web depend on now?" > "$O/packages.txt" 2>&1; echo "$(date +%T) packages $?"
timeout 600 $PY gq.py ask /tmp/t1-flights.graph.json --model $M --python $PY --examples examples/flights.examples.json --tools cheapest,path,close,reopen "What's the cheapest way from Lisbon to Warsaw?" "Paris airport has closed. What's the cheapest way from Lisbon to Warsaw now?" "Paris airport has reopened. What's the cheapest way from Lisbon to Warsaw now?" > "$O/flights.txt" 2>&1; echo "$(date +%T) flights $?"
timeout 450 $PY gq.py ask examples/team.graph.json --model $M --python $PY "What's the route with the fewest stops from Dana to Kofi?" "Who does Dana report to?" > "$O/team.txt" 2>&1; echo "$(date +%T) team $?"
timeout 450 $PY gq.py ask nyc --model $M --python $PY "Flooding has shut Saratoga Av. What's the route with the fewest stops from Bowling Green to Pennsylvania Av?" > "$O/nyc.txt" 2>&1; echo "$(date +%T) nyc $?"
echo t1 finished
