#!/usr/bin/env bash
# Run sitespeed, then always build the custom dashboard from the latest result.
set -euo pipefail
cd "$(dirname "$0")"

if [ "$#" -lt 1 ]; then
  echo "Usage: ./run-sitespeed.sh <script.js> [extra sitespeed flags]"
  echo "Example: ./run-sitespeed.sh scripts/dashboard_admin.js -n 1"
  exit 1
fi

SCRIPT="$1"
shift

sitespeed.io "$SCRIPT" --config sitespeed.config.json "$@"
python3 build-custom-dashboard.py

if [ "${SKIP_AI_SUMMARY:-}" != "1" ]; then
  echo "Generating AI performance summary..."
  if python3 tools/run-performance.py --skip-command; then
    echo "[PASS] AI summary added to custom-dashboard/index.html"
  else
    echo "[WARN] AI summary was not generated. Dashboard metrics are still available."
  fi
  echo
fi

echo
echo "Custom dashboard (latest): custom-dashboard/index.html"
