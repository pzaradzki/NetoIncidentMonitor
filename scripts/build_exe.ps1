param(
    [Parameter(Mandatory = $true)][string]$DashboardParameters,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$Python,
    [string]$Wheelhouse,
    [string]$BrowserCache
)

$ErrorActionPreference = 'Stop'
$resolvePath = $ExecutionContext.SessionState.Path
$buildArguments = @('--dashboard-parameters', $resolvePath.GetUnresolvedProviderPathFromPSPath($DashboardParameters),
                    '--output', $resolvePath.GetUnresolvedProviderPathFromPSPath($OutputDirectory))
if ($Wheelhouse) {
    $buildArguments += @('--wheelhouse', $resolvePath.GetUnresolvedProviderPathFromPSPath($Wheelhouse))
}
if ($BrowserCache) {
    $buildArguments += @('--browser-cache', $resolvePath.GetUnresolvedProviderPathFromPSPath($BrowserCache))
}
if ($Python) {
    $Python = $resolvePath.GetUnresolvedProviderPathFromPSPath($Python)
}
Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    if ($Python) {
        & $Python -E -s -B -m tools.build_package @buildArguments
    } else {
        & py -3.12 -E -s -B -m tools.build_package @buildArguments
    }
    $buildExit = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $buildExit
