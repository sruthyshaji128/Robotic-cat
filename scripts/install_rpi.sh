#!/usr/bin/env bash
# scripts/install_rpi.sh
# Run this script ON THE RASPBERRY PI to install all dependencies
# and set up the weed robot to auto-start on boot.
#
# Usage (on RPi):
#   cd ~/weed-robot
#   bash scripts/install_rpi.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "╔══════════════════════════════════════════════╗"
echo "║     Weed Robot — Raspberry Pi 4 Installer    ║"
echo "╚══════════════════════════════════════════════╝"

# ── 1. System packages ─────────────────────────────────────────
echo ""
echo "► Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    libopencv-dev \
    python3-opencv \
    libatlas-base-dev \
    libjpeg-dev \
    libopenjp2-7 \
    i2c-tools \
    raspi-gpio \
    git \
    wget

# ── 2. Python virtual environment ──────────────────────────────
echo ""
echo "► Setting up Python virtual environment..."
cd "$PROJECT_DIR"
python3 -m venv .venv
source .venv/bin/activate

# ── 3. Python packages ─────────────────────────────────────────
echo ""
echo "► Installing Python dependencies..."
pip install --upgrade pip wheel
pip install -r requirements_rpi.txt

# ── 4. Download default model ──────────────────────────────────
echo ""
echo "► Downloading base YOLO model..."
python models/download_model.py

# ── 5. Enable camera interface ─────────────────────────────────
echo ""
echo "► Enabling camera interface..."
# USB cameras don't need raspi-config, but enable legacy camera just in case
sudo raspi-config nonint do_camera 0 2>/dev/null || echo "  Camera config skipped (not needed for USB)."

# ── 6. Set config.py for real hardware ─────────────────────────
echo ""
echo "► Configuring for Raspberry Pi hardware mode..."
sed -i 's/^SIMULATE = True/SIMULATE = False/' config.py
echo "  SIMULATE = False  (set in config.py)"

# ── 7. Systemd service ─────────────────────────────────────────
echo ""
echo "► Installing systemd service for auto-start..."
USERNAME=$(whoami)
SERVICE_CONTENT="[Unit]
Description=Weed Detection & Removal Robot
After=network.target

[Service]
Type=simple
User=${USERNAME}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/.venv/bin/python ${PROJECT_DIR}/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"

echo "$SERVICE_CONTENT" | sudo tee /etc/systemd/system/weed-robot.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable weed-robot.service

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║           Installation Complete! ✅           ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Manual start  : source .venv/bin/activate && python main.py --dashboard"
echo "Service start : sudo systemctl start weed-robot"
echo "Service logs  : sudo journalctl -u weed-robot -f"
echo "Dashboard     : http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "⚠️  IMPORTANT: Review config.py and set correct GPIO pin numbers!"
echo "   ARM_GPIO_EXTEND_PIN  = GPIO pin to extend actuator"
echo "   ARM_GPIO_RETRACT_PIN = GPIO pin to retract actuator"
