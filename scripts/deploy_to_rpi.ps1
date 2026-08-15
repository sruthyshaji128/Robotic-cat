#!/usr/bin/env pwsh
# scripts/deploy_to_rpi.ps1
# Deploys the weed-robot project to a Raspberry Pi over SSH (Windows-native).
#
# Usage:
#   .\scripts\deploy_to_rpi.ps1
#   .\scripts\deploy_to_rpi.ps1 -RpiIp 192.168.1.42 -RpiUser pi

param(
    [string]$RpiIp   = "raspberrypi.local",
    [string]$RpiUser = "pi"
)

$RemoteDir = "/home/$RpiUser/weed-robot"
$ProjectDir = Split-Path $PSScriptRoot -Parent

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    Weed Robot — Windows → RPi Deployer      ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host "  Source : $ProjectDir"
Write-Host "  Target : ${RpiUser}@${RpiIp}:${RemoteDir}"
Write-Host ""

# ── 1. Test SSH connectivity ────────────────────────────────────
Write-Host "► Testing SSH connection..." -ForegroundColor Yellow
$sshTest = ssh -o ConnectTimeout=10 -o BatchMode=yes "${RpiUser}@${RpiIp}" "echo SSH_OK" 2>&1
if ($sshTest -notlike "*SSH_OK*") {
    Write-Host "ERROR: Cannot SSH into the RPi at $RpiIp" -ForegroundColor Red
    Write-Host "Ensure:"
    Write-Host "  1. Raspberry Pi is powered on and connected to the same network"
    Write-Host "  2. SSH is enabled (raspi-config → Interface Options → SSH)"
    Write-Host "  3. Run 'ssh-keygen' and 'ssh-copy-id ${RpiUser}@${RpiIp}' for passwordless SSH"
    exit 1
}
Write-Host "  SSH OK" -ForegroundColor Green

# ── 2. Create remote directory ──────────────────────────────────
Write-Host "► Creating remote project directory..." -ForegroundColor Yellow
ssh "${RpiUser}@${RpiIp}" "mkdir -p ${RemoteDir}"

# ── 3. Files to copy (relative to project root) ─────────────────
Write-Host "► Copying project files..." -ForegroundColor Yellow
$FilesToCopy = @(
    "config.py",
    "main.py",
    "requirements.txt",
    "requirements_rpi.txt",
    "modules",
    "dashboard",
    "models",
    "tests",
    "scripts"
)

foreach ($item in $FilesToCopy) {
    $localPath = Join-Path $ProjectDir $item
    if (Test-Path $localPath) {
        Write-Host "  Copying: $item"
        scp -r "$localPath" "${RpiUser}@${RpiIp}:${RemoteDir}/"
    } else {
        Write-Host "  Skipping: $item (not found)" -ForegroundColor DarkGray
    }
}

# ── 4. Ensure logs dir exists on RPi ───────────────────────────
ssh "${RpiUser}@${RpiIp}" "mkdir -p ${RemoteDir}/logs"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║         Deployment Complete!                 ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps — run these on the Raspberry Pi:" -ForegroundColor Cyan
Write-Host "  ssh ${RpiUser}@${RpiIp}"
Write-Host "  cd ~/weed-robot"
Write-Host ""
Write-Host "  # First time only — install dependencies:"
Write-Host "  bash scripts/install_rpi.sh"
Write-Host ""
Write-Host "  # To run the robot with live camera + dashboard:"
Write-Host "  python main.py"
Write-Host ""
Write-Host "  # Then open in browser (on any device on the same network):"
Write-Host "  http://${RpiIp}:5000"
Write-Host ""
