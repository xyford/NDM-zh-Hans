@echo off
chcp 65001 >nul
setlocal
title 安装 NDM 汉化自动保持

net session >nul 2>&1
if errorlevel 1 (
  echo 需要管理员权限，正在请求提权...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set "DEST=%LOCALAPPDATA%\NDM-zh"
if not exist "%DEST%" mkdir "%DEST%"
copy /y "%~dp0ndm-zh-patch.exe" "%DEST%\" >nul
copy /y "%~dp0ndm_zh_watchdog.ps1" "%DEST%\" >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_task.ps1" -Dir "%DEST%"
if errorlevel 1 (
  echo [X] 计划任务注册失败
  pause
  exit /b 1
)
echo.
echo [√] 已安装自动保持：登录时和每小时自动检查，NDM 更新后会自动重新汉化
echo     文件位置: %DEST%
pause
