#!/usr/bin/env bash
# ============================================================================
#  run-all-roles.sh
#  Runs performance tests for all three Orbit roles
#  (Admin, Airport Manager, Analyst)
#  Usage:
#    ./run-all-roles.sh                 (default: preprod)
#    ./run-all-roles.sh --prod         (production: orbit.pieq.ai)
#    ./run-all-roles.sh --pre-prod     (preprod:    preprod.orbit.pieq.ai)
#    ./run-all-roles.sh --prod -n 3    (production, 3 iterations per page)
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")"

ENV_FLAG=""
EXTRA_ARGS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prod)
      ENV_FLAG="prod"
      shift
      ;;
    --pre-prod)
      ENV_FLAG="preprod"
      shift
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [ -z "$ENV_FLAG" ]; then
  echo "No environment flag specified, defaulting to preprod."
  ENV_FLAG="preprod"
fi

TOTAL_FAILED=0

if [ "$ENV_FLAG" = "prod" ]; then
  BASE_URL="https://orbit.pieq.ai"
else
  BASE_URL="https://preprod.orbit.pieq.ai"
fi

echo
echo "============================================================"
echo " Environment : $ENV_FLAG"
echo " Base URL    : $BASE_URL"
echo " Extra args  : ${EXTRA_ARGS[*]:-}"
echo "============================================================"
echo

export PERF_ENV="$ENV_FLAG"

echo "[1/3] Running Admin performance test..."
if sitespeed.io scripts/dashboard_admin.js --config sitespeed.config.json "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"; then
  echo "[PASS] Admin test completed."
else
  echo "[FAIL] Admin test failed."
  TOTAL_FAILED=$((TOTAL_FAILED + 1))
fi
echo

echo "[2/3] Running Airport Manager performance test..."
if sitespeed.io scripts/dashboard_airport_manager.js --config sitespeed.config.json "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"; then
  echo "[PASS] Airport Manager test completed."
else
  echo "[FAIL] Airport Manager test failed."
  TOTAL_FAILED=$((TOTAL_FAILED + 1))
fi
echo

echo "[3/3] Running Analyst performance test..."
if sitespeed.io scripts/dashboard_analyst.js --config sitespeed.config.json "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"; then
  echo "[PASS] Analyst test completed."
else
  echo "[FAIL] Analyst test failed."
  TOTAL_FAILED=$((TOTAL_FAILED + 1))
fi
echo

echo "Building custom dashboards..."
if python3 tools/build-custom-dashboard.py; then
  :
else
  echo "[WARN] Custom dashboard build failed."
fi
echo

if [ "${SKIP_AI_SUMMARY:-}" != "1" ]; then
  echo "Generating AI performance summary..."
  if python3 tools/run-performance.py --skip-command; then
    echo "[PASS] AI summary added to custom-dashboard/index.html"
  else
    echo "[WARN] AI summary was not generated. Dashboard metrics are still available."
  fi
  echo
fi

echo "============================================================"
if [ "$TOTAL_FAILED" -eq 0 ]; then
  echo " All 3 role tests completed successfully."
else
  echo " $TOTAL_FAILED of 3 role test(s) failed."
fi
echo "============================================================"
echo
echo "Custom dashboard (latest): custom-dashboard/index.html"

if [ "$TOTAL_FAILED" -ne 0 ]; then
  exit 1
fi
