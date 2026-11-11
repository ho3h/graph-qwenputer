#!/bin/zsh
# Stops round 18's queue and whatever it is running, at once. Saved rows stay. zsh exam/stop_q27.sh
pkill -f "zsh exam/queue27.sh"; pkill -f "exam/think.py"; pkill -f "edit_run_b.py"; pkill -f "journeys_run.py"; pkill -f "X2.10/tools/memguard.py"
echo "$(date +%T) queue27 stopped"
