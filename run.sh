#!/usr/bin/env bash
# Ovidius NIDS launcher for Linux/macOS.
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 run.py
elif command -v python >/dev/null 2>&1; then
  exec python run.py
else
  echo
  echo "[!] Python was not found on PATH."
  echo "    Install Python 3.10+ from https://www.python.org/downloads/"
  exit 1
fi
