#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ -x "$HOME/emg-lab-venv/bin/python" ]; then
  PY="$HOME/emg-lab-venv/bin/python"
elif [ -x "$PWD/.venv/bin/python" ]; then
  PY="$PWD/.venv/bin/python"
else
  python3 -m venv .venv
  PY="$PWD/.venv/bin/python"
fi
if ! "$PY" -c 'import serial, numpy, scipy' >/dev/null 2>&1; then
  "$PY" -m pip install -r requirements.txt
fi
exec "$PY" server.py "$@"
