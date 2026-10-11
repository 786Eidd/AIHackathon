#!/usr/bin/env bash
# Installs NexGen on a Raspberry Pi (64-bit Raspberry Pi OS, Bookworm or newer)
# from a fresh git clone, and registers it as a service that starts on boot.
#
#   git clone https://github.com/786Eidd/AIHackathon.git ~/nexgen
#   cd ~/nexgen && bash deploy/pi-install.sh
#
# Things that are not kept in git are created here: the dashboard is built
# from source, and the object-detection model is downloaded from Ultralytics.
# Enrolled faces are not transferred; enrol people again from the dashboard.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/next-gen-backend"
FRONTEND="$ROOT/nextgen-frontend"
SERVICE=/etc/systemd/system/nexgen.service
RUN_AS="${SUDO_USER:-$USER}"
WEAPON_MODEL="$BACKEND/storage/models/weapon_detector.pt"

if [ "$(uname -m)" != "aarch64" ]; then
    echo "This needs the 64-bit Raspberry Pi OS (found: $(uname -m))."
    exit 1
fi

echo "[1/6] System packages"
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    python3-venv python3-dev ffmpeg libgl1 libglib2.0-0 nodejs npm

echo "[2/6] Python environment (the first run downloads PyTorch; allow 15-30 minutes)"
cd "$BACKEND"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "[3/6] Settings"
if [ ! -f .env ]; then
    cp "$ROOT/deploy/pi.env" .env
    echo "      Created next-gen-backend/.env from the Pi preset."
else
    echo "      Keeping the existing next-gen-backend/.env."
fi
mkdir -p storage/models

echo "[4/6] Object-detection model"
if [ ! -f "$WEAPON_MODEL" ]; then
    # Official YOLO11s weights (about 19 MB), fetched by the ultralytics
    # package from its own release page.
    TMP_DIR="$(mktemp -d)"
    (cd "$TMP_DIR" && "$BACKEND/.venv/bin/python" -c "from ultralytics import YOLO; YOLO('yolo11s.pt')")
    mv "$TMP_DIR/yolo11s.pt" "$WEAPON_MODEL"
    rm -rf "$TMP_DIR"
    echo "      Downloaded to storage/models/weapon_detector.pt"
else
    echo "      Already present."
fi

echo "[5/6] Dashboard"
if [ ! -f "$FRONTEND/dist/index.html" ]; then
    cd "$FRONTEND"
    npm install --no-audit --no-fund
    npm run build
else
    echo "      Already built."
fi

echo "[6/6] Service"
sudo tee "$SERVICE" >/dev/null <<UNIT
[Unit]
Description=NexGen AI Surveillance
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_AS
WorkingDirectory=$BACKEND
ExecStart=$BACKEND/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=40

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable nexgen.service
sudo systemctl restart nexgen.service

ADDRESS="$(hostname -I | awk '{print $1}')"
echo
echo "NexGen is starting. In about a minute, open:  http://$ADDRESS:8000"
echo "Logs:     journalctl -u nexgen -f"
echo "Restart:  sudo systemctl restart nexgen"
echo "Update:   cd $ROOT && git pull && rm -rf nextgen-frontend/dist && bash deploy/pi-install.sh"
