#!/usr/bin/env bash
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/solver:$PYTHONPATH"
MODE="$(cat ci/mode.txt 2>/dev/null || echo watch)"
echo "mode=$MODE"
timeout ${BUDGET_S:-1500} python3 solver/play.py "$MODE"
echo "exit=$?"
