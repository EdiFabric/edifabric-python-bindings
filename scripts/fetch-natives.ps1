<#
.SYNOPSIS
Download the ediFabric Native X12 library for every platform into <Destination>/<rid>/.

.EXAMPLE
./scripts/fetch-natives.ps1
./scripts/fetch-natives.ps1 -Destination natives
#>
param(
    [string]$Destination = 'natives',
    [string]$BaseUrl = $(if ($env:EDIFABRIC_DOWNLOAD_URL) { $env:EDIFABRIC_DOWNLOAD_URL } else { 'https://www.edifabric.com/download' })
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$work = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName())
New-Item -ItemType Directory $work | Out-Null
try {
    foreach ($rid in 'win-x64', 'linux-x64', 'linux-arm64', 'osx-arm64') {
        Write-Host "Downloading $rid"
        $zip = Join-Path $work "$rid.zip"
        Invoke-WebRequest -UseBasicParsing "$BaseUrl/edifabric-x12-tools-$rid.zip" -OutFile $zip
        Expand-Archive $zip (Join-Path $work $rid)
        $target = Join-Path $Destination $rid
        if (Test-Path $target) { Remove-Item $target -Recurse -Force }
        New-Item -ItemType Directory $target -Force | Out-Null
        # Keep the library and its signature; the zip's README.txt is not redistributed.
        Get-ChildItem (Join-Path $work $rid) -Recurse -File -Filter 'edifabric-x12-tools.*' | Copy-Item -Destination $target
        Get-ChildItem $target | Format-Table Name, Length -AutoSize
    }
}
finally {
    Remove-Item $work -Recurse -Force
}
