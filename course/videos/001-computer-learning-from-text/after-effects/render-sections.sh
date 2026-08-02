#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_PATH="${SCRIPT_DIR}/video-001-what-ai-models-actually-do.aep"
readonly MASTER_COMP="S001_MASTER_What_AI_Models_Actually_Do"
readonly AERENDER_BIN="${VIDEO001_AERENDER:-/Applications/Adobe After Effects 2025/aerender}"
readonly TEMP_ROOT="${VIDEO001_TEMP_ROOT:-/private/tmp}"
readonly MIN_FREE_KB="${VIDEO001_MIN_FREE_KB:-4194304}"

readonly -a SECTION_IDS=(00 01 02 03 04 05 06 07)
readonly -a SECTION_NAMES=(
  "Hook"
  "Direct explanation"
  "Technical meaning"
  "Tiny example"
  "Repository walkthrough"
  "Live mini-lab"
  "Common mistake"
  "Recap and exercise"
)
readonly -a START_FRAMES=(0 1350 3600 7200 10800 16200 21600 23400)
readonly -a END_FRAMES=(1349 3599 7199 10799 16199 21599 23399 25199)

probe_frames() {
  ffprobe -v error -select_streams v:0 \
    -show_entries stream=nb_frames -of default=noprint_wrappers=1:nokey=1 "$1"
}

validate_segment() {
  local path="$1"
  local expected_frames="$2"
  local actual_frames

  [[ -s "$path" ]] || return 1
  actual_frames="$(probe_frames "$path")"
  [[ "$actual_frames" == "$expected_frames" ]]
}

require_free_space() {
  local available_kb

  available_kb="$(df -Pk "$TEMP_ROOT" | awk 'NR == 2 {print $4}')"
  if [[ ! "$available_kb" =~ ^[0-9]+$ ]] || ((available_kb < MIN_FREE_KB)); then
    echo "ERROR: insufficient temporary storage; need at least ${MIN_FREE_KB} KiB free in ${TEMP_ROOT}" >&2
    return 1
  fi
}

for index in "${!SECTION_IDS[@]}"; do
  section_id="${SECTION_IDS[$index]}"
  section_name="${SECTION_NAMES[$index]}"
  start_frame="${START_FRAMES[$index]}"
  end_frame="${END_FRAMES[$index]}"
  expected_frames="$((end_frame - start_frame + 1))"

  source_path="${TEMP_ROOT}/video001-seg${section_id}-source.mov"
  hq_path="${TEMP_ROOT}/video001-seg${section_id}-hq.mov"
  h264_path="${TEMP_ROOT}/video001-seg${section_id}-h264.mp4"

  if validate_segment "$hq_path" "$expected_frames" && \
    validate_segment "$h264_path" "$expected_frames"; then
    echo "SECTION ${section_id} already verified: ${section_name}"
    continue
  fi

  require_free_space
  echo "SECTION ${section_id} rendering: ${section_name} (${expected_frames} frames)"
  rm -f "$source_path"
  "$AERENDER_BIN" \
    -project "$PROJECT_PATH" \
    -comp "$MASTER_COMP" \
    -OMtemplate "High Quality" \
    -s "$start_frame" \
    -e "$end_frame" \
    -output "$source_path" \
    -v ERRORS \
    -sound OFF \
    -mfr ON 85

  if ! validate_segment "$source_path" "$expected_frames"; then
    echo "ERROR: source validation failed for section ${section_id}" >&2
    exit 1
  fi

  echo "SECTION ${section_id} encoding ProRes 422 HQ"
  ffmpeg -hide_banner -y -loglevel error \
    -i "$source_path" \
    -map 0:v:0 -an \
    -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le -vendor apl0 \
    -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
    "$hq_path"

  echo "SECTION ${section_id} encoding H.264 review"
  ffmpeg -hide_banner -y -loglevel error \
    -i "$source_path" \
    -map 0:v:0 -an \
    -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
    -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
    -movflags +faststart \
    "$h264_path"

  if ! validate_segment "$hq_path" "$expected_frames" || \
    ! validate_segment "$h264_path" "$expected_frames"; then
    echo "ERROR: delivery encoding validation failed for section ${section_id}" >&2
    exit 1
  fi

  rm -f "$source_path"
  echo "SECTION ${section_id} complete: ${section_name}"
done

echo "All requested sections rendered and verified."
