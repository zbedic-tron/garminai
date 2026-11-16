# GarminAI Public v1.1.7: Install SYNTHETIC-only D1->MCP->Neon bridge lab.
# Existing Cloudflare Workers Free account + D1 only; NO new D1, NO Garmin API,
# NO Render configuration mutations, NO writes of any secrets to disk.
[CmdletBinding()]
param([switch]$Deploy)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-SafeWrangler {
    param([string]$Stage, [string[]]$CliArgs, [AllowNull()][string]$StdinLine=$null)
    if (-not $CliArgs -or $CliArgs.Count -eq 0) { throw "$Stage missing arguments" }
    foreach($arg in $CliArgs) {
        if ($arg -notmatch '^[a-zA-Z0-9_.:/-]+$') { throw "$Stage invalid CLI argument" }
    }
    $startInfo=New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName='cmd.exe'
    $startInfo.Arguments='/d /s /c "npx.cmd --yes wrangler ' + ($CliArgs -join ' ') + '"'
    $startInfo.WorkingDirectory=(Get-Location).Path
    $startInfo.UseShellExecute=$false
    $startInfo.CreateNoWindow=$true
    $startInfo.RedirectStandardInput=$true
    $startInfo.RedirectStandardOutput=$true
    $startInfo.RedirectStandardError=$true
    $process=New-Object System.Diagnostics.Process
    $process.StartInfo=$startInfo
    try {
        if (-not $process.Start()) { throw "$Stage could not start Wrangler" }
        $stdoutTask=$process.StandardOutput.ReadToEndAsync()
        $stderrTask=$process.StandardError.ReadToEndAsync()
        if ($null -ne $StdinLine) { $process.StandardInput.WriteLine($StdinLine) }
        $process.StandardInput.Close()
        $process.WaitForExit()
        $out=$stdoutTask.GetAwaiter().GetResult()
        $err=$stderrTask.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) {
            $safe=($out+[Environment]::NewLine+$err).Trim()
            if ($safe.Length -gt 1400) { $safe=$safe.Substring(0,1400)+' [truncated]' }
            throw "$Stage FAILED (Wrangler exit $($process.ExitCode)): $safe"
        }
        return [string]($out+[Environment]::NewLine+$err)
    } finally { $process.Dispose() }
}

if (-not $Deploy) { throw 'Use -Deploy only after reviewing V117_START_HERE_SR.md' }
if ((Read-Host 'Confirm WORKERS FREE only. Type FREE') -cne 'FREE') { throw 'Cancelled: no changes' }
if ((Read-Host 'Confirm NO REAL GARMIN DATA. Type SYNTHETIC') -cne 'SYNTHETIC') { throw 'Cancelled: no changes' }
if (-not (Get-Command npx.cmd -ErrorAction SilentlyContinue)) { throw 'Node/npm npx.cmd unavailable' }
if (-not (Get-Command Set-Clipboard -ErrorAction SilentlyContinue)) { throw 'Windows clipboard API unavailable. No secrets created.' }
$folder=Split-Path -Parent $MyInvocation.MyCommand.Path
$cfg=Join-Path $folder 'wrangler.toml'
if (-not (Test-Path -LiteralPath $cfg)) { throw 'STOP: missing existing wrangler.toml. Do not create another D1.' }
foreach($name in @('worker.mjs','bridge_v117.mjs','schema_bridge_v117.sql')) {
    if (-not (Test-Path -LiteralPath (Join-Path $folder $name))) { throw "STOP: missing $name" }
}
$raw=Get-Content -LiteralPath $cfg -Raw
$uuid='[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
if (($raw -notmatch ('(?m)^\s*database_id\s*=\s*"'+$uuid+'"\s*$')) -or
    ($raw -notmatch '(?m)^\s*name\s*=\s*"garminai-synthetic-edge-v116"\s*$') -or
    ($raw -notmatch '(?m)^\s*database_name\s*=\s*"garminai-synthetic-edge-v116"\s*$') -or
    ($raw -notmatch '(?m)^\s*main\s*=\s*"worker.mjs"\s*$') -or
    ($raw -notmatch '(?m)^\s*LAB_SYNTHETIC_ONLY\s*=\s*"1"\s*$')) {
    throw 'STOP: unexpected existing Cloudflare lab configuration. No changes.'
}

