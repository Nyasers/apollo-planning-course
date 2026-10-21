@echo off
setlocal
chcp 65001 >nul
title Apollo Claw Harness Setup
set "SCRIPT=%~dp0scripts\install-harness-oneclick.ps1"
set "CHECK_ARG="
set "NO_PAUSE="
if /I "%~1"=="--check" (
  set "CHECK_ARG=-CheckOnly"
  set "NO_PAUSE=1"
)
if not exist "%SCRIPT%" (
  echo [ERROR] Setup script not found: %SCRIPT%
  if not defined NO_PAUSE pause
  exit /b 1
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %CHECK_ARG%
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo [ERROR] Harness setup failed. Review the messages above.
) else (
  echo.
  echo Harness setup completed.
)
if not defined NO_PAUSE pause
exit /b %EXIT_CODE%