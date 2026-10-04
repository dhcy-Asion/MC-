param(
    [Parameter(Mandatory=$true)][string]$Item,
    [ValidateRange(1,6400)][int]$Count=1
)
$ErrorActionPreference='Stop'
$body=@{item=$Item;count=$Count} | ConvertTo-Json -Compress
$result=Invoke-RestMethod -Uri 'http://127.0.0.1:8767/ui/add-item' -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 15
Write-Output $result
