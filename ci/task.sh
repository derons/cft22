cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/solver:$PYTHONPATH"
python3 solver/play.py "${MODE:-test}" "${GAMES:-1}"
