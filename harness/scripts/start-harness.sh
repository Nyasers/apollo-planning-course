#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m apollo_claw serve --port "${APOLLO_CLAW_PORT:-8765}"
