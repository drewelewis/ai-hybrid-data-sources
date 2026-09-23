#!/usr/bin/env sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if ! command -v pwsh >/dev/null 2>&1; then
  echo "PowerShell 7 is required to run the fresh regional preflight and placement picker." >&2
  echo "Install pwsh, then run azd up again. Provisioning has not started." >&2
  exit 1
fi

exec pwsh -NoProfile -File "$script_dir/select-deployment-configuration.ps1"
