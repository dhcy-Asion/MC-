param(
    [switch]$AcceptMinecraftEula,
    [switch]$SourceBuild
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$downloadsRoot=Join-Path $projectRoot 'downloads'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
New-Item -ItemType Directory -Path $downloadsRoot -Force | Out-Null

function Assert-ArchiveHash([string]$Archive,[string]$ExpectedHash) {
    $actual=(Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
    if($actual -ne $ExpectedHash) {
        throw "Checksum mismatch: $Archive. Existing files were retained; inspect this archive before retrying."
    }
}

function Ensure-PortableTool {
    param([string]$ArchiveName,[string]$Url,[string]$Sha256,[string]$Directory,[string]$ExpectedFile)
    $archive=Join-Path $downloadsRoot $ArchiveName
    $destination=Join-Path $downloadsRoot $Directory
    $expected=Join-Path $destination $ExpectedFile
    if(Test-Path -LiteralPath $archive -PathType Leaf){Assert-ArchiveHash $archive $Sha256}
    if(Test-Path -LiteralPath $expected -PathType Leaf){
        Write-Host "Using existing $Directory."
        return
    }
    if(Test-Path -LiteralPath $destination){
        if(Get-ChildItem -LiteralPath $destination -Force | Select-Object -First 1){
            throw "Incomplete existing directory: $destination. Its contents were retained; move it aside or repair it before retrying."
        }
    }
    if(!(Test-Path -LiteralPath $archive -PathType Leaf)){
        $partial=Join-Path $downloadsRoot ($ArchiveName+'.download-'+[Guid]::NewGuid().ToString('N')+'.zip')
        Write-Host "Downloading $ArchiveName from its official release..."
        Invoke-WebRequest -Uri $Url -OutFile $partial -UseBasicParsing
        Assert-ArchiveHash $partial $Sha256
        Move-Item -LiteralPath $partial -Destination $archive
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $destination
    if(!(Test-Path -LiteralPath $expected -PathType Leaf)){
        throw "Archive did not provide the expected file: $expected. Extracted files were retained."
    }
    Write-Host "Prepared $Directory."
}

Ensure-PortableTool -ArchiveName 'temurin21-jdk.zip' -Url 'https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip' -Sha256 'f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e' -Directory 'jdk21' -ExpectedFile 'jdk-21.0.12.1+1\bin\java.exe'
# Verified against https://services.gradle.org/distributions/gradle-8.10.2-bin.zip.sha256.
Ensure-PortableTool -ArchiveName 'gradle-8.10.2-bin.zip' -Url 'https://services.gradle.org/distributions/gradle-8.10.2-bin.zip' -Sha256 '31c55713e40233a8303827ceb42ca48a47267a0ad4bab9177123121e71524c26' -Directory 'gradle' -ExpectedFile 'gradle-8.10.2\bin\gradle.bat'
Ensure-PortableTool -ArchiveName 'Ultimate-ASI-Loader-NoPDB_x64-v9.7.4.zip' -Url 'https://github.com/ThirteenAG/Ultimate-ASI-Loader/releases/download/v9.7.4/Ultimate-ASI-Loader-NoPDB_x64.zip' -Sha256 'e5860e7d9a1805267535b65749575b5e406cc6ea3325c7392189c578815045d1' -Directory 'asi-loader-v9.7.4' -ExpectedFile 'dinput8.dll'

# Minecraft 1.21.1 asset index 17: official zh_cn resource, retained only in ignored downloads.
# https://piston-meta.mojang.com/v1/packages/9b16298b1dc0697878cec88bb2d96168f5239e4f/17.json
$languageHash='f87510f4509890eaf176e0de1430f6bb326a6800'
$languageFile=Join-Path $downloadsRoot 'minecraft-lang-1.21.1-zh_cn.json'
if(!(Test-Path -LiteralPath $languageFile)){
    $languagePartial=$languageFile+'.download-'+[Guid]::NewGuid().ToString('N')
    Invoke-WebRequest -Uri ('https://resources.download.minecraft.net/f8/'+$languageHash) -OutFile $languagePartial -UseBasicParsing
    if((Get-FileHash -LiteralPath $languagePartial -Algorithm SHA1).Hash -ne $languageHash){throw 'Minecraft zh_cn download checksum mismatch; partial file retained.'}
    Move-Item -LiteralPath $languagePartial -Destination $languageFile
}
if((Get-FileHash -LiteralPath $languageFile -Algorithm SHA1).Hash -ne $languageHash){throw 'Existing Minecraft zh_cn checksum mismatch; file retained.'}
Write-Host 'Verified official Minecraft 1.21.1 Simplified Chinese language data.'
& python (Join-Path $PSScriptRoot 'prepare_item_icons.py')
if($LASTEXITCODE -ne 0){throw 'Item icon preparation failed.'}

$nativeBuild=Join-Path $projectRoot 'build\world-builder\cdmodkit.asi'
if(!(Test-Path -LiteralPath $nativeBuild -PathType Leaf)){
    $nativeArtifact=Join-Path $projectRoot 'artifacts\native\cdmodkit.asi'
    if(Test-Path -LiteralPath $nativeArtifact -PathType Leaf){
        New-Item -ItemType Directory -Path (Split-Path $nativeBuild -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $nativeArtifact -Destination $nativeBuild
        Write-Host 'Copied the published native adapter into the local build directory.'
    } elseif(-not $SourceBuild){
        throw 'Missing artifacts/native/cdmodkit.asi. Obtain the published artifact or use -SourceBuild and build the native adapter.'
    }
}

$serverRoot=Join-Path $projectRoot 'runtime\minecraft-server'
New-Item -ItemType Directory -Path $serverRoot -Force | Out-Null
$properties=Join-Path $serverRoot 'server.properties'
if(!(Test-Path -LiteralPath $properties)){
    Copy-Item -LiteralPath (Join-Path $projectRoot 'config\minecraft-server.properties') -Destination $properties
    Write-Host 'Created the local server configuration; existing configurations and saves are preserved.'
}
$eulaPath=Join-Path $serverRoot 'eula.txt'
if(!(Test-Path -LiteralPath $eulaPath)){
    if($AcceptMinecraftEula){
        [IO.File]::WriteAllText($eulaPath,"# Accepted by the user through -AcceptMinecraftEula.`neula=true`n",[Text.UTF8Encoding]::new($false))
        Write-Host 'Recorded Minecraft EULA acceptance for this local installation.'
    } else {
        Write-Warning 'Read https://www.minecraft.net/eula and, if you agree, rerun with -AcceptMinecraftEula before starting the server. No acceptance has been recorded.'
    }
} elseif((Get-Content -LiteralPath $eulaPath -Raw) -notmatch '(?m)^\s*eula\s*=\s*true\s*$'){
    Write-Warning 'An existing EULA file has not accepted the EULA. It was preserved; review https://www.minecraft.net/eula and edit that file yourself if you agree.'
}

function Invoke-PinnedGit([string]$Repository,[string[]]$GitArguments){
    $result=& git -C $Repository @GitArguments 2>&1
    if($LASTEXITCODE){throw "Git failed in $Repository`: $($result -join [Environment]::NewLine)"}
    return ($result -join [Environment]::NewLine)
}

function New-PinnedCheckout([string]$Repository,[string]$Url,[string]$Commit){
    if(Test-Path -LiteralPath $Repository){throw "Existing checkout retained: $Repository. Move it aside before preparing a fresh source checkout."}
    New-Item -ItemType Directory -Path $Repository | Out-Null
    Invoke-PinnedGit $Repository @('init','--quiet') | Out-Null
    Invoke-PinnedGit $Repository @('remote','add','origin',$Url) | Out-Null
    Invoke-PinnedGit $Repository @('fetch','--quiet','--depth=1','origin',$Commit) | Out-Null
    Invoke-PinnedGit $Repository @('checkout','--quiet','--detach','FETCH_HEAD') | Out-Null
}

if($SourceBuild){
    if(!(Get-Command git -ErrorAction SilentlyContinue)){throw 'Install Git before requesting -SourceBuild.'}
    $vendorRoot=Join-Path $projectRoot 'vendor'
    $upstream=Join-Path $vendorRoot 'world-builder'
    $patchRoot=Join-Path $projectRoot 'red-side-patches'
    $worldCommit='4dcedc8dfe1592fdee0528894389221291900b8d'
    $minhookCommit='9fbd087432700d73fc571118d6a9697a36443d88'
    $imguiCommit='f401021d5a5d56fe2304056c391e78f81c8d4b8f'
    if(Test-Path -LiteralPath $upstream){
        $prepared=$false
        try {
            $prepared=(Invoke-PinnedGit $upstream @('rev-parse','HEAD')).Trim() -eq $worldCommit
            $prepared=$prepared -and ((Invoke-PinnedGit (Join-Path $upstream 'tools\minhook') @('rev-parse','HEAD')).Trim() -eq $minhookCommit)
            $prepared=$prepared -and ((Invoke-PinnedGit (Join-Path $upstream 'tools\imgui') @('rev-parse','HEAD')).Trim() -eq $imguiCommit)
            foreach($name in @('mc_panel.cpp','mc_panel.h','mc_inventory_ui.cpp','mc_inventory_ui.h','mc_inventory_protocol.h','mc_hotbar_layout.h')){
                $prepared=$prepared -and ((Get-FileHash -LiteralPath (Join-Path $patchRoot $name)).Hash -eq (Get-FileHash -LiteralPath (Join-Path $upstream ('asi\cdmodkit\'+$name))).Hash)
            }
            Invoke-PinnedGit $upstream @('apply','--reverse','--check',(Join-Path $patchRoot 'upstream.patch')) | Out-Null
        } catch {$prepared=$false}
        if(!$prepared){throw "Existing vendor checkout is not the expected prepared source: $upstream. It was retained. Use a fresh project clone or move this vendor checkout aside before retrying -SourceBuild."}
        Write-Host 'Using the existing pinned and patched source checkout; no vendor files were changed.'
    } else {
        New-Item -ItemType Directory -Path $vendorRoot -Force | Out-Null
        New-PinnedCheckout $upstream 'https://github.com/Moon-yungg/crimson-desert-world-builder.git' $worldCommit
        New-PinnedCheckout (Join-Path $upstream 'tools\minhook') 'https://github.com/TsudaKageyu/minhook.git' $minhookCommit
        New-PinnedCheckout (Join-Path $upstream 'tools\imgui') 'https://github.com/ocornut/imgui.git' $imguiCommit
        Invoke-PinnedGit $upstream @('apply',(Join-Path $patchRoot 'upstream.patch')) | Out-Null
        foreach($name in @('mc_panel.cpp','mc_panel.h','mc_inventory_ui.cpp','mc_inventory_ui.h','mc_inventory_protocol.h','mc_hotbar_layout.h')){
            Copy-Item -LiteralPath (Join-Path $patchRoot $name) -Destination (Join-Path $upstream 'asi\cdmodkit')
        }
        Write-Host 'Prepared the pinned World Builder, MinHook, ImGui, and prototype patches.'
    }
    Write-Host 'Native compilation requires Python 3 and the MSYS2 UCRT64 compiler at C:/msys64/ucrt64/bin; run python tools/build_worldbuilder.py.'
}
Write-Host 'Local environment prepared. Existing saves, server configuration, EULA files, and native builds were retained.'
