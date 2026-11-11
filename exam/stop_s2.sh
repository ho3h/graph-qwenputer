#!/bin/zsh
until [ $(date +%H%M) -ge 1032 ]; do /bin/sleep 10; done
pkill -f "edit_run_b.py --out .*s2_nyc-cf" && echo "$(date +%T) s2 nyc-cf stopped at 10:32, rows kept"
pkill -f "timeout 6750" ; true
