param([ValidateSet('F7','F8','F9','INSERT')][string]$MenuKey='F8')
$ErrorActionPreference='Stop'
if(Get-Process -Name CrimsonDesert -ErrorAction SilentlyContinue){throw 'Save and close Crimson Desert before changing its prototype menu key.'}
$projectRoot=Split-Path $PSScriptRoot -Parent
$manifest=Get-Content -LiteralPath (Join-Path $projectRoot 'runtime\installation.json') -Raw | ConvertFrom-Json
$settingsPath=Join-Path $manifest.gameRoot 'bin64\cdmodkit\settings.txt'
$owned=@($manifest.files | Where-Object { $_.path -eq $settingsPath })
if($owned.Count -ne 1){throw 'Expected the prototype installation to own this settings path.'}
$text=[IO.File]::ReadAllText($settingsPath)
$matches=[regex]::Matches($text,'(?m)^key_toggle=[^\r\n]*')
if($matches.Count -ne 1){throw 'Expected exactly one menu key entry; settings retained.'}
if($matches[0].Value -eq ('key_toggle='+$MenuKey)){Write-Output "Menu key is already $MenuKey.";exit}
$backupRoot=Join-Path $projectRoot 'backups'
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$backup=Join-Path $backupRoot ('settings-before-menu-key-'+[Guid]::NewGuid().ToString('N')+'.txt')
Copy-Item -LiteralPath $settingsPath -Destination $backup
$next=[regex]::Replace($text,'(?m)^key_toggle=[^\r\n]*',('key_toggle='+$MenuKey))
[IO.File]::WriteAllText($settingsPath,$next,[Text.UTF8Encoding]::new($false))
Write-Output "Prototype menu key changed to $MenuKey. Other settings retained; backup: $backup"
