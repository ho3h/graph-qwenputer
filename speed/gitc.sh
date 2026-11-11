#!/bin/zsh
# gitc.sh MESSAGE paths...: commit speed/ paths only, waiting for another agent's index lock. Fails loudly.
cd "<project>" || exit 1
MSG=$1; shift
for i in {1..60}; do
  [ -e .git/index.lock ] || { git add -- "$@" && git commit -q -m "$MSG

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- "$@" && { git log --oneline -1; exit 0; }; }
  sleep 2
done
echo "COMMIT FAILED"; exit 1
