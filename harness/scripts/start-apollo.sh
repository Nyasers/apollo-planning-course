#!/bin/bash
# Start Apollo in WSL with a persistent guard holding the interactive container open.
set -uo pipefail

CONTAINER="${APOLLO_CONTAINER_NAME:-apollo_neo_dev_edu}"
GUARD_SCRIPT="${APOLLO_GUARD_SCRIPT:-/home/fqx/apollo-guard.sh}"
GUARD_PID_FILE="${APOLLO_GUARD_PID_FILE:-/home/fqx/apollo-guard.pid}"
GUARD_LOG="${APOLLO_GUARD_LOG:-/home/fqx/apollo-guard.log}"

echo "[1/4] 等待 Docker 就绪..."
for _ in $(seq 1 60); do
  if docker info >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
if ! docker info >/dev/null 2>&1; then
  echo "Docker 未能就绪"
  exit 1
fi

guard_running=false
if [ -f "$GUARD_PID_FILE" ]; then
  guard_pid=$(cat "$GUARD_PID_FILE" 2>/dev/null || true)
  if [ -n "$guard_pid" ] && kill -0 "$guard_pid" 2>/dev/null; then
    guard_running=true
  else
    rm -f "$GUARD_PID_FILE"
  fi
fi

echo "[2/4] 启动 Apollo 守护进程..."
if [ "$guard_running" = false ]; then
  setsid nohup "$GUARD_SCRIPT" >>"$GUARD_LOG" 2>&1 </dev/null &
  for _ in $(seq 1 30); do
    if [ -f "$GUARD_PID_FILE" ] && kill -0 "$(cat "$GUARD_PID_FILE")" 2>/dev/null; then
      break
    fi
    sleep 0.5
  done
fi
if [ ! -f "$GUARD_PID_FILE" ] || ! kill -0 "$(cat "$GUARD_PID_FILE")" 2>/dev/null; then
  echo "Apollo 守护进程启动失败，日志：$GUARD_LOG"
  tail -n 80 "$GUARD_LOG" 2>/dev/null || true
  exit 1
fi

echo "[3/4] 等待容器 $CONTAINER 运行..."
for _ in $(seq 1 60); do
  if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" = "true" ]; then
    break
  fi
  sleep 1
done
if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" != "true" ]; then
  echo "容器未进入 running 状态"
  docker ps -a --format '{{.Names}} {{.Status}}' | head -n 10
  tail -n 120 "$GUARD_LOG" 2>/dev/null || true
  exit 1
fi

echo "[4/4] 启动 DreamView..."
docker exec -u 1000:1000 -e HOME=/home/fqx "$CONTAINER" bash -c '
source /opt/apollo/neo/setup.sh >/dev/null 2>&1
cd /apollo_workspace || exit 1
aem bootstrap start --plus 2>&1 | tail -n 5
'

for _ in $(seq 1 45); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://localhost:8888/ || true)
  if [ "$code" = "200" ]; then
    if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" = "true" ]; then
      echo "DreamView 就绪: http://localhost:8888/"
      echo "容器: $CONTAINER running"
      echo "守护 PID: $(cat "$GUARD_PID_FILE")"
      exit 0
    fi
  fi
  sleep 2
done

echo "DreamView 或容器未保持就绪"
docker ps -a --format '{{.Names}} {{.Status}}' | head -n 10
tail -n 120 "$GUARD_LOG" 2>/dev/null || true
exit 1