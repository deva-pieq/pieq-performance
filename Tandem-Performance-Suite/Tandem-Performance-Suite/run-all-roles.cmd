@echo off
REM ============================================================================
REM  run-all-roles.cmd
REM  Runs performance tests for all three Orbit roles
REM  (Admin, Airport Manager, Analyst)
REM  Usage:
REM    run-all-roles.cmd                 (default: preprod)
REM    run-all-roles.cmd --prod         (production: orbit.pieq.ai)
REM    run-all-roles.cmd --pre-prod     (preprod:    preprod.orbit.pieq.ai)
REM    run-all-roles.cmd --prod -n 3    (production, 3 iterations per page)
REM ============================================================================
cd /d "%~dp0"

REM --- Parse environment flag ---
set "ENV_FLAG="
set "EXTRA_ARGS="

:parse_args
if "%~1"=="" goto validate_env
if /i "%~1"=="--prod" (
    set "ENV_FLAG=prod"
    shift
    goto parse_args
)
if /i "%~1"=="--pre-prod" (
    set "ENV_FLAG=preprod"
    shift
    goto parse_args
)
set "EXTRA_ARGS=%EXTRA_ARGS% %1"
shift
goto parse_args

:validate_env
if "%ENV_FLAG%"=="" (
    echo No environment flag specified, defaulting to preprod.
    set "ENV_FLAG=preprod"
)

set "TOTAL_FAILED=0"

echo.
echo ============================================================
echo  Environment : %ENV_FLAG%
if "%ENV_FLAG%"=="prod" (
    echo  Base URL    : https://orbit.pieq.ai
) else (
    echo  Base URL    : https://preprod.orbit.pieq.ai
)
echo  Extra args  : %EXTRA_ARGS%
echo ============================================================
echo.

REM --- 1) Admin ---
echo [1/3] Running Admin performance test...
set "PERF_ENV=%ENV_FLAG%"
call sitespeed.io.cmd scripts\dashboard_admin.js --config sitespeed.config.json %EXTRA_ARGS%
if errorlevel 1 (
    echo [FAIL] Admin test failed.
    set /a TOTAL_FAILED+=1
) else (
    echo [PASS] Admin test completed.
)
echo.

REM --- 2) Airport Manager ---
echo [2/3] Running Airport Manager performance test...
set "PERF_ENV=%ENV_FLAG%"
call sitespeed.io.cmd scripts\dashboard_airport_manager.js --config sitespeed.config.json %EXTRA_ARGS%
if errorlevel 1 (
    echo [FAIL] Airport Manager test failed.
    set /a TOTAL_FAILED+=1
) else (
    echo [PASS] Airport Manager test completed.
)
echo.

REM --- 3) Analyst ---
echo [3/3] Running Analyst performance test...
set "PERF_ENV=%ENV_FLAG%"
call sitespeed.io.cmd scripts\dashboard_analyst.js --config sitespeed.config.json %EXTRA_ARGS%
if errorlevel 1 (
    echo [FAIL] Analyst test failed.
    set /a TOTAL_FAILED+=1
) else (
    echo [PASS] Analyst test completed.
)
echo.

REM --- Build custom dashboards ---
echo Building custom dashboards...
python tools\build-custom-dashboard.py
if errorlevel 1 (
    echo [WARN] Custom dashboard build failed.
)
echo.

if not "%SKIP_AI_SUMMARY%"=="1" (
    echo Generating AI performance summary...
    python tools\run-performance.py --skip-command
    if errorlevel 1 (
        echo [WARN] AI summary was not generated. Dashboard metrics are still available.
    ) else (
        echo [PASS] AI summary added to custom-dashboard\index.html
    )
    echo.
)

REM --- Summary ---
echo ============================================================
if %TOTAL_FAILED%==0 (
    echo  All 3 role tests completed successfully.
) else (
    echo  %TOTAL_FAILED% of 3 role test^(s^) failed.
)
echo ============================================================
echo.
echo Custom dashboard ^(latest^): custom-dashboard\index.html

if %TOTAL_FAILED% neq 0 exit /b 1
