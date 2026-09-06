#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "School IT must approve setup first. See docs/STAFF_INSTALL_AND_UPDATES.md."
  read -r -p "Press Enter to close."
  exit 1
fi
.venv/bin/python run.py staff --open "$@"
