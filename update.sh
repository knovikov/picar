#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/kidbot-updater.log"
mkdir -p "$LOG_DIR"

exec >>"$LOG_FILE" 2>&1

echo "---- $(date '+%Y-%m-%dT%H:%M:%S%z') Picar manual update ----"
cd "$REPO_DIR"

if [[ -d ".venv" ]]; then
  source .venv/bin/activate
fi

KIDBOT_REPO_DIR="$REPO_DIR" python3 - <<'PY'
import os
from pathlib import Path

from kidbot.core.updater import apply_update

result = apply_update(Path(os.environ["KIDBOT_REPO_DIR"]))
print(result.message)
if result.stderr:
    print(result.stderr)
raise SystemExit(0 if result.success else 1)
PY
