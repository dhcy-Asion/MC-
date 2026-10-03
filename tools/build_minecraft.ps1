param([string]$Task='build')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$jdk=Get-ChildItem -LiteralPath (Join-Path $projectRoot 'downloads\jdk21') -Directory | Select-Object -First 1
$env:JAVA_HOME=$jdk.FullName
$env:GRADLE_USER_HOME=Join-Path $env:USERPROFILE '.gradle-crimsonmc'
Push-Location (Join-Path $projectRoot 'minecraft')
try {
    & (Join-Path $projectRoot 'downloads\gradle\gradle-8.10.2\bin\gradle.bat') --no-daemon --no-watch-fs --console=plain '-Dorg.gradle.internal.instrumentation.agent=false' $Task
    if($LASTEXITCODE){throw "Gradle task failed: $Task"}
} finally {Pop-Location}
