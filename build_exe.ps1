$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Najpierw uruchom start.bat.' }
& $taskPython -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Blad instalacji narzedzi.' }
& $taskPython -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Blad przygotowania przegladarki.' }
& $taskPython -m PyInstaller --noconfirm --clean 'Neto Incident Monitor.spec'
if ($LASTEXITCODE -ne 0) { throw 'Blad budowania EXE.' }
Write-Host 'Gotowe: dist\Neto Incident Monitor\Neto Incident Monitor.exe'
