param([Parameter(Mandatory=$true)][string]$Dir)
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f (Join-Path $Dir 'ndm_zh_watchdog.ps1'))
$triggerLogon = New-ScheduledTaskTrigger -AtLogOn
$triggerHourly = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName 'NDM-zh-autopatch' -Action $action -Trigger @($triggerLogon, $triggerHourly) -Principal $principal -Settings $settings -Force | Out-Null
