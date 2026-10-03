$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$manifestPath=Join-Path $projectRoot 'runtime\installation.json'
if(Get-Process -Name CrimsonDesert -ErrorAction SilentlyContinue){throw 'Close Crimson Desert before uninstalling.'}
$manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$allowedRoot=[IO.Path]::GetFullPath((Join-Path $manifest.gameRoot 'bin64')).TrimEnd('\')+'\'
foreach($item in $manifest.files){
    $resolved=[IO.Path]::GetFullPath($item.path)
    if(!$resolved.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase)){throw "Unexpected target: $resolved"}
    if(Test-Path -LiteralPath $resolved){
        $hash=(Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
        if($hash -ne $item.sha256){Write-Warning "Changed since installation; retained: $resolved";continue}
        Remove-Item -LiteralPath $resolved
        Write-Output "Removed prototype file: $resolved"
    }
}
Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $projectRoot 'runtime\installation-uninstalled.json') -Force
Remove-Item -LiteralPath $manifestPath
Write-Output 'Original game files were not overwritten. Generated plugin logs/projects are retained.'
