param([string]$Task='build')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
if($Task -eq 'runServer'){
    $languageFile=Join-Path $projectRoot 'downloads\minecraft-lang-1.21.1-zh_cn.json'
    if(!(Test-Path -LiteralPath $languageFile -PathType Leaf)){throw 'Run tools/prepare_environment.ps1 first: official Minecraft zh_cn language data is missing.'}
    if((Get-FileHash -LiteralPath $languageFile -Algorithm SHA1).Hash -ne 'f87510f4509890eaf176e0de1430f6bb326a6800'){throw 'Minecraft zh_cn checksum mismatch. Existing file retained; repair the language download before starting.'}
}
$jdk=Get-ChildItem -LiteralPath (Join-Path $projectRoot 'downloads\jdk21') -Directory | Select-Object -First 1
$env:JAVA_HOME=$jdk.FullName
$env:GRADLE_USER_HOME=Join-Path $env:USERPROFILE '.gradle-crimsonmc'
Push-Location (Join-Path $projectRoot 'minecraft')
try {
    & (Join-Path $projectRoot 'downloads\gradle\gradle-8.10.2\bin\gradle.bat') --no-daemon --no-watch-fs --console=plain '-Dorg.gradle.internal.instrumentation.agent=false' $Task
    if($LASTEXITCODE){throw "Gradle task failed: $Task"}
} finally {Pop-Location}
