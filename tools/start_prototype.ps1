param([switch]$NoGame)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$runtimeRoot=Join-Path $projectRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
function Get-MCState {
    try { return Invoke-RestMethod -Uri 'http://127.0.0.1:8766/api/state' -TimeoutSec 3 }
    catch { return $null }
}
$mcState=Get-MCState
if($mcState -and $mcState.engine -ne 'Minecraft Java 1.21.1'){throw 'Port 8766 is occupied by an unexpected service.'}
if(-not $mcState){
    if(Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue){throw 'Port 8766 is occupied; do not start a duplicate server.'}
    $buildScript=Join-Path $PSScriptRoot 'build_minecraft.ps1'
    $mcProcess=Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$buildScript+'"'),'-Task','runServer') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeRoot 'mc-start.stdout.log') -RedirectStandardError (Join-Path $runtimeRoot 'mc-start.stderr.log') -PassThru
    Write-Host 'Starting Minecraft rules server...'
    $deadline=(Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 2
        $mcState=Get-MCState
        if($mcProcess.HasExited -and -not $mcState){throw 'MC startup failed; inspect runtime/mc-start logs.'}
    } while(-not $mcState -and (Get-Date) -lt $deadline)
    if(-not $mcState){throw 'MC is still starting. Inspect runtime/mc-start logs before retrying.'}
}
$bridgeText=$null
try {$bridgeText=Invoke-RestMethod -Uri 'http://127.0.0.1:8767/ui/state' -TimeoutSec 8} catch {}
if($bridgeText -and $bridgeText -notmatch 'Minecraft Java 1.21.1 authority'){throw 'Port 8767 is occupied by an unexpected service.'}
if(-not $bridgeText){
    if(Get-NetTCPConnection -LocalPort 8767 -State Listen -ErrorAction SilentlyContinue){throw 'Port 8767 is occupied; do not start a duplicate bridge.'}
    $pythonPath=(Get-Command python.exe).Source
    Start-Process -FilePath $pythonPath -ArgumentList @('-u','-m','bridge.service') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeRoot 'bridge.stdout.log') -RedirectStandardError (Join-Path $runtimeRoot 'bridge.stderr.log') | Out-Null
    $deadline=(Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 500
        try {$bridgeText=Invoke-RestMethod -Uri 'http://127.0.0.1:8767/ui/state' -TimeoutSec 8} catch {}
    } while(-not $bridgeText -and (Get-Date) -lt $deadline)
    if(-not $bridgeText){throw 'Bridge startup failed; inspect runtime/bridge logs.'}
}
if(-not $NoGame -and -not (Get-Process CrimsonDesert -ErrorAction SilentlyContinue)){
    Start-Process -FilePath 'steam://rungameid/3321460'
}
Write-Host 'Ready. Enter the Crimson Desert world and press Insert for the MC panel.'
Write-Host 'After a game restart, click Restore Blocks in the MC panel.'
