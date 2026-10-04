param([Parameter(Mandatory)][string]$WorkDirectory)
$ErrorActionPreference = 'Stop'
$oldNuget = $env:NUGET_PACKAGES
$oldResolver = $env:MSBuildEnableWorkloadResolver
if (Test-Path -LiteralPath $WorkDirectory) { throw 'Use an empty, task-owned build directory.' }
git clone --depth 1 --branch v2.6.5.5623 https://github.com/Prowlarr/Prowlarr.git $WorkDirectory
if ($LASTEXITCODE) { throw 'Clone failed' }
Push-Location $WorkDirectory
try {
    if ((git rev-parse HEAD) -ne '12c327808314a7cae1b7301935ee10cabc19609f') { throw 'Upstream source changed' }
    git apply "$PSScriptRoot/queue-wait.patch"
    if ($LASTEXITCODE) { throw 'Patch rejected' }
    Copy-Item "$PSScriptRoot/FlareSolverrQueueFixture.cs" 'src/NzbDrone.Core.Test/IndexerTests/'
    $env:NUGET_PACKAGES = Join-Path $WorkDirectory 'packages'
    $env:MSBuildEnableWorkloadResolver = 'false'
    & 'C:/Program Files/dotnet/dotnet.exe' test src/NzbDrone.Core.Test/Prowlarr.Core.Test.csproj `
        --filter FullyQualifiedName~FlareSolverrQueueFixture -c Release `
        -p:AssemblyVersion=2.6.5.5623 -p:RuntimeIdentifiers=win-x64 `
        "-p:SolutionDir=$WorkDirectory/src/" -m:2 --nologo
    if ($LASTEXITCODE) { throw 'Focused build or verification failed' }
    Get-FileHash '_output/net8.0/Prowlarr.Core.dll' -Algorithm SHA256
} finally {
    $env:NUGET_PACKAGES = $oldNuget
    $env:MSBuildEnableWorkloadResolver = $oldResolver
    Pop-Location
}
