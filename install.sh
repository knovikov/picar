#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_USER="${SUDO_USER:-$USER}"

echo "Installing KidBot from $REPO_DIR"

sudo apt-get update
sudo apt-get install -y \
  git \
  python3-pip \
  python3-venv \
  python3-pygame \
  python3-opencv \
  python3-picamera2 \
  espeak-ng \
  bluetooth \
  bluez \
  network-manager \
  joystick \
  alsa-utils \
  ffmpeg

sudo systemctl enable --now NetworkManager || true
sudo systemctl enable --now bluetooth || true
sudo usermod -aG bluetooth,input "$SERVICE_USER" || true
if command -v rfkill >/dev/null 2>&1; then
  sudo rfkill unblock bluetooth || true
fi

cd "$REPO_DIR"
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

mkdir -p photos logs assets/sounds assets/music assets/stories
touch .env
chmod 600 .env
python3 tools/generate_sample_audio.py

sudo cp systemd/kidbot.service /etc/systemd/system/kidbot.service
sudo cp systemd/kidbot-updater.service /etc/systemd/system/kidbot-updater.service
sudo cp systemd/kidbot-updater.timer /etc/systemd/system/kidbot-updater.timer

sudo sed -i "s|__KIDBOT_DIR__|$REPO_DIR|g" /etc/systemd/system/kidbot.service /etc/systemd/system/kidbot-updater.service
sudo sed -i "s|__KIDBOT_USER__|$SERVICE_USER|g" /etc/systemd/system/kidbot.service /etc/systemd/system/kidbot-updater.service

sudo systemctl daemon-reload
sudo systemctl enable kidbot.service
sudo systemctl enable --now kidbot-updater.timer

NMCLI_PATH="$(command -v nmcli || true)"
if [[ -n "$NMCLI_PATH" ]]; then
  echo "$SERVICE_USER ALL=(root) NOPASSWD: $NMCLI_PATH" | sudo tee /etc/sudoers.d/kidbot-network >/dev/null
  sudo chmod 440 /etc/sudoers.d/kidbot-network
fi

BLUETOOTHCTL_PATH="$(command -v bluetoothctl || true)"
if [[ -n "$BLUETOOTHCTL_PATH" ]]; then
  echo "$SERVICE_USER ALL=(root) NOPASSWD: $BLUETOOTHCTL_PATH" | sudo tee /etc/sudoers.d/kidbot-bluetooth >/dev/null
  sudo chmod 440 /etc/sudoers.d/kidbot-bluetooth
fi

SYSTEMCTL_PATH="$(command -v systemctl || true)"
if [[ -n "$SYSTEMCTL_PATH" ]]; then
  echo "$SERVICE_USER ALL=(root) NOPASSWD: $SYSTEMCTL_PATH restart kidbot.service" | sudo tee /etc/sudoers.d/kidbot-service >/dev/null
  sudo chmod 440 /etc/sudoers.d/kidbot-service
fi

echo "KidBot installed."
echo "Start now with: sudo systemctl start kidbot.service"
