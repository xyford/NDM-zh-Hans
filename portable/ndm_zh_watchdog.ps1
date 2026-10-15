# NDM 汉化看门狗 (便携版): 与 ndm-zh-patch.exe 同目录
# 登录时/每小时由计划任务触发; exe 变回英文版则自动重打补丁
$ErrorActionPreference = 'Stop'
$exe = 'C:\Program Files (x86)\Neat Download Manager\NeatDM.exe'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$patcher = Join-Path $dir 'ndm-zh-patch.exe'
$hashFile = Join-Path $dir 'patched.hash'
$logFile  = Join-Path $dir 'watchdog.log'

function Log($msg) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

if (-not (Test-Path $exe)) { exit 0 }

$bytes = [System.IO.File]::ReadAllBytes($exe)
$peoff = [BitConverter]::ToInt32($bytes, 0x3c)
$nsec  = [BitConverter]::ToUInt16($bytes, $peoff + 6)
$optsz = [BitConverter]::ToUInt16($bytes, $peoff + 20)
$sec0  = $peoff + 24 + $optsz
$hasL10n = $false
for ($i = 0; $i -lt $nsec; $i++) {
    $nm = [System.Text.Encoding]::ASCII.GetString($bytes, $sec0 + $i * 40, 8).TrimEnd([char]0)
    if ($nm -eq '.l10n') { $hasL10n = $true; break }
}
$curHash = (Get-FileHash $exe -Algorithm SHA256).Hash

if ($hasL10n) {
    if ((Test-Path $hashFile) -and ((Get-Content $hashFile -Raw).Trim() -eq $curHash)) { exit 0 }
    Set-Content -Path $hashFile -Value $curHash -Encoding ASCII
    exit 0
}

$wasRunning = $false
Get-Process -Name 'NeatDM' -ErrorAction SilentlyContinue | ForEach-Object {
    $wasRunning = $true
    Stop-Process -Id $_.Id -Force
}
if ($wasRunning) { Start-Sleep -Seconds 2 }

$bak = Join-Path $dir 'NeatDM.original.bak'
if (-not (Test-Path $bak)) { Copy-Item $exe $bak -Force; Log '已备份原版' }

& $patcher $exe | Out-Null
$rc = $LASTEXITCODE
if ($rc -eq 0 -or $rc -eq 2) {
    Set-Content -Path $hashFile -Value (Get-FileHash $exe -Algorithm SHA256).Hash -Encoding ASCII
    Log "已重新汉化 (rc=$rc)"
} else {
    Log "重打失败 rc=$rc"
}
if ($wasRunning) { Start-Process $exe }
