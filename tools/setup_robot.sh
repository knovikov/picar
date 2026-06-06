#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PI_HOST="pi@picar.local"
ROBOT_DIR="/home/pi/picar"
GITHUB_REPO="knovikov/picar"
BRANCH="main"
LOCAL_KEY="$REPO_ROOT/.deploy-keys/picar_robot_ed25519"
GITHUB_HOST_ALIAS="github.com-picar"
DEPLOY_KEY_TITLE="picar-robot"
REBOOT_AFTER="0"
SKIP_GITHUB_KEY="0"

usage() {
  cat <<'EOF'
Usage:
  ./tools/setup_robot.sh [options]

Options:
  --host USER@HOST       Raspberry Pi SSH target. Default: pi@picar.local
  --dir PATH             Robot project path on Raspberry Pi. Default: /home/pi/picar
  --repo OWNER/REPO      GitHub repo. Default: knovikov/picar
  --branch NAME          Git branch to install. Default: main
  --key PATH             Local deploy private key. Default: .deploy-keys/picar_robot_ed25519
  --reboot               Reboot Raspberry Pi after installation.
  --skip-github-key      Do not add/check the deploy key with GitHub CLI.
  -h, --help             Show this help.

The script generates a read-only deploy key if it is missing, copies the private
key to the Raspberry Pi, configures SSH there, clones or updates the private
repo, runs install.sh, and starts kidbot.service.
EOF
}

