$ErrorActionPreference='Stop'
# Local endpoints save/stop their own processes; the red-side game remains open.
try {
    $state=Invoke-RestMethod 'http://127.0.0.1:8766/api/state' -TimeoutSec 4
    if($state.engine -ne 'Minecraft Java 1.21.1'){throw 'Unexpected authority service'}
    $mcProcessId=(Get-NetTCPConnection -LocalPort 8766 -State Listen).OwningProcess
    Invoke-RestMethod 'http://127.0.0.1:8766/api/shutdown' -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 5 | Out-Null
    if(Get-Process -Id $mcProcessId -ErrorAction SilentlyContinue){Wait-Process -Id $mcProcessId -Timeout 30}
} catch {
    if(Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue){throw}
}
try {
    $state=Invoke-RestMethod 'http://127.0.0.1:8767/ui/state' -TimeoutSec 8
    if($state -notmatch 'Minecraft Java 1.21.1 authority'){throw 'Unexpected bridge service'}
    $bridgeProcessId=(Get-NetTCPConnection -LocalPort 8767 -State Listen).OwningProcess
    Invoke-RestMethod 'http://127.0.0.1:8767/ui/shutdown' -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 5 | Out-Null
    if(Get-Process -Id $bridgeProcessId -ErrorAction SilentlyContinue){Wait-Process -Id $bridgeProcessId -Timeout 10}
} catch {
    if(Get-NetTCPConnection -LocalPort 8767 -State Listen -ErrorAction SilentlyContinue){throw}
}
Write-Host 'Local MC and bridge services stopped; their saves and the game remain intact.'
