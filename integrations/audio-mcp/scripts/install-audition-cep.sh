#!/usr/bin/env bash
set -euo pipefail

readonly extension_name="com.zx.audio-mcp-audition"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly script_dir
integration_root="$(cd "${script_dir}/.." && pwd)"
readonly integration_root
readonly source_extension="${integration_root}/audition-cep"
if [[ -z "${HOME:-}" || "${HOME}" == "/" ]]; then
  echo "A safe HOME directory is required." >&2
  exit 1
fi
readonly user_support="${HOME}/Library/Application Support"
readonly config_dir="${user_support}/audio-mcp"
readonly config_path="${config_dir}/audition.json"
readonly backup_dir="${config_dir}/backups"
readonly extensions_dir="${user_support}/Adobe/CEP/extensions"
readonly extension_path="${extensions_dir}/${extension_name}"
readonly default_media_dir="${HOME}/Music/AudioMCP"
readonly read_root="${default_media_dir}/Read"
readonly write_root="${default_media_dir}/Write"

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--dry-run]" >&2
  exit 2
fi

if [[ "${dry_run}" == true ]]; then
  echo "Create owner-only directory: ${config_dir}"
  echo "Create owner-only directory: ${extensions_dir}"
  echo "Create default media roots: ${read_root} and ${write_root}"
  echo "Create config if absent: ${config_path}"
  echo "Back up existing extension if present: ${backup_dir}/${extension_name}.backup-YYYYMMDD-HHMMSS"
  echo "Copy extension: ${source_extension} -> ${extension_path}"
  exit 0
fi

if [[ ! -d "${source_extension}" ]]; then
  echo "Audition CEP source is missing: ${source_extension}" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to generate the local configuration." >&2
  exit 1
fi

umask 077
mkdir -p "${config_dir}" "${extensions_dir}"
chmod 0700 "${config_dir}" "${extensions_dir}"

if [[ -L "${config_path}" || ( -e "${config_path}" && ! -f "${config_path}" ) ]]; then
  echo "Existing Audition config must be a regular file: ${config_path}" >&2
  exit 1
elif [[ ! -e "${config_path}" ]]; then
  mkdir -p "${read_root}" "${write_root}"
  chmod 0700 "${read_root}" "${write_root}"
  python3 - "${config_path}" "${read_root}" "${write_root}" <<'PY'
import json
import os
import secrets
import sys

config_path, read_root, write_root = sys.argv[1:]
payload = {
    "secret": secrets.token_hex(32),
    "read_roots": [read_root],
    "write_roots": [write_root],
    "host": "127.0.0.1",
    "port": 18765,
    "favorites": [],
    "export_presets": {"wav": ".wav"},
}
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
descriptor = os.open(config_path, flags, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
  chmod 0600 "${config_path}"
  echo "Created owner-only config: ${config_path}"
else
  echo "Preserved existing config: ${config_path}"
fi

if [[ -e "${extension_path}" || -L "${extension_path}" ]]; then
  readonly timestamp="$(date '+%Y%m%d-%H%M%S')"
  readonly backup_path="${backup_dir}/${extension_name}.backup-${timestamp}"
  if [[ -e "${backup_path}" || -L "${backup_path}" ]]; then
    echo "Backup already exists; wait one second and retry: ${backup_path}" >&2
    exit 1
  fi
  mkdir -p "${backup_dir}"
  chmod 0700 "${backup_dir}"
  mv "${extension_path}" "${backup_path}"
  echo "Backed up existing extension: ${backup_path}"
fi

mkdir -p "${extension_path}"
cp -R "${source_extension}/." "${extension_path}/"
echo "Installed Audition CEP extension: ${extension_path}"
