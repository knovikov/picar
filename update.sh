#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/kidbot-updater.log"
mkdir -p "$LOG_DIR"

exec >>"$LOG_FILE" 2>&1

echo "---- $(date '+%Y-%m-%dT%H:%M:%S%z') KidBot update check ----"
cd "$REPO_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository; skipping update."
  exit 0
fi

if ! git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  echo "No upstream branch configured; skipping update."
  echo "Set one with: git remote add origin <url> && git push -u origin $(git branch --show-current)"
  exit 0
fi

if ! ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
  echo "No internet; skipping update."
  exit 0
fi

OLD_COMMIT="$(git rev-parse HEAD)"
git fetch

LOCAL_COMMIT="$(git rev-parse @)"
REMOTE_COMMIT="$(git rev-parse '@{u}')"
BASE_COMMIT="$(git merge-base @ '@{u}')"

if [[ "$LOCAL_COMMIT" == "$REMOTE_COMMIT" ]]; then
  echo "Already up to date."
  exit 0
fi

if [[ "$LOCAL_COMMIT" != "$BASE_COMMIT" ]]; then
  echo "Local branch has commits that are not on upstream; skipping automatic update."
  exit 1
fi

if ! git pull --ff-only; then
  echo "git pull failed; returning to $OLD_COMMIT"
  git checkout "$OLD_COMMIT"
  exit 1
fi

if [[ -d ".venv" ]]; then
  source .venv/bin/activate
fi

python3 -m pip install -r requirements.txt
python3 tools/generate_sample_audio.py

if command -v systemctl >/dev/null 2>&1; then
  sudo -n systemctl restart kidbot.service
fi

echo "Update complete."
