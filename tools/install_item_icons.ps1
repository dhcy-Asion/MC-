$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
if(Get-Process -Name CrimsonDesert -ErrorAction SilentlyContinue){throw 'Close Crimson Desert before installing item icons.'}
$manifestPath=Join-Path $projectRoot 'runtime\installation.json'
$manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$iconRoot=Join-Path $projectRoot 'downloads\minecraft-icons-1.21.1'
$icons=Get-Content -LiteralPath (Join-Path $iconRoot 'manifest.json') -Raw | ConvertFrom-Json
$config=Get-Content -LiteralPath (Join-Path $projectRoot 'config\item-icons.json') -Raw | ConvertFrom-Json
if($icons.version -ne $config.minecraftVersion -or $icons.archiveSha256 -ne $config.archiveSha256 -or @($icons.items).Count -ne $config.iconCount){throw 'Icon manifest does not match the pinned configuration.'}
$binRoot=[IO.Path]::GetFullPath((Join-Path $manifest.gameRoot 'bin64')).TrimEnd('\')+'\'
$targetRoot=Join-Path $binRoot 'cdmodkit\mc-icons'
# Reject directory junctions rather than resolving a copy outside the installation.
foreach($directory in @($binRoot,(Join-Path $binRoot 'cdmodkit'),$targetRoot)){
    if((Test-Path -LiteralPath $directory) -and ((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw "Linked target directory refused: $directory"}
}
$plan=@()
$seen=@{}
foreach($icon in $icons.items){
    if($icon.file -notmatch '^[a-z0-9_]+\.png$' -or $icon.id -cne ('minecraft:'+[IO.Path]::GetFileNameWithoutExtension($icon.file)) -or $seen.ContainsKey($icon.file)){throw 'Invalid or duplicate icon filename.'}
    $seen[$icon.file]=$true
    $source=Join-Path $iconRoot $icon.file
    $target=[IO.Path]::GetFullPath((Join-Path $targetRoot $icon.file))
    if(!$target.StartsWith($binRoot,[StringComparison]::OrdinalIgnoreCase)){throw "Unexpected target: $target"}
    if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $icon.sha256){throw "Cached icon changed: $source"}
    if(Test-Path -LiteralPath $target){
        if((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint){throw "Linked target file refused: $target"}
        $owned=@($manifest.files | Where-Object { $_.path -eq $target })
        if($owned.Count -ne 1 -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $owned[0].sha256){throw "Existing icon is not unchanged project-owned content: $target"}
    }
    $plan+=@{source=$source;path=$target;sha256=$icon.sha256}
}
New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
$targets=@{};foreach($item in $plan){$targets[$item.path]=$true}
$manifest.files=@($manifest.files | Where-Object { !$targets.ContainsKey($_.path) })+@($plan | ForEach-Object { @{path=$_.path;sha256=$_.sha256} })
# Record ownership first so an interrupted copy can be repaired or safely uninstalled.
$temporary=$manifestPath+'.icons.tmp'
[IO.File]::WriteAllText($temporary,($manifest | ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $temporary -Destination $manifestPath -Force
foreach($item in $plan){
    $staged=$item.path+'.install-'+[Guid]::NewGuid().ToString('N')
    Copy-Item -LiteralPath $item.source -Destination $staged
    if((Get-FileHash -LiteralPath $staged -Algorithm SHA256).Hash -ne $item.sha256){throw "Staged icon verification failed: $staged"}
    Move-Item -LiteralPath $staged -Destination $item.path -Force
}
Write-Output "Installed and verified $($plan.Count) item icons; recorded in installation.json."
