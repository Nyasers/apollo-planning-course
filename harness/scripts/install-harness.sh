#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install --user -e .
mkdir -p "$HOME/.apollo-claw"
if [ ! -f "$HOME/.apollo-claw/.env" ]; then
  cp .env.example "$HOME/.apollo-claw/.env"
  echo "created $HOME/.apollo-claw/.env"
fi
# The four skills are external skills, not vendored into this repository.
SKILLS_SOURCE="${APOLLO_SKILLS_SOURCE:-$HOME/.openclaw/skills}"
SKILLS_DEST="${APOLLO_CLAW_SKILLS_DIR:-$HOME/.apollo-claw/skills}"
WORKSPACE_HOST="${APOLLO_WORKSPACE_HOST:-$HOME/application-pnc}"
CONTAINER_STAGE="$WORKSPACE_HOST/.comate/skills"
mkdir -p "$SKILLS_DEST"
if [ -d "$WORKSPACE_HOST" ]; then
  mkdir -p "$CONTAINER_STAGE"
fi
for skill in apollo-env apollo-dev apollo-test apollo-eval; do
  if [ -d "$SKILLS_SOURCE/$skill" ]; then
    mkdir -p "$SKILLS_DEST/$skill"
    cp -a "$SKILLS_SOURCE/$skill/." "$SKILLS_DEST/$skill/"
    echo "installed skill: $skill -> $SKILLS_DEST/$skill"
    if [ -d "$WORKSPACE_HOST" ]; then
      mkdir -p "$CONTAINER_STAGE/$skill"
      cp -a "$SKILLS_SOURCE/$skill/." "$CONTAINER_STAGE/$skill/"
      echo "staged for container: $CONTAINER_STAGE/$skill"
    fi
  else
    echo "warning: skill not found: $SKILLS_SOURCE/$skill" >&2
  fi
done
echo "Apollo Claw Harness installed"
