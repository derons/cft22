#!/usr/bin/env bash
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/solver:$PYTHONPATH"
MODE="$(cat ci/mode.txt 2>/dev/null || echo watch)"
echo "mode=$MODE"
case "$MODE" in
  debug) timeout 900 python3 solver/debug_move.py ;;
  *) BUDGET=7800 timeout 8400 python3 solver/play.py "$MODE" ;;
esac
echo "exit=$?"
