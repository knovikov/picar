#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_USER="${SUDO_USER:-$USER}"
SUNFOUNDER_DIR="${SUNFOUNDER_DIR:-/opt/sunfounder}"

run_as_service_user() {
  if [[ "$(id -un)" == "$SERVICE_USER" ]]; then
    "$@"
  else
    sudo -H -u "$SERVICE_USER" "$@"
  fi
}

clone_or_update_repo() {
  local repo_url="$1"
  local repo_dir="$2"
  local branch="${3:-}"

  if [[ -d "$repo_dir/.git" ]]; then
    if [[ -n "$branch" ]]; then
      run_as_service_user git -C "$repo_dir" fetch origin "$branch" --depth 1 || true
      run_as_service_user git -C "$repo_dir" checkout "$branch" || true
    fi
    run_as_service_user git -C "$repo_dir" pull --ff-only || true
    return
  fi

  if [[ -e "$repo_dir" ]]; then
    echo "ERROR: $repo_dir exists but is not a git checkout." >&2
    exit 1
  fi

  if [[ -n "$branch" ]]; then
    run_as_service_user git clone -b "$branch" "$repo_url" "$repo_dir" --depth 1
  else
    run_as_service_user git clone "$repo_url" "$repo_dir" --depth 1
  fi
}

install_sunfounder_sdk() {
  echo "Installing SunFounder PiCar-X SDK"
  sudo mkdir -p "$SUNFOUNDER_DIR" /opt/picar-x
  sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$SUNFOUNDER_DIR" /opt/picar-x
  sudo chmod 775 /opt/picar-x

  clone_or_update_repo "https://github.com/sunfounder/robot-hat.git" "$SUNFOUNDER_DIR/robot-hat" "2.5.x"
  (cd "$SUNFOUNDER_DIR/robot-hat" && sudo python3 install.py)

  clone_or_update_repo "https://github.com/sunfounder/vilib.git" "$SUNFOUNDER_DIR/vilib"
  (cd "$SUNFOUNDER_DIR/vilib" && sudo python3 install.py)

  clone_or_update_repo "https://github.com/sunfounder/picar-x.git" "$SUNFOUNDER_DIR/picar-x" "2.1.x"
  (cd "$SUNFOUNDER_DIR/picar-x" && sudo python3 -m pip install . --break-system-packages)

  sudo chown -R "$SERVICE_USER:$SERVICE_USER" /opt/picar-x
}

echo "Installing KidBot from $REPO_DIR"

sudo apt-get update
sudo apt-get install -y \
  git \
  python3-pip \
  python3-setuptools \
  python3-smbus \
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

install_sunfounder_sdk

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
sudo chown -R "$SERVICE_USER:$SERVICE_USER" .venv photos logs assets .env

sudo cp systemd/kidbot.service /etc/systemd/system/kidbot.service
sudo cp systemd/kidbot-network-recovery.service /etc/systemd/system/kidbot-network-recovery.service
sudo cp systemd/kidbot-updater.service /etc/systemd/system/kidbot-updater.service
sudo cp systemd/kidbot-updater.timer /etc/systemd/system/kidbot-updater.timer

sudo sed -i "s|__KIDBOT_DIR__|$REPO_DIR|g" /etc/systemd/system/kidbot.service /etc/systemd/system/kidbot-network-recovery.service /etc/systemd/system/kidbot-updater.service
sudo sed -i "s|__KIDBOT_USER__|$SERVICE_USER|g" /etc/systemd/system/kidbot.service /etc/systemd/system/kidbot-network-recovery.service /etc/systemd/system/kidbot-updater.service

sudo systemctl daemon-reload
sudo systemctl enable kidbot-network-recovery.service
sudo systemctl enable kidbot.service
sudo systemctl disable --now kidbot-updater.timer || true

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

CHMOD_PATH="$(command -v chmod || true)"
CHOWN_PATH="$(command -v chown || true)"
if [[ -n "$CHMOD_PATH" && -n "$CHOWN_PATH" ]]; then
  {
    echo "$SERVICE_USER ALL=(root) NOPASSWD: $CHMOD_PATH 777 /opt/picar-x/picar-x.conf"
    echo "$SERVICE_USER ALL=(root) NOPASSWD: $CHOWN_PATH -R $SERVICE_USER\\:$SERVICE_USER /opt/picar-x"
  } | sudo tee /etc/sudoers.d/kidbot-picarx-config >/dev/null
  sudo chmod 440 /etc/sudoers.d/kidbot-picarx-config
fi

echo "KidBot installed."
echo "Start now with: sudo systemctl start kidbot.service"
