#!/usr/bin/env bash
set -euo pipefail

readonly package_pin="audacity-mcp==0.1.8"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly script_dir
integration_root="$(cd "${script_dir}/.." && pwd)"
readonly integration_root
readonly venv_path="${integration_root}/.venv-audacity"

dry_run=false
if [[ "${1:-}" == "--dry-run" ]]; then
  dry_run=true
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--dry-run]" >&2
  exit 2
fi

if [[ "${dry_run}" == true ]]; then
  printf 'uv venv --python 3.11 %q\n' "${venv_path}"
  printf 'uv pip install --python %q %q\n' \
    "${venv_path}/bin/python" "${package_pin}"
  printf 'uv pip install --python %q --no-deps --editable %q # audio-mcp-integrations compatibility wrapper\n' \
    "${venv_path}/bin/python" "${integration_root}"
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but was not found." >&2
  exit 1
fi

if [[ ! -x "${venv_path}/bin/python" ]]; then
  uv venv --python 3.11 "${venv_path}"
fi

uv pip install --python "${venv_path}/bin/python" "${package_pin}"
uv pip install \
  --python "${venv_path}/bin/python" \
  --no-deps \
  --editable "${integration_root}"
"${venv_path}/bin/python" -c \
  'from importlib.metadata import version; assert version("audacity-mcp") == "0.1.8"; assert version("audio-mcp-integrations") == "0.1.0"'

if [[ ! -x "${venv_path}/bin/audacity-mcp" ]]; then
  echo "Installation completed without an audacity-mcp executable." >&2
  exit 1
fi
if [[ ! -x "${venv_path}/bin/audio-mcp-audacity" ]]; then
  echo "Installation completed without an audio-mcp-audacity wrapper." >&2
  exit 1
fi

echo "Installed ${package_pin} with compatibility wrapper at ${venv_path}/bin/audio-mcp-audacity"
