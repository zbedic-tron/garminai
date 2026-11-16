# GarminAI v1.1.6 Cloudflare Workers Free + D1, SYNTHETIC ONLY.
# Run ONLY after creating/verifying a Cloudflare WORKERS FREE account.
# No Render, Neon, Garmin or real-activity data is used by this script.
[CmdletBinding()]
param([switch]$Deploy)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Stop-IfFailed([string]$Action) {
    if ($LASTEXITCODE -ne 0) { throw "$Action failed (exit code $LASTEXITCODE). No Garmin data was touched." }
}
function Wrangler([string[]]$Arguments) {
    $output = & npx.cmd --yes wrangler @Arguments 2>&1
    $exit = $LASTEXITCODE
    if ($exit -ne 0) {
        $message = ($output | Out-String)
        throw "Wrangler command failed: $($Arguments[0]) $($Arguments[1]); $message"
    }
    return ($output | Out-String)
}
function Lab-Post([string]$Uri,[string]$Token,[string]$Data) {
    $time = [Diagnostics.Stopwatch]::StartNew()
    $code = -1
    $body = ''
    try {
        $resp = Invoke-WebRequest -Uri $Uri -Method POST -ContentType 'application/json' -Headers @{'x-lab-token'=$Token} -Body $Data -UseBasicParsing -TimeoutSec 25
        $code = [int]$resp.StatusCode
        $body = [string]$resp.Content
    } catch {
        $webError = $_.Exception
        if (-not $webError.Response) { throw }
        $code = [int]$webError.Response.StatusCode
        if ($webError.Response.PSObject.Methods.Name -contains 'GetResponseStream') {
            $stream = $webError.Response.GetResponseStream()
            if ($stream) {
                $reader = New-Object IO.StreamReader($stream)
                try { $body = $reader.ReadToEnd() } finally { $reader.Dispose() }
            }
        }
    }
    $time.Stop()
    return [PSCustomObject]@{http=$code;elapsed_ms=$time.ElapsedMilliseconds;body=$body}
}
if (-not $Deploy) {
    Write-Host 'Nothing deployed. To explicitly create test Cloudflare resources, run this script with -Deploy.'
    return
}
$choice = Read-Host 'Confirm your Cloudflare account uses WORKERS FREE (no paid subscriptions). Type FREE to continue'
if ($choice -cne 'FREE') { throw 'Cancelled. No resources created.' }
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) { throw 'Install Node.js 20+ first (free).' }
if (-not (Get-Command npx.cmd -ErrorAction SilentlyContinue)) { throw 'Install Node.js/npm first (free).' }
$nodeVer = (& node.exe --version).Trim('v')
$nodeMajor = [int]($nodeVer.Split('.')[0])
if ($nodeMajor -lt 20) { throw 'Node.js 20+ is required.' }
$cwd = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $cwd
$token = $null
try {
    Write-Host 'Signing in to Cloudflare...'
    & npx.cmd --yes wrangler login
    Stop-IfFailed 'Cloudflare login'
    $dbName='garminai-synthetic-edge-v116'
    Write-Host 'Creating a NEW D1 test database (synthetic-only; Western Europe region hint)...'
    $createOutput = Wrangler -Arguments @('d1','create',$dbName,'--location','weur')
    $uuidPattern='[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
    $match=[regex]::Match($createOutput,$uuidPattern)
    if (-not $match.Success) { throw 'D1 database created but the UUID was not parsed. See Cloudflare dashboard; do not rerun create blindly.' }
    $dbUuid=$match.Value
    $conf = @"
name = "garminai-synthetic-edge-v116"
main = "worker.mjs"
compatibility_date = "2026-11-16"
workers_dev = true

[vars]
LAB_SYNTHETIC_ONLY = "1"

[[d1_databases]]
binding = "LAB_DB"
database_name = "$dbName"
database_id = "$dbUuid"
"@
    # Generated config has no secret. Keep it local, not in public GitHub.
    [IO.File]::WriteAllText((Join-Path $cwd 'wrangler.toml'), $conf, ([System.Text.UTF8Encoding]::new($false)))
    Write-Host 'Creating the D1 synthetic-only table...'
    $null = Wrangler -Arguments @('d1','execute',$dbName,'--remote','--file','schema.sql','--yes')
    Write-Host 'Deploying Worker. Until LAB_TOKEN is set it rejects all writes...'
    $deployOutput = Wrangler -Arguments @('deploy')
    $link=[regex]::Match($deployOutput,'https://[A-Za-z0-9.-]+\.workers\.dev').Value
    if (-not $link) { throw 'Worker deployment succeeded but URL was not parsed. Find it in Cloudflare Workers dashboard.' }
    $random=New-Object byte[] 32
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($random) } finally { $rng.Dispose() }
    $token=[Convert]::ToBase64String($random).TrimEnd('=').Replace('+','-').Replace('/','_')
    # The token is fed directly to Wrangler stdin, not put in a command line, GitHub, logs, or a config file.
    Write-Host 'Configuring LAB_TOKEN as a Cloudflare secret (not displayed)...'
    $null = $token | & npx.cmd --yes wrangler secret put LAB_TOKEN 2>&1
    Stop-IfFailed 'Cloudflare secret storage'
    $endpoint=$link.TrimEnd('/') + '/_lab/synthetic'
    Write-Host 'Testing synthetic D1 inserts over HTTPS. Do NOT send Garmin data here.'
    $uid='SYNTHETIC_V116_' + ([Guid]::NewGuid().ToString('N').Substring(0,24))
    $normal=(@{kind='SYNTHETIC';event_id=$uid;scenario='NORMAL'}|ConvertTo-Json -Compress)
    $different=(@{kind='SYNTHETIC';event_id=$uid;scenario='DUPLICATE'}|ConvertTo-Json -Compress)
    $first=Lab-Post $endpoint $token $normal
    $second=Lab-Post $endpoint $token $normal
    $conflict=Lab-Post $endpoint $token $different
    $result=[PSCustomObject]@{
        version='1.1.6';mode='SYNTHETIC_ONLY';worker_url=$link;
        first_http=$first.http;first_ms=$first.elapsed_ms;
        repeat_http=$second.http;repeat_ms=$second.elapsed_ms;
        conflict_http=$conflict.http;conflict_ms=$conflict.elapsed_ms;
        writes_reported_successful=($first.http -eq 200 -and $second.http -eq 200 -and $conflict.http -eq 409);
        actual_d1_row_count='VERIFY_WITH_WRANGLER_REMOTE_QUERY';garmin_push_enabled=$false;
        real_garmin_data_used=$false
    }
    Write-Host '--- SHARE ONLY THIS SAFE TEST SUMMARY (NEVER THE TOKEN) ---'
    $result | ConvertTo-Json -Depth 3
    Write-Host "Verify remote record: npx wrangler d1 execute $dbName --remote --command 'SELECT COUNT(*) AS total FROM lab_events_v116;'"
    Write-Host 'All Garmin endpoints remain DISABLED. Do not put this Worker URL in Garmin API Tools.'
} finally {
    $token=$null
    Pop-Location
}
