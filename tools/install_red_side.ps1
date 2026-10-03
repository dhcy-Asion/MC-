param([string]$GameRoot='E:\SteamLibrary\steamapps\common\Crimson Desert')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$binRoot=Join-Path $GameRoot 'bin64'
if(Get-Process -Name CrimsonDesert -ErrorAction SilentlyContinue){throw 'Close Crimson Desert before installing.'}
if(!(Test-Path -LiteralPath (Join-Path $binRoot 'CrimsonDesert.exe'))){throw 'Game executable not found.'}
$manifestPath=Join-Path $projectRoot 'runtime\installation.json'
if(Test-Path -LiteralPath $manifestPath){throw 'Installation manifest already exists. Inspect the current installation first.'}
$sources=@(
    @{source=(Join-Path $projectRoot 'downloads\asi-loader-v9.7.4\dinput8.dll'); target=(Join-Path $binRoot 'winmm.dll')},
    @{source=(Join-Path $projectRoot 'build\world-builder\cdmodkit.asi'); target=(Join-Path $binRoot 'cdmodkit.asi')}
)
foreach($item in $sources){
    if(!(Test-Path -LiteralPath $item.source)){throw "Missing build: $($item.source)"}
    if(Test-Path -LiteralPath $item.target){throw "Refusing to overwrite existing file: $($item.target)"}
}
$settingsPath=Join-Path $binRoot 'cdmodkit\settings.txt'
if(Test-Path -LiteralPath $settingsPath){throw 'Existing cdmodkit settings found. Refusing to overwrite.'}
$backupRoot=Join-Path $projectRoot ('backups\before-install-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$saveRoot=Join-Path $env:LOCALAPPDATA 'Pearl Abyss\CD\save'
if(Test-Path -LiteralPath $saveRoot){Copy-Item -LiteralPath $saveRoot -Destination (Join-Path $backupRoot 'red-saves') -Recurse}
$steamUserData='C:\Program Files (x86)\Steam\userdata'
if(Test-Path -LiteralPath $steamUserData){
    foreach($account in (Get-ChildItem -LiteralPath $steamUserData -Directory)){
        $appData=Join-Path $account.FullName '3321460'
        if(Test-Path -LiteralPath $appData){Copy-Item -LiteralPath $appData -Destination (Join-Path $backupRoot ('steam-appdata-'+$account.Name)) -Recurse}
    }
}
New-Item -ItemType Directory -Path (Split-Path $manifestPath -Parent),(Split-Path $settingsPath -Parent) -Force | Out-Null
$settings="key_toggle=INSERT`nkey_mode=HOME`nconsole=0`nlanguage=zh-CN`nhttp_api=1`nhttp_port=8765`nfovauto=1`nfov=55.0`nmirror=0`npreview_quality=0`n"
[IO.File]::WriteAllText($settingsPath,$settings,[Text.UTF8Encoding]::new($false))
$installed=@(@{path=$settingsPath;sha256=(Get-FileHash -LiteralPath $settingsPath -Algorithm SHA256).Hash})
foreach($item in $sources){
    Copy-Item -LiteralPath $item.source -Destination $item.target
    $installed+=@{path=$item.target;sha256=(Get-FileHash -LiteralPath $item.target -Algorithm SHA256).Hash}
}
$manifest=@{gameRoot=$GameRoot;backupRoot=$backupRoot;created=(Get-Date -Format 'o');files=$installed}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8
$manifest | ConvertTo-Json -Depth 5
