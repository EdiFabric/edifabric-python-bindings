<#
.SYNOPSIS
Build the platform wheels, smoke-test the one for this machine, and upload them.

.DESCRIPTION
Uploads with twine; set TWINE_USERNAME=__token__ and TWINE_PASSWORD=<PyPI API token>.

.EXAMPLE
./scripts/release.ps1 -DryRun
./scripts/release.ps1 -TestPyPI
./scripts/release.ps1
#>
param(
    [switch]$DryRun,
    [switch]$TestPyPI,
    [switch]$SkipFetch,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Invoke-Checked {
    # Native tools write progress to stderr; only the exit code decides failure.
    $ErrorActionPreference = 'Continue'
    & $args[0] $args[1..($args.Count - 1)] 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "$($args -join ' ') failed with exit code $LASTEXITCODE" }
}

Invoke-Checked $Python -m pip install --quiet --disable-pip-version-check --no-warn-script-location --upgrade build wheel twine

if (-not $SkipFetch) { & "$PSScriptRoot/fetch-natives.ps1" -Destination natives }
Invoke-Checked $Python scripts/build_wheels.py
$wheels = Get-ChildItem dist -Filter *.whl | ForEach-Object FullName
Invoke-Checked $Python -m twine check --strict @wheels

$venv = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName())
try {
    Invoke-Checked $Python -m venv $venv
    $venvPython = if ($IsWindows -or $env:OS -eq 'Windows_NT') { "$venv/Scripts/python.exe" } else { "$venv/bin/python" }
    Invoke-Checked $venvPython -m pip install --quiet --disable-pip-version-check --no-index --find-links dist edifabric-x12
    Invoke-Checked $venvPython scripts/smoke_test.py
}
finally {
    Remove-Item $venv -Recurse -Force -ErrorAction SilentlyContinue
}

if ($DryRun) {
    Write-Host "Dry run: built $($wheels.Count) wheels, nothing uploaded."
    return
}
$repository = if ($TestPyPI) { 'testpypi' } else { 'pypi' }
Invoke-Checked $Python -m twine upload --repository $repository @wheels
