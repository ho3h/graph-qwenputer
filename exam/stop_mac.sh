#!/bin/zsh
# Theo, 5 Nov: clear the Mac by 10:44 ET.
until [ $(date +%H%M) -ge 1044 ]; do /bin/sleep 15; done
pkill -f "zsh exam/queue26.sh"; pkill -f "edit_run_b.py"; pkill -f "exam/alone.py"; pkill -f "X2.10/tools/memguard.py"
echo "$(date +%T) the Mac cleared"
