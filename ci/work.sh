#!/usr/bin/env bash
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/solver:$PYTHONPATH"
MODE="$(cat ci/mode.txt 2>/dev/null | cut -d' ' -f1 || echo watch)"
URL="$(cat ci/mode.txt 2>/dev/null | cut -d' ' -f2)"
[ -n "$URL" ] && export INSTANCE="$URL"
echo "mode=$MODE instance=$INSTANCE"
case "$MODE" in
  debug) timeout 900 python3 solver/debug_move.py ;;
  *)
    if [ -n "$INSTANCE" ]; then timeout 600 python3 solver/setup.py "$INSTANCE" || exit 1; fi
    BUDGET=7200 timeout 8000 python3 solver/play.py "${MODE:-play}"
    ;;
esac
echo "exit=$?"
