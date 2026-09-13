#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$#" -gt 1 ]; then
  echo "Usage: bash scripts/setup.sh [local-wheelhouse]"
  exit 1
fi
install_options=()
if [ "$#" -eq 1 ]; then
  install_options+=(--directory "$1")
fi
python3 scripts/dependency_artifacts.py install "${install_options[@]}"
printf '\nSetup complete. Start a synthetic demo with: .venv/bin/python run.py demo --open\n'
printf 'Staff setup and local directory selection: .venv/bin/python run.py staff --choose-data-dir --open\n'
