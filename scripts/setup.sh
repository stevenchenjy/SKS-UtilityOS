#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11 or newer is required"'
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
# Optional offline wheelhouse: bash scripts/setup.sh /approved/local/wheelhouse
install_options=(--only-binary=:all: --disable-pip-version-check)
if [ "$#" -gt 1 ]; then
  echo "Usage: bash scripts/setup.sh [local-wheelhouse]"
  exit 1
fi
if [ "$#" -eq 1 ]; then
  install_options+=(--no-index --find-links "$1")
fi
.venv/bin/python -m pip install "${install_options[@]}" -r requirements-bootstrap.txt
.venv/bin/python -m pip install "${install_options[@]}" -c constraints-tested.txt -r requirements.txt
printf '\nSetup complete. Start a synthetic demo with: .venv/bin/python run.py demo --open\n'
