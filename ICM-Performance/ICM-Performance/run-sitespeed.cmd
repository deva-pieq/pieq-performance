@echo off
REM Run sitespeed, then always build the custom dashboard from the latest result.
cd /d "%~dp0"

if "%~1"=="" (
  echo Usage: run-sitespeed.cmd script.js [extra sitespeed flags]
  echo Example: run-sitespeed.cmd dashboard_op_prod1_js.js -n 1
  exit /b 1
)

call sitespeed.io.cmd %1 --config sitespeed.config.json %2 %3 %4 %5 %6 %7 %8 %9
if errorlevel 1 exit /b 1

python build-custom-dashboard.py
if errorlevel 1 exit /b 1

echo.
echo Custom dashboard (latest): custom-dashboard\index.html
