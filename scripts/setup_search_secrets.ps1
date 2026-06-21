param(
    [string]$PerplexityBaseUrl = "https://api.perplexity.ai",
    [string]$PerplexityModel = "sonar",
    [ValidateSet("Global", "Project")]
    [string]$Scope = "Global",
    [string]$EnvPath = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $EnvPath) {
    if ($Scope -eq "Global") {
        $ToolsRoot = Split-Path -Parent (Split-Path -Parent $ProjectRoot)
        $EnvPath = Join-Path $ToolsRoot "secrets\llm.env"
    } else {
        $EnvPath = Join-Path $ProjectRoot ".env.local"
    }
}
$EnvDir = Split-Path -Parent $EnvPath

Write-Host "Configure local search provider secrets" -ForegroundColor Cyan
Write-Host "Target: $EnvPath"
Write-Host "Scope: $Scope"
Write-Host "This file must stay outside git commits."

$secureKey = Read-Host "Enter Perplexity API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if (-not $apiKey -or $apiKey.Trim().Length -lt 10) {
    throw "API key looks empty or too short."
}

New-Item -ItemType Directory -Path $EnvDir -Force | Out-Null
$existing = @()
if (Test-Path $EnvPath) {
    $existing = Get-Content -Path $EnvPath -Encoding UTF8 |
        Where-Object {
            $_ -notmatch '^\s*PERPLEXITY_API_KEY=' -and
            $_ -notmatch '^\s*PERPLEXITY_BASE_URL=' -and
            $_ -notmatch '^\s*PERPLEXITY_MODEL='
        }
}

$content = @($existing) + @(
    "PERPLEXITY_API_KEY=$($apiKey.Trim())",
    "PERPLEXITY_BASE_URL=$PerplexityBaseUrl",
    "PERPLEXITY_MODEL=$PerplexityModel"
)

Set-Content -Path $EnvPath -Value $content -Encoding UTF8

Write-Host "Saved local search secrets." -ForegroundColor Green
Write-Host "Base URL: $PerplexityBaseUrl"
Write-Host "Model: $PerplexityModel"
Write-Host "Next: python scripts/check_search_config.py"