log() {
  printf '\n==> %s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

require_value() {
  [[ $# -ge 2 && -n "${2:-}" ]] || die "$1 requires a value"
}

abs_path() {
  local value="$1"
  if [[ "$value" == /* ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$REPO_ROOT/$value"
  fi
}

shell_quote() {
  printf '%q' "$1"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      require_value "$@"
      PI_HOST="${2:-}"
      shift 2
      ;;
    --dir)
      require_value "$@"
      ROBOT_DIR="${2:-}"
      shift 2
      ;;
    --repo)
      require_value "$@"
      GITHUB_REPO="${2:-}"
      shift 2
      ;;
    --branch)
      require_value "$@"
      BRANCH="${2:-}"
      shift 2
      ;;
    --key)
      require_value "$@"
      LOCAL_KEY="$(abs_path "${2:-}")"
      shift 2
      ;;
    --reboot)
      REBOOT_AFTER="1"
      shift
      ;;
    --skip-github-key)
      SKIP_GITHUB_KEY="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

[[ -n "$PI_HOST" ]] || die "--host cannot be empty"
[[ -n "$ROBOT_DIR" ]] || die "--dir cannot be empty"
[[ -n "$GITHUB_REPO" ]] || die "--repo cannot be empty"
[[ -n "$BRANCH" ]] || die "--branch cannot be empty"

LOCAL_KEY="$(abs_path "$LOCAL_KEY")"
LOCAL_PUB_KEY="$LOCAL_KEY.pub"
GIT_REMOTE_URL="git@${GITHUB_HOST_ALIAS}:${GITHUB_REPO}.git"
DIRECT_GITHUB_URL="git@github.com:${GITHUB_REPO}.git"

require_cmd ssh
require_cmd scp
require_cmd git
require_cmd ssh-keygen

log "Preparing local deploy key"
mkdir -p "$(dirname "$LOCAL_KEY")"
chmod 700 "$(dirname "$LOCAL_KEY")"
if [[ ! -f "$LOCAL_KEY" ]]; then
  ssh-keygen -t ed25519 -C "picar-robot" -f "$LOCAL_KEY" -N ""
fi
[[ -f "$LOCAL_PUB_KEY" ]] || ssh-keygen -y -f "$LOCAL_KEY" >"$LOCAL_PUB_KEY"
chmod 600 "$LOCAL_KEY"
chmod 644 "$LOCAL_PUB_KEY"

if [[ "$SKIP_GITHUB_KEY" == "0" ]]; then
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    public_key="$(cat "$LOCAL_PUB_KEY")"
    if gh repo deploy-key list --repo "$GITHUB_REPO" | grep -Fq "$public_key"; then
      log "GitHub deploy key already exists: $DEPLOY_KEY_TITLE"
    else
      log "Adding read-only deploy key to GitHub repo $GITHUB_REPO"
      gh repo deploy-key add "$LOCAL_PUB_KEY" --repo "$GITHUB_REPO" --title "$DEPLOY_KEY_TITLE"
    fi
  else
    log "GitHub CLI is not authenticated; expecting the deploy key to already exist on GitHub"
  fi

  log "Checking private repo access with the deploy key"
  GIT_SSH_COMMAND="ssh -i $LOCAL_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
    git ls-remote "$DIRECT_GITHUB_URL" HEAD >/dev/null || die "Deploy key cannot read $DIRECT_GITHUB_URL"
fi

log "Checking Raspberry Pi SSH access: $PI_HOST"
ssh "$PI_HOST" 'mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"'
remote_home="$(ssh "$PI_HOST" 'printf "%s" "$HOME"')"
remote_key_path="$remote_home/.ssh/picar_github"

log "Copying deploy key to Raspberry Pi"
scp "$LOCAL_KEY" "$PI_HOST:$remote_key_path"
ssh "$PI_HOST" "chmod 600 $(shell_quote "$remote_key_path")"

log "Installing or updating Picar on Raspberry Pi"
ssh "$PI_HOST" \
  "ROBOT_DIR=$(shell_quote "$ROBOT_DIR") GIT_REMOTE_URL=$(shell_quote "$GIT_REMOTE_URL") BRANCH=$(shell_quote "$BRANCH") GITHUB_HOST_ALIAS=$(shell_quote "$GITHUB_HOST_ALIAS") REMOTE_KEY_PATH=$(shell_quote "$remote_key_path") REBOOT_AFTER=$(shell_quote "$REBOOT_AFTER") bash -s" <<'REMOTE_SETUP'
set -euo pipefail

log() {
  printf '\n==> %s\n' "$*"
}

log "Writing Raspberry Pi SSH config for GitHub deploy key"
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/config"
tmp_config="$(mktemp)"
awk '
  /^# BEGIN PICAR DEPLOY KEY$/ { skip=1; next }
  /^# END PICAR DEPLOY KEY$/ { skip=0; next }
  skip != 1 { print }
' "$HOME/.ssh/config" >"$tmp_config"
cat "$tmp_config" >"$HOME/.ssh/config"
rm -f "$tmp_config"
cat >>"$HOME/.ssh/config" <<EOF
# BEGIN PICAR DEPLOY KEY
Host $GITHUB_HOST_ALIAS
  HostName github.com
  User git
  IdentityFile $REMOTE_KEY_PATH
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
# END PICAR DEPLOY KEY
EOF
chmod 600 "$HOME/.ssh/config"

log "Checking GitHub access from Raspberry Pi"
git ls-remote "$GIT_REMOTE_URL" HEAD >/dev/null

if [[ -d "$ROBOT_DIR/.git" ]]; then
  log "Updating existing checkout: $ROBOT_DIR"
  cd "$ROBOT_DIR"
  git remote set-url origin "$GIT_REMOTE_URL"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH"
  git branch --set-upstream-to="origin/$BRANCH" "$BRANCH" || true
  git pull --ff-only origin "$BRANCH"
else
  if [[ -e "$ROBOT_DIR" ]]; then
    printf 'ERROR: %s exists but is not a git checkout.\n' "$ROBOT_DIR" >&2
    exit 1
  fi
  log "Cloning $GIT_REMOTE_URL into $ROBOT_DIR"
  mkdir -p "$(dirname "$ROBOT_DIR")"
  git clone --branch "$BRANCH" "$GIT_REMOTE_URL" "$ROBOT_DIR"
  cd "$ROBOT_DIR"
fi

log "Running install.sh"
chmod +x install.sh run.sh update.sh tools/generate_sample_audio.py
./install.sh

log "Starting kidbot.service"
sudo systemctl restart kidbot.service
sudo systemctl --no-pager --full status kidbot.service || true

log "Robot network addresses"
hostname -I || true

if [[ "$REBOOT_AFTER" == "1" ]]; then
  log "Reboot requested"
  sudo reboot
else
  log "No reboot requested. Service was started now."
fi
REMOTE_SETUP

log "Setup finished"
printf 'Open the robot UI at http://picar.local:8080 or http://<robot-ip>:8080\n'
