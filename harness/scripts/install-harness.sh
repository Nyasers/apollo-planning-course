#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install --user -e .
mkdir -p "$HOME/.apollo-claw"
if [ ! -f "$HOME/.apollo-claw/.env" ]; then
  cp .env.example "$HOME/.apollo-claw/.env"
  echo "created $HOME/.apollo-claw/.env"
fi
echo "Apollo Claw Harness installed"
