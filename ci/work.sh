#!/usr/bin/env bash
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/solver:$PYTHONPATH"
MODE="$(cat ci/mode.txt 2>/dev/null || echo watch)"
echo "mode=$MODE"
case "$MODE" in
  debug) timeout ${BUDGET_S:-600} python3 solver/debug_move.py ;;
  *) timeout ${BUDGET_S:-1500} python3 solver/play.py "$MODE" ;;
esac
echo "exit=$?"
