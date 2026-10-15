@echo off
chcp 65001 >nul
setlocal
title 恢复 NDM 原版英文

net session >nul 2>&1
if errorlevel 1 (
  echo 需要管理员权限，正在请求提权...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set "TARGET=C:\Program Files (x86)\Neat Download Manager\NeatDM.exe"
set "BAK=%~dp0NeatDM.original.bak"
if not exist "%BAK%" set "BAK=%LOCALAPPDATA%\NDM-zh\NeatDM.original.bak"
if not exist "%BAK%" (
  echo [X] 找不到原版备份 NeatDM.original.bak
  pause
  exit /b 1
)

taskkill /F /IM NeatDM.exe >nul 2>&1
copy /y "%BAK%" "%TARGET%" >nul
powershell -NoProfile -Command "Unregister-ScheduledTask -TaskName 'NDM-zh-autopatch' -Confirm:$false -ErrorAction SilentlyContinue"
start "" "%TARGET%"
echo [√] 已恢复原版英文并停用自动保持
pause
