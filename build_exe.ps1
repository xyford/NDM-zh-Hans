# NDM-zh-Hans 单文件 exe 构建脚本
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
C:\Python314\python.exe -m PyInstaller --onefile --windowed --uac-admin `
  --name ndm-zh-patch --collect-all capstone --add-data "translations.json;." `
  --distpath dist --workpath build --specpath . gui_patcher.py --noconfirm
Copy-Item dist\ndm-zh-patch.exe portable\ndm-zh-patch.exe -Force
Write-Output 'built: dist\ndm-zh-patch.exe, portable\ndm-zh-patch.exe'
