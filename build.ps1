# Builds the portable package dist\GlintRemote-Windows-x64.zip
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# libmpv: official Windows build linked from mpv.io (shinchiro), verified by SHA-256.
$MpvUrl = "https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/20261111/mpv-dev-x86_64-20261111-git-bcde6b93cc.7z"
$MpvSha = "273c079b11ea5575822f972756f4c9a71149a5c10130353abeb8586738938452"

if (-not (Test-Path ".venv\Scripts\python.exe")) { py -3.13 -m venv .venv; if ($LASTEXITCODE -ne 0) { python -m venv .venv } }
$py = ".venv\Scripts\python.exe"
& $py -m pip install --disable-pip-version-check -q -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "pip failed" }

if (-not (Test-Path "vendor\libmpv-2.dll")) {
    New-Item -ItemType Directory -Force "vendor\_dl" | Out-Null
    $arch = "vendor\_dl\mpv-dev.7z"
    if (-not (Test-Path $arch)) { Invoke-WebRequest -UseBasicParsing $MpvUrl -OutFile $arch }
    $sha = (& certutil -hashfile $arch SHA256 | Select-Object -Index 1).Replace(" ", "").ToLower()
    if ($sha -ne $MpvSha) { Remove-Item $arch; throw "libmpv SHA-256 mismatch: $sha" }
    Push-Location vendor; & "$env:SystemRoot\System32\tar.exe" -xf "_dl\mpv-dev.7z" libmpv-2.dll; Pop-Location
    if (-not (Test-Path "vendor\libmpv-2.dll")) { throw "could not extract libmpv-2.dll" }
}

& $py -m pyflakes viewer tools tests
if ($LASTEXITCODE -ne 0) { throw "pyflakes found problems" }
& $py -m pytest tests\test_logic.py
if ($LASTEXITCODE -ne 0) { throw "unit tests failed" }

& $py tools\build_portable.py
if ($LASTEXITCODE -ne 0) { throw "build_portable failed" }
& $py tools\make_zip.py
if ($LASTEXITCODE -ne 0) { throw "make_zip failed" }
Write-Host "Done: dist\GlintRemote-Windows-x64.zip  (run: dist\GlintRemote-Viewer\GlintRemote-Viewer.cmd)"
