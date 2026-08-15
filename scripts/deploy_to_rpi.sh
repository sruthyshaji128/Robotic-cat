#!/usr/bin/env bash
# scripts/deploy_to_rpi.sh
# Deploys the weed-robot project to a Raspberry Pi 4 over SSH.
#
# Usage:
#   chmod +x scripts/deploy_to_rpi.sh
#   ./scripts/deploy_to_rpi.sh <rpi-ip> [rpi-user]
#
# Example:
#   ./scripts/deploy_to_rpi.sh 192.168.1.42 pi

set -e

RPi_IP="${1:-weedfinder.local}"
RPi_USER="${2:-rpi}"
REMOTE_DIR="/home/${RPi_USER}/weed-robot"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "╔══════════════════════════════════════════════╗"
echo "║       Weed Robot — RPi Deployment Tool       ║"
echo "╚══════════════════════════════════════════════╝"
echo "  Source : $LOCAL_DIR"
echo "  Target : ${RPi_USER}@${RPi_IP}:${REMOTE_DIR}"
echo ""

# Test SSH connectivity
echo "► Testing SSH connection..."
ssh -o ConnectTimeout=10 "${RPi_USER}@${RPi_IP}" "echo '  SSH OK'" || {
    echo "ERROR: Cannot connect to RPi at ${RPi_IP}"
    echo "Ensure:"
    echo "  1. RPi is powered on and on same network"
    echo "  2. SSH is enabled (raspi-config → Interfaces → SSH)"
    exit 1
}

# Create remote directory
echo "► Creating remote directory..."
ssh "${RPi_USER}@${RPi_IP}" "mkdir -p ${REMOTE_DIR}"

# Sync files (exclude heavy/unnecessary items)
echo "► Syncing files..."
rsync -avz --progress \
    --exclude ".git/" \
    --exclude "__pycache__/" \
    --exclude "*.pyc" \
    --exclude "train/raw/" \
    --exclude "train/runs/" \
    --exclude "*.zip" \
    --exclude ".venv/" \
    --exclude "venv/" \
    --exclude "logs/" \
    "${LOCAL_DIR}/" "${RPi_USER}@${RPi_IP}:${REMOTE_DIR}/"

echo ""
echo "► Deployment complete! ✅"
echo ""
echo "Next steps on the Raspberry Pi:"
echo "  ssh ${RPi_USER}@${RPi_IP}"
echo "  cd ${REMOTE_DIR}"
echo "  bash scripts/install_rpi.sh"
echo "  python main.py --dashboard"
