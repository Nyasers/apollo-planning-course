#!/bin/bash
# Keep the Apollo container's interactive entrypoint alive and keep WSL from idling out.
set -u

CONTAINER="${APOLLO_CONTAINER_NAME:-apollo_neo_dev_edu}"
PID_FILE="${APOLLO_GUARD_PID_FILE:-/home/fqx/apollo-guard.pid}"

echo $$ >"$PID_FILE"
cleanup() {
  rm -f "$PID_FILE"
}
trap cleanup EXIT INT TERM

echo "[guard] pid=$$ starting container=$CONTAINER $(date -Is)"
until docker info >/dev/null 2>&1; do
  sleep 2
done

while true; do
  echo "[guard] docker start -ai $CONTAINER $(date -Is)"
  tail -f /dev/null | docker start -ai "$CONTAINER"
  status=${PIPESTATUS[1]:-0}
  echo "[guard] container attached process exited status=$status $(date -Is)"
  sleep 2
done