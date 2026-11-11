#!/bin/zsh
# Stops the round 18 revision queue and whatever it started. Rows already written stay.
pkill -f "zsh exam/queue28.sh"; pkill -f "exam/think.py"; pkill -f "X2.10/tools/memguard.py"
