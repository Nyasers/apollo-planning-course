@echo off
setlocal
title Apollo Claw Harness 一键配置
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-harness-oneclick.ps1"
if errorlevel 1 (
  echo.
  echo 一键配置没有完成，请查看上方提示。
) else (
  echo.
  echo 一键配置完成。
)
pause
endlocal
