# GarminAI Public 1.1.8: upgrade EXISTING synthetic-only Workers Free lab.
# Never creates a new D1 database, rotates LAB_TOKEN/BRIDGE_TOKEN, modifies
# Render, enables real Garmin push, or places credentials into source files.
[CmdletBinding()]
param([switch]$Deploy)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

function Invoke-SafeWrangler {
    param([string]$Stage,[string[]]$CliArgs)
    if (-not $CliArgs -or $CliArgs.Count -eq 0) { throw "$Stage: missing arguments" }
    foreach($arg in $CliArgs) {
        if ($arg -notmatch '^[a-zA-Z0-9_.:/-]+$') { throw "$Stage: invalid argument" }
    }
    $si=New-Object System.Diagnostics.ProcessStartInfo
    $si.FileName='cmd.exe'
    $si.Arguments='/d /s /c "npx.cmd --yes wrangler '+($CliArgs -join ' ')+'"'
    $si.WorkingDirectory=(Get-Location).Path
    $si.UseShellExecute=$false
    $si.CreateNoWindow=$true
    $si.RedirectStandardOutput=$true
    $si.RedirectStandardError=$true
    $proc=New-Object System.Diagnostics.Process
    $proc.StartInfo=$si
    try {
        if (-not $proc.Start()) { throw "$Stage: cannot start Wrangler" }
        $outTask=$proc.StandardOutput.ReadToEndAsync()
        $errTask=$proc.StandardError.ReadToEndAsync()
        $proc.WaitForExit()
        $output=$outTask.GetAwaiter().GetResult()
        $errors=$errTask.GetAwaiter().GetResult()
        if ($proc.ExitCode -ne 0) {
            $safe=($output+[Environment]::NewLine+$errors).Trim()
            if ($safe.Length -gt 1100) { $safe=$safe.Substring(0,1100)+' [truncated]' }
            throw "$Stage FAILED: Wrangler exit $($proc.ExitCode): $safe"
        }
        return [string]($output+[Environment]::NewLine+$errors)
    } finally { $proc.Dispose() }
}

if (-not $Deploy) { throw 'Run -Deploy only after reading V118_START_HERE_SR.md' }
if ((Read-Host 'Confirm existing WORKERS FREE, no paid upgrades. Type FREE') -cne 'FREE') {
    throw 'Cancelled before changes'
}
if ((Read-Host 'Confirm SYNTHETIC data ONLY. Type SYNTHETIC') -cne 'SYNTHETIC') {
    throw 'Cancelled before changes'
}
if (-not (Get-Command npx.cmd -ErrorAction SilentlyContinue)) { throw 'npx.cmd unavailable' }
$folder=Split-Path -Parent $MyInvocation.MyCommand.Path
$cfg=Join-Path $folder 'wrangler.toml'
if (-not (Test-Path -LiteralPath $cfg)) { throw 'STOP: existing wrangler.toml is missing. Do not create a new database.' }
foreach($name in @('worker.mjs','bridge_v117.mjs','recovery_v118.mjs','schema_recovery_v118.sql')) {
    if (-not (Test-Path -LiteralPath (Join-Path $folder $name))) { throw "STOP: missing $name" }
}
$raw=Get-Content -LiteralPath $cfg -Raw
$uuid='[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
if (($raw -notmatch ('(?m)^\s*database_id\s*=\s*"'+$uuid+'"\s*$')) -or
    ($raw -notmatch '(?m)^\s*name\s*=\s*"garminai-synthetic-edge-v116"\s*$') -or
    ($raw -notmatch '(?m)^\s*database_name\s*=\s*"garminai-synthetic-edge-v116"\s*$') -or
    ($raw -notmatch '(?m)^\s*main\s*=\s*"worker.mjs"\s*$') -or
    ($raw -notmatch '(?m)^\s*LAB_SYNTHETIC_ONLY\s*=\s*"1"\s*$')) {
    throw 'STOP: unexpected existing Worker/D1 configuration; no changes.'
}

$stage='Init'
Push-Location $folder
try {
    $stage='Cloudflare login'
    Write-Host 'Checking current Cloudflare account (existing login only)...'
    $null=Invoke-SafeWrangler -Stage $stage -CliArgs @('whoami')
    $stage='D1 recovery table'
    Write-Host 'Applying additive v1.1.8 synthetic schema to EXISTING D1...'
    $null=Invoke-SafeWrangler -Stage $stage -CliArgs @('d1','execute','garminai-synthetic-edge-v116','--remote','--file','schema_recovery_v118.sql','--yes')
    $stage='Worker deployment'
    Write-Host 'Deploying recovery-only addition (no secret rotation)...'
    $deployment=Invoke-SafeWrangler -Stage $stage -CliArgs @('deploy')
    if ($deployment -notmatch 'https://garminai-synthetic-edge-v116\.zbedic\.workers\.dev') {
        throw 'Unexpected workers.dev URL. Inspect Cloudflare; do not recreate D1.'
    }
    $stage='Health check'
    Write-Host 'Checking new read-only Recovery status...'
    $ready=$false
    for($attempt=1;$attempt -le 35;$attempt++) {
        try {
            $result=Invoke-RestMethod -Uri 'https://garminai-synthetic-edge-v116.zbedic.workers.dev/_lab/recovery/status' -TimeoutSec 12 -ErrorAction Stop
            if($result.version -eq '1.1.8' -and $result.recovery_enabled -eq $true -and
               $result.real_garmin_push_enabled -eq $false -and
               $result.outbounds_to_neon_or_render -eq $false) { $ready=$true; break }
        } catch { }
        if($attempt -lt 35) { Start-Sleep -Seconds 2 }
    }
    if(-not $ready) { throw 'Recovery status not ready. Preserve existing D1 and BRIDGE_TOKEN.' }
    Write-Host 'PASS: Existing synthetic Cloudflare Worker upgraded to v1.1.8.'
    Write-Host 'BRIDGE_TOKEN and LAB_TOKEN: unchanged; existing D1 kept.'
    Write-Host 'Next: on Render set GARMINAI_EDGE_RECOVERY_STAGING_ENABLED=1 only for the operator-approved test.'
    Write-Host 'Keep GARMINAI_EDGE_BRIDGE_STAGING_ENABLED=0 and Garmin Endpoint Configuration disabled.'
} catch {
    Write-Host "STOP at stage: $stage"
    Write-Host ('Reason: '+$_.Exception.Message)
    throw
} finally { Pop-Location }
