@echo off
chcp 65001 >nul
setlocal
title 卸载 NDM 汉化自动保持

net session >nul 2>&1
if errorlevel 1 (
  echo 需要管理员权限，正在请求提权...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

powershell -NoProfile -Command "Unregister-ScheduledTask -TaskName 'NDM-zh-autopatch' -Confirm:$false -ErrorAction SilentlyContinue"
echo [√] 已删除计划任务 NDM-zh-autopatch
echo （保留 %LOCALAPPDATA%\NDM-zh 下的补丁器文件，可手动删除）
pause
