#!/bin/bash
# Usage: record_pnc_sim.sh <tag> [description]
# Example: record_pnc_sim.sh nudge_retry "调小buffer后重试窄路场景"
#          record_pnc_sim.sh baseline "修改前的基线数据"

RECORD_DIR="/apollo_workspace/data/record/pnc_sim"
MANIFEST="${RECORD_DIR}/manifest.csv"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TAG="${1:-notag}"
DESC="${2:-}"
RECORD_FILE="${RECORD_DIR}/${TIMESTAMP}_${TAG}"

mkdir -p "${RECORD_DIR}"

# 初始化 manifest
if [ ! -f "${MANIFEST}" ]; then
  echo "timestamp,tag,file,description" > "${MANIFEST}"
fi

CHANNELS=(
  /apollo/planning
  /apollo/planning/pad
  /apollo/routing_response
  /apollo/prediction
  /apollo/perception/obstacles
  /apollo/perception/traffic_light
  /apollo/localization/pose
  /apollo/canbus/chassis
  /apollo/control
  /apollo/external_command/lane_follow
)

CHANNEL_ARGS=""
for ch in "${CHANNELS[@]}"; do
  CHANNEL_ARGS="${CHANNEL_ARGS} -c ${ch}"
done

echo "Recording: ${RECORD_FILE}"
echo "Tag: ${TAG}"
echo "Desc: ${DESC}"
echo "Press Ctrl+C to stop."

# 记录到 manifest
echo "${TIMESTAMP},${TAG},${RECORD_FILE},${DESC}" >> "${MANIFEST}"

cyber_recorder record -o "${RECORD_FILE}" ${CHANNEL_ARGS}
