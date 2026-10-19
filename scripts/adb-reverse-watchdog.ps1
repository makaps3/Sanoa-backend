# adb-reverse-watchdog.ps1
#
# Keeps `adb reverse tcp:8101 tcp:8101` alive for the connected phone.
# Run this in a side terminal during dev: the phone hits
# http://127.0.0.1:8101 and the bytes get forwarded down USB to
# Django on the PC. If the mapping drops (phone unplug, reboot, adb
# restart, USB hiccup), the watchdog re-applies it within ~3 seconds.
#
#   PS> .\scripts\adb-reverse-watchdog.ps1
#   PS> .\scripts\adb-reverse-watchdog.ps1 -Port 9000    # override
#
# Ctrl+C to stop. Safe to leave running indefinitely.

param(
    [int]$Port = 8101,
    [int]$IntervalSeconds = 3,
    [string]$AdbPath = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
)

if (-not (Test-Path $AdbPath)) {
    Write-Host "adb not found at $AdbPath" -ForegroundColor Red
    Write-Host "Pass -AdbPath '<full path>' if installed elsewhere." -ForegroundColor Yellow
    exit 1
}

$mapping = "tcp:$Port"
$expected = "$mapping $mapping"

Write-Host "Watching adb reverse $expected (Ctrl+C to stop)" -ForegroundColor Cyan

$lastState = $null
while ($true) {
    $devices = & $AdbPath devices 2>$null | Select-String "device$"
    if (-not $devices) {
        if ($lastState -ne 'no-device') {
            Write-Host ("[{0}] no device connected" -f (Get-Date -Format HH:mm:ss)) -ForegroundColor Yellow
            $lastState = 'no-device'
        }
        Start-Sleep -Seconds $IntervalSeconds
        continue
    }

    $current = & $AdbPath reverse --list 2>$null
    $hasMapping = $current | Select-String -SimpleMatch $expected

    if (-not $hasMapping) {
        & $AdbPath reverse $mapping $mapping | Out-Null
        Write-Host ("[{0}] reapplied: {1}" -f (Get-Date -Format HH:mm:ss), $expected) -ForegroundColor Green
        $lastState = 'reapplied'
    }
    elseif ($lastState -ne 'ok') {
        Write-Host ("[{0}] ok: {1}" -f (Get-Date -Format HH:mm:ss), $expected) -ForegroundColor DarkGray
        $lastState = 'ok'
    }

    Start-Sleep -Seconds $IntervalSeconds
}
