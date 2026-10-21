#!/bin/bash
# Stop Apollo and fully release the guard process group so WSL can idle out.
set -u

CONTAINER="${APOLLO_CONTAINER_NAME:-apollo_neo_dev_edu}"
GUARD_PID_FILE="${APOLLO_GUARD_PID_FILE:-/home/fqx/apollo-guard.pid}"

echo "停止进行中的录制 ..."
docker exec -u 1000:1000 -e HOME=/home/fqx "$CONTAINER" bash -c '
pkill -INT -f "[c]yber_recorder record" 2>/dev/null || true
sleep 1
' 2>/dev/null || true
echo "停止 DreamView ..."
docker exec -u 1000:1000 -e HOME=/home/fqx "$CONTAINER" bash -c '
source /opt/apollo/neo/setup.sh >/dev/null 2>&1
cd /apollo_workspace && aem bootstrap stop 2>&1 | tail -n 3
' 2>/dev/null || true

echo "停止守护进程 ..."
if [ -f "$GUARD_PID_FILE" ]; then
  guard_pid=$(cat "$GUARD_PID_FILE" 2>/dev/null || true)
  if [ -n "$guard_pid" ] && kill -0 "$guard_pid" 2>/dev/null; then
    kill -TERM -- "-$guard_pid" 2>/dev/null || kill -TERM "$guard_pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$guard_pid" 2>/dev/null || break
      sleep 0.2
    done
    kill -KILL -- "-$guard_pid" 2>/dev/null || true
  fi
  rm -f "$GUARD_PID_FILE"
fi
pkill -f '[a]pollo-guard.sh' 2>/dev/null || true

echo "停止容器 ..."
docker stop "$CONTAINER" >/dev/null 2>&1 || true

echo "已停止。WSL 无活动会话后会自动关机，内存随之释放。"