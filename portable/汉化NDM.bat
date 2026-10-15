@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title NDM 汉化补丁

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=C:\Program Files (x86)\Neat Download Manager\NeatDM.exe"

if not exist "%TARGET%" (
  echo [X] 找不到文件: %TARGET%
  echo     请先安装 Neat Download Manager，或把 NeatDM.exe 拖到本批处理上
  pause
  exit /b 1
)

rem 仅当目标在 Program Files 下才需要提权
echo %TARGET% | findstr /I /C:"Program Files" >nul
if not errorlevel 1 (
  net session >nul 2>&1
  if errorlevel 1 (
    echo 需要管理员权限，正在请求提权...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '\"%TARGET%\"' -Verb RunAs"
    exit /b
  )
)

echo [*] 目标: %TARGET%
taskkill /F /IM NeatDM.exe >nul 2>&1
set "KILLED=!errorlevel!"
if "!KILLED!"=="0" echo [*] 已结束运行中的 NDM

"%~dp0ndm-zh-patch.exe" --silent "%TARGET%"
set RC=!errorlevel!

if "!KILLED!"=="0" (
  start "" "%TARGET%"
  echo [*] 已重启 NDM
)

echo.
if !RC!==0 (
  echo [√] 汉化完成
) else if !RC!==2 (
  echo [=] 已经是汉化版，无需操作
) else (
  echo [X] 汉化失败，错误码 !RC!
)
pause
