#!/usr/bin/env bash
# Run a command (pytest or tox) inside a local virtualenv.
# Bootstraps .venv (with the test + dev extras) on first run, then reuses it.
#
# Usage: ./run.sh <pytest|tox> [args...]
set -euo pipefail

cd "$(dirname "$0")"

VENV=".venv"
PYTHON="${PYTHON:-python3}"

cmd="${1:-}"
case "$cmd" in
	pytest | tox) shift ;;
	*)
		echo "Usage: $0 <pytest|tox> [args...]" >&2
		exit 2
		;;
esac

if [[ ! -x "$VENV/bin/python" ]]; then
	echo ">> Creating virtualenv in $VENV"
	"$PYTHON" -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo ">> Installing package with test + dev extras"
python -m pip install --upgrade pip >/dev/null
python -m pip install -e '.[test,dev]'

echo ">> Running $cmd"
exec "$cmd" "$@"
