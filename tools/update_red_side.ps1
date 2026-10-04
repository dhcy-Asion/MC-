$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
if(Get-Process -Name CrimsonDesert -ErrorAction SilentlyContinue){throw 'Close Crimson Desert before updating.'}
$manifestPath=Join-Path $projectRoot 'runtime\installation.json'
$manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$entry=$manifest.files | Where-Object { [IO.Path]::GetFileName($_.path) -eq 'cdmodkit.asi' }
if(@($entry).Count -ne 1){throw 'Expected exactly one installed ASI.'}
$currentHash=(Get-FileHash -LiteralPath $entry.path -Algorithm SHA256).Hash
if($currentHash -ne $entry.sha256){throw 'Installed ASI changed outside this project; refusing overwrite.'}
$build=Join-Path $projectRoot 'build\world-builder\cdmodkit.asi'
$nextHash=(Get-FileHash -LiteralPath $build -Algorithm SHA256).Hash
if($currentHash -eq $nextHash){
    & (Join-Path $PSScriptRoot 'install_item_icons.ps1')
    Write-Output 'Already up to date.'
    exit
}
$archive=Join-Path $projectRoot ('backups\cdmodkit-'+$currentHash.Substring(0,12)+'.asi')
Copy-Item -LiteralPath $entry.path -Destination $archive
Copy-Item -LiteralPath $build -Destination $entry.path -Force
$entry.sha256=$nextHash
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8
& (Join-Path $PSScriptRoot 'install_item_icons.ps1')
Write-Output "Installed MC control panel. SHA256: $nextHash"
