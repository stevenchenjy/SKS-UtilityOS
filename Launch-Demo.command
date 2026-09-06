#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "First run: use bash scripts/setup.sh after reviewing the source and dependency list."
  read -r -p "Press Enter to close."
  exit 1
fi
.venv/bin/python run.py demo --open "$@"
