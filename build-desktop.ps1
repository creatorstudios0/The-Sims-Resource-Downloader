param(
    [string]$Output = (Join-Path $PSScriptRoot 'dist'),
    [string]$Work = (Join-Path $PSScriptRoot 'build')
)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot 'venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Run start.bat once to prepare the Python environment.' }
New-Item -ItemType Directory -Path $Work, $Output -Force | Out-Null
$Work = (Resolve-Path -LiteralPath $Work).Path
$Output = (Resolve-Path -LiteralPath $Output).Path
$config = Join-Path $PSScriptRoot 'src/config.json'
$entry = Join-Path $PSScriptRoot 'src/desktop_qt.py'
$iconBuilder = Join-Path $PSScriptRoot 'src/build_icon.py'
$icon = Join-Path $Work 'Mod Library.ico'
& $python $iconBuilder $icon
if ($LASTEXITCODE) { throw 'Could not generate application icon.' }
$version = Join-Path $PSScriptRoot 'src/windows-version.txt'
# Qt links to the Windows ICU DLL. Prefer system DLLs over similarly named tools on PATH.
$buildSearchPath = $env:Path
try {
    $env:Path = "$(Join-Path $env:SystemRoot 'System32');$buildSearchPath"
    & $python -m PyInstaller --clean --noconfirm --onefile --windowed --name 'Sims 4 Mod Library 2.0' --distpath $Output --workpath $Work --specpath $Work --icon $icon --version-file $version --add-data "${config}:." $entry
    if ($LASTEXITCODE) { throw 'PyInstaller failed.' }
} finally {
    $env:Path = $buildSearchPath
}
