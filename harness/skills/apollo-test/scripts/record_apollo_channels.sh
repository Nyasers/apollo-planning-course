#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  record_apollo_channels.sh <tag> [description] [profile]

Profiles:
  pnc      planning/control/canbus/localization/perception/prediction/guardian/safety
  vehicle  pnc + gnss/imu/lidar key channels
  full     all channels currently published by cyber

Examples:
  record_apollo_channels.sh s_curve "S弯道闭环基线" pnc
  record_apollo_channels.sh real_vehicle "实车闭环数据采集" vehicle
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

TAG="${1:-notag}"
DESC="${2:-}"
PROFILE="${3:-pnc}"
ROOT_DIR="${APOLLO_RECORD_DIR:-/apollo_workspace/data/record/apollo_channels}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${ROOT_DIR}/${TIMESTAMP}_${TAG}"
MANIFEST="${ROOT_DIR}/manifest.csv"
OUT_FILE="${OUT_DIR}/${TIMESTAMP}_${TAG}.record"

mkdir -p "${OUT_DIR}"
mkdir -p "${ROOT_DIR}"

if [[ ! -f "${MANIFEST}" ]]; then
  echo "timestamp,tag,profile,file,description" > "${MANIFEST}"
fi

pnc_channels=(
  /apollo/planning
  /apollo/planning/command
  /apollo/planning/command_status
  /apollo/planning/pad
  /apollo/routing_response
  /apollo/prediction
  /apollo/perception/obstacles
  /apollo/perception/traffic_light
  /apollo/localization/pose
  /apollo/localization/msf_status
  /apollo/canbus/chassis
  /apollo/canbus/chassis_detail
  /apollo/control
  /apollo/control/debug
  /apollo/control/interactive
  /apollo/guardian
  /apollo/safety/status
  /apollo/safety/decision
  /tf
)

vehicle_extra_channels=(
  /apollo/sensor/gnss/best_pose
  /apollo/sensor/gnss/corrected_imu
  /apollo/sensor/gnss/imu
  /apollo/sensor/gnss/ins_stat
  /apollo/sensor/gnss/odometry
  /apollo/sensor/lidar/compensator/PointCloud2
  /apollo/sensor/hesai40/PointCloud2
)

channel_args=()
case "${PROFILE}" in
  pnc)
    for channel in "${pnc_channels[@]}"; do
      channel_args+=("-c" "${channel}")
    done
    ;;
  vehicle)
    for channel in "${pnc_channels[@]}" "${vehicle_extra_channels[@]}"; do
      channel_args+=("-c" "${channel}")
    done
    ;;
  full)
    channel_args=()
    ;;
  *)
    echo "Unknown profile: ${PROFILE}" >&2
    usage >&2
    exit 2
    ;;
esac

echo "${TIMESTAMP},${TAG},${PROFILE},${OUT_FILE},${DESC}" >> "${MANIFEST}"

echo "Recording Apollo channels"
echo "  profile: ${PROFILE}"
echo "  output : ${OUT_FILE}"
echo "  manifest: ${MANIFEST}"
echo "Press Ctrl+C to stop."

if [[ "${PROFILE}" == "full" ]]; then
  cyber_recorder record -o "${OUT_FILE}"
else
  cyber_recorder record -o "${OUT_FILE}" "${channel_args[@]}"
fi