$stage='Initialization'
$token=$null
Push-Location $folder
try {
    $stage='Login validation'
    Write-Host 'Checking existing Cloudflare login...'
    $null=Invoke-SafeWrangler -Stage $stage -CliArgs @('whoami')
    $stage='Existing D1 schema'
    Write-Host 'Installing v117 synthetic table in EXISTING D1 (idempotent)...'
    $null=Invoke-SafeWrangler -Stage $stage -CliArgs @('d1','execute','garminai-synthetic-edge-v116','--remote','--file','schema_bridge_v117.sql','--yes')
    $stage='Worker deploy'
    Write-Host 'Deploying synthetic-only bridge Worker (existing name and D1 binding)...'
    $deployment=Invoke-SafeWrangler -Stage $stage -CliArgs @('deploy')
    if ($deployment -notmatch 'https://garminai-synthetic-edge-v116\.zbedic\.workers\.dev') {
        throw 'Unexpected workers.dev URL; stop and inspect Cloudflare Dashboard.'
    }
    $stage='Bridge secret'
    $random=New-Object byte[] 32
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($random) } finally { $rng.Dispose() }
    $token=[Convert]::ToBase64String($random).TrimEnd('=').Replace('+','-').Replace('/','_')
    [Array]::Clear($random,0,$random.Length)
    Write-Host 'Installing a NEW separate BRIDGE_TOKEN (existing LAB_TOKEN preserved)...'
    $null=Invoke-SafeWrangler -Stage $stage -CliArgs @('secret','put','BRIDGE_TOKEN') -StdinLine $token
    $stage='Clipboard'
    # Operator pastes into Render Environment; never echo the secret or write a file.
    Set-Clipboard -Value $token
    Write-Host 'Bridge secret copied to Windows clipboard. PASTE into Render GARMINAI_EDGE_BRIDGE_TOKEN.'
    $stage='Bridge status verification'
    Write-Host 'Checking Worker bridge status (no real Garmin messages)...'
    $ok=$false
    for($i=1;$i -le 45;$i++){
        try{
            $v=Invoke-RestMethod -Uri 'https://garminai-synthetic-edge-v116.zbedic.workers.dev/_lab/bridge/status' -TimeoutSec 15 -ErrorAction Stop
            if ($v.version -eq '1.1.7' -and $v.bridge_enabled -eq $true -and
                $v.real_garmin_push_enabled -eq $false -and $v.neon_connected_from_edge -eq $false){$ok=$true;break}
        }catch { }
        if($i -lt 45){Start-Sleep -Seconds 2}
    }
    if (-not $ok) { throw 'Bridge status not ready. Secret is in clipboard; inspect Cloudflare, do not recreate DB.' }
    Write-Host '--- SAFE STATUS: Bridge Worker + D1 schema deployed, Garmin push remains OFF ---'
    Write-Host 'bridge_version: 1.1.7'
    Write-Host 'bridge_enabled: true'
    Write-Host 'bridge_url: https://garminai-synthetic-edge-v116.zbedic.workers.dev'
    Write-Host 'PASTE clipboard into Render Environment: GARMINAI_EDGE_BRIDGE_TOKEN'
    Write-Host 'Set GARMINAI_EDGE_BRIDGE_URL=https://garminai-synthetic-edge-v116.zbedic.workers.dev'
    Write-Host 'Set GARMINAI_EDGE_BRIDGE_STAGING_ENABLED=1 only for the authorized test'
    Write-Host 'Keep GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=0 and all Garmin endpoints DISABLED'
    Write-Host 'After the MCP test, set GARMINAI_EDGE_BRIDGE_STAGING_ENABLED=0, then clear clipboard.'
    Write-Host 'Do not run this setup again unless intentionally rotating BRIDGE_TOKEN.'
} catch {
    Write-Host "STOP at stage: $stage"
    Write-Host ("Reason: "+$_.Exception.Message)
    throw
} finally {
    $token=$null
    Pop-Location
}
