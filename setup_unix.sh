#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v python3.10 >/dev/null 2>&1; then
  echo "Python 3.10 is required. Install python3.10 and try again." >&2
  exit 1
fi

python3.10 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python scripts/check_environment.py
./.venv/bin/python scripts/test_model.py

echo ""
echo "Setup complete."
echo "Launch command:"
echo "./.venv/bin/python app/main.py"

