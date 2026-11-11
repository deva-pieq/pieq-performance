@echo off
REM ============================================================================
REM  run-all-roles.cmd
REM  Runs performance tests for all three roles (Ops Manager, Agency Owner, Agent)
REM  Usage:
REM    run-all-roles.cmd                 (default: preprod)
REM    run-all-roles.cmd --prod         (production: icm.pieq.ai)
REM    run-all-roles.cmd --pre-prod     (preprod:    preprod.app.pieq.ai)
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
    echo  Base URL    : https://icm.pieq.ai
) else (
    echo  Base URL    : https://preprod.app.pieq.ai
)
echo  Extra args  : %EXTRA_ARGS%
echo ============================================================
echo.

REM --- 1) Ops Manager ---
echo [1/3] Running Ops Manager performance test...
set "PERF_ENV=%ENV_FLAG%"
call sitespeed.io.cmd scripts\dashboard_op_manager.js --config sitespeed.config.json %EXTRA_ARGS%
if errorlevel 1 (
    echo [FAIL] Ops Manager test failed.
    set /a TOTAL_FAILED+=1
) else (
    echo [PASS] Ops Manager test completed.
)
echo.

REM --- 2) Agency Owner ---
echo [2/3] Running Agency Owner performance test...
set "PERF_ENV=%ENV_FLAG%"
call sitespeed.io.cmd scripts\dashboard_agency_owner.js --config sitespeed.config.json %EXTRA_ARGS%
if errorlevel 1 (
    echo [FAIL] Agency Owner test failed.
    set /a TOTAL_FAILED+=1
) else (
    echo [PASS] Agency Owner test completed.
)
echo.

REM --- 3) Agent ---
echo [3/3] Running Agent performance test...
set "PERF_ENV=%ENV_FLAG%"
if /i "%ENV_FLAG%"=="prod" (
    set "AGENT_SCRIPT=scripts\dashboard_agent.js"
) else (
    set "AGENT_SCRIPT=scripts\dashboard_agent_preprod.js"
)
call sitespeed.io.cmd %AGENT_SCRIPT% --config sitespeed.config.json %EXTRA_ARGS%
if errorlevel 1 (
    echo [FAIL] Agent test failed.
    set /a TOTAL_FAILED+=1
) else (
    echo [PASS] Agent test completed.
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
