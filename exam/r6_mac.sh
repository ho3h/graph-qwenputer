#!/bin/zsh
# exam/AFTER.md r6a, r6b, r6c: items, then the mini and the Mac's CPU.
cd "<repo>"
PY=<qwenputer>/experimental/riscv/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/vendor/qwenputer-riscv" T8_NOUN=on T8_R1=1 T8_R2=1 T8_R3=1 T8_R4=1 T8_R5=1 T8_R6=1 T8_WRITES=1
B=$PWD/exam/items/nyc_b.graph.json; O=exam/results/o6; mkdir -p $O
M="python3 tools/memguard.py --limit-gib 3 --log exam/mem6.log --"; P="$PY -B t8/fw/tokrun.py"
if [ ! -s exam/items/nyc_b_all.json ]; then
  ITEMS_GRAPH=$B ${=P} ../exam/items_all.py --out $PWD/exam/items/nyc_b_all.json > $O/items.log 2>&1 || { echo items failed; exit 1 }
fi
echo "$(date +%T) items done"
SSHC="ssh -o HostKeyAlias=<mini-ip> <mini-host>"
R=<mini>
rsync -aR -e "ssh -o HostKeyAlias=<mini-ip>" t8/fw/tokrun.py t8/fw/fwb.py t8/fw/gen.py t8/fw/build_r6 exam/run_all.py exam/r6_routes.py exam/items/nyc_b.graph.json exam/items/nyc_b_all.json <mini-host>:$R/ || { echo rsync failed; exit 1 }
rsync -a -e "ssh -o HostKeyAlias=<mini-ip>" exam/r6_mini.sh <mini-host>:$R/go15.sh
${=SSHC} "cd $R && nohup bash go15.sh > results_go15.log 2>&1 &" </dev/null
echo "$(date +%T) mini started"
export RUN_ALL_GRAPH=$B
for w in 1 2 3 4 5 6 7 8; do ${=M} ${=P} ../exam/run_all.py --items exam/items/nyc_b_all.json --out $PWD/exam/results/r6_all_mac --only all3,all4 --limit-s 11000 > $O/a$w.log 2>&1 & done
for k in 0 1 2 3 4 5; do ${=M} ${=P} ../exam/r6_routes.py --shard $k/6 --out $PWD/exam/results/r6_routes --limit-s 3600 > $O/r$k.log 2>&1 & done
wait
echo "$(date +%T) exam and routes done on the Mac"
export R2_D_GRAPH=$B R2_D_SEED=20261104:r6b
for k in 0 1 2 3 4 5 6 7; do ${=M} ${=P} ../exam/r2_directed.py --shard $k/8 --out $PWD/exam/results/r6_directed --limit-s 3000 > $O/d$k.log 2>&1 & done
wait
echo r6 mac finished
