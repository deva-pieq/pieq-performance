#!/usr/bin/env bash
# Run sitespeed, then always build the custom dashboard from the latest result.
set -euo pipefail
cd "$(dirname "$0")"

if [ "$#" -lt 1 ]; then
  echo "Usage: ./run-sitespeed.sh <script.js> [extra sitespeed flags]"
  echo "Example: ./run-sitespeed.sh dashboard_op_prod1_js.js -n 1"
  exit 1
fi

SCRIPT="$1"
shift

sitespeed.io "$SCRIPT" --config sitespeed.config.json "$@"
python3 build-custom-dashboard.py

echo
echo "Custom dashboard (latest): custom-dashboard/index.html"
