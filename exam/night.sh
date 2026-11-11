#!/bin/zsh
# exam/R1.md unattended: the stock window on the frozen build and the CPU exams and proofs finish, then the fast runner's proofs, then the GPU exams. Any stop ends it.
cd "/Users/tedsandtads/computing field/xseries/X2.10"
R=exam/results
exam/go_r1a.sh > $R/go_r1a.log 2>&1 &
wait $!
grep -q "go_r1a finished" $R/go_r1a.log || { echo STOP go_r1a; tail -3 $R/go_r1a.log; exit 1 }
echo "$(date +%T) machine and names passed"
until grep -q "r1 finished" t8/fw/results/r1.log && grep -q "x_nyc finished" $R/x_nyc.log; do /bin/sleep 30; done
echo "$(date +%T) window finished"
t8/fw/p_r1.sh > t8/fw/results/r1/p_r1.log 2>&1
python3 t8/fw/r1_check.py > $R/r1_check.log 2>&1 || { echo STOP proofs; cut -c1-200 $R/r1_check.log; exit 1 }
echo "$(date +%T) proofs passed"
exam/go_r1.sh > $R/go_r1.log 2>&1
tail -4 $R/go_r1.log | cut -c1-500
echo night finished
