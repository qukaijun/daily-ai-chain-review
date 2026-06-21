# Installs a Windows Task Scheduler job for the daily AI chain review.
param(
    [string]$TaskName = "Daily AI Chain Review",
    [string]$At = "18:30",
    [switch]$NoFetchMarket
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Runner = Join-Path $RepoRoot "scripts\run_daily_review.py"
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue

if (-not $PythonCommand) {
    throw "python was not found on PATH"
}

$Arguments = "`"$Runner`""
if ($NoFetchMarket) {
    $Arguments = "$Arguments --no-fetch-market"
}

$Action = New-ScheduledTaskAction -Execute $PythonCommand.Source -Argument $Arguments -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At $At
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Generate and QA the Daily AI Chain Review after market close." `
    -Force | Out-Null

Write-Host "[OK] Scheduled task installed: $TaskName"
Write-Host "[INFO] Time: weekday $At"
Write-Host "[INFO] Runner: $Runner"
