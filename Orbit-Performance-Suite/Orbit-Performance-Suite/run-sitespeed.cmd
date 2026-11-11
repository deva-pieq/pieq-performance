@echo off
REM Run sitespeed, then always build the custom dashboard from the latest result.
cd /d "%~dp0"

if "%~1"=="" (
  echo Usage: run-sitespeed.cmd script.js [extra sitespeed flags]
  echo Example: run-sitespeed.cmd scripts\dashboard_admin.js -n 1
  exit /b 1
)

sitespeed.io %1 --config sitespeed.config.json %2 %3 %4 %5 %6 %7 %8 %9
if errorlevel 1 exit /b 1

python build-custom-dashboard.py
if errorlevel 1 exit /b 1

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

echo.
echo Custom dashboard (latest): custom-dashboard\index.html
