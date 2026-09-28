#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Vigil · one-shot server installer (Debian / Ubuntu, run as root)
#
#  Interactive:   bash install.sh
#  Non-interactive:
#     BOT_TOKEN=... SYSTEM_OWNER_ID=... OPENROUTER_API_KEY=... bash install.sh
#  Force mode:    bash install.sh --docker   |   bash install.sh --native
#  Re-running the script updates the code and restarts the service.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/qna1087-coder/mybot-.git}"
BRANCH="${BRANCH:-claude/telegram-protection-system-fl5j6k}"
APP_DIR="${APP_DIR:-/opt/vigil}"
MODE="${1:-auto}"

log()  { printf '\n\033[1m● %s\033[0m\n' "$*"; }
warn() { printf '\n\033[33m! %s\033[0m\n' "$*"; }
die()  { printf '\n\033[31m! %s\033[0m\n' "$*"; exit 1; }

[ "$(id -u)" = 0 ] || die "Run this as root."
command -v apt-get >/dev/null 2>&1 || die "This installer supports Debian/Ubuntu (apt-get)."

export DEBIAN_FRONTEND=noninteractive
log "Base packages"
apt-get update -qq
apt-get install -y -qq git ca-certificates curl >/dev/null

# ── code ─────────────────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
  log "Updating $APP_DIR ($BRANCH)"
  git -C "$APP_DIR" fetch -q origin "$BRANCH"
  git -C "$APP_DIR" checkout -q "$BRANCH"
  git -C "$APP_DIR" reset -q --hard "origin/$BRANCH"
else
  log "Cloning into $APP_DIR ($BRANCH)"
  git clone -q --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
mkdir -p data

# ── .env ─────────────────────────────────────────────────────
set_env() {  # set_env KEY VALUE  (escapes sed specials)
  local key="$1" val="$2"
  val="${val//\\/\\\\}"; val="${val//&/\\&}"; val="${val//|/\\|}"
  if grep -q "^${key}=" .env; then sed -i "s|^${key}=.*|${key}=${val}|" .env; else printf '%s=%s\n' "$key" "$val" >> .env; fi
}
ask() {  # ask VAR "Prompt"  — environment wins, then the existing .env, then the terminal
  local var="$1" prompt="$2" cur
  cur="${!var:-}"
  if [ -z "$cur" ] && [ -f .env ]; then cur="$(grep -E "^${var}=" .env | head -1 | cut -d= -f2-)"; fi
  if [ -z "$cur" ]; then
    if [ -r /dev/tty ]; then read -r -p "$prompt: " cur </dev/tty 2>/dev/null || cur=""; fi
  fi
  [ -n "$cur" ] || die "$var is required. Pass it like:  BOT_TOKEN=... SYSTEM_OWNER_ID=... OPENROUTER_API_KEY=... bash install.sh"
  printf -v "$var" '%s' "$cur"
}

log "Configuration (.env)"
[ -f .env ] || cp .env.example .env
ask BOT_TOKEN "BOT_TOKEN (from @BotFather)"
ask SYSTEM_OWNER_ID "SYSTEM_OWNER_ID (your numeric Telegram ID)"
ask OPENROUTER_API_KEY "OPENROUTER_API_KEY (https://openrouter.ai/keys)"
case "$BOT_TOKEN" in *:*) ;; *) die "BOT_TOKEN looks wrong (expected 123456789:AA...)";; esac
case "$SYSTEM_OWNER_ID" in ''|*[!0-9]*) die "SYSTEM_OWNER_ID must be a number";; esac
set_env BOT_TOKEN "$BOT_TOKEN"
set_env SYSTEM_OWNER_ID "$SYSTEM_OWNER_ID"
set_env OPENROUTER_API_KEY "$OPENROUTER_API_KEY"
[ -n "${DEFAULT_TIMEZONE:-}" ] && set_env DEFAULT_TIMEZONE "$DEFAULT_TIMEZONE"
[ -n "${DEFAULT_LANGUAGE:-}" ] && set_env DEFAULT_LANGUAGE "$DEFAULT_LANGUAGE"
[ -n "${MODERATION_MODELS:-}" ] && set_env MODERATION_MODELS "$MODERATION_MODELS"
chmod 600 .env

# ── pick mode ────────────────────────────────────────────────
py_ok() { "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; }
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && py_ok "$c"; then PY="$c"; break; fi
done
if [ "$MODE" = "auto" ]; then
  if [ -n "$PY" ]; then MODE="--native"; else MODE="--docker"; fi
fi

if [ "$MODE" = "--native" ]; then
  if [ -z "$PY" ]; then
    apt-get install -y -qq python3.11 python3.11-venv >/dev/null 2>&1 && PY="python3.11" || die "Python ≥ 3.11 not available; run with --docker."
  fi
  log "Native install with $PY"
  apt-get install -y -qq "${PY}-venv" python3-pip >/dev/null 2>&1 || apt-get install -y -qq python3-venv >/dev/null 2>&1 || true
  [ -x .venv/bin/python ] && ! py_ok .venv/bin/python && rm -rf .venv
  [ -x .venv/bin/python ] || "$PY" -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt

  log "Validating configuration"
  .venv/bin/python -c "from vigil.config import get_settings; s = get_settings(); print('  owner', s.system_owner_id, '·', len(s.model_chain), 'models')" \
    || die "Configuration invalid — check the values in $APP_DIR/.env"

  cat > /etc/systemd/system/vigil.service <<UNIT
[Unit]
Description=Vigil · Telegram channel protection system
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/python -m vigil
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable -q vigil
  systemctl restart vigil
  sleep 4
  log "Service"
  systemctl --no-pager --lines=0 status vigil || true
  log "Last log lines"
  journalctl -u vigil -n 25 --no-pager || true
  printf '\n  Logs:     journalctl -u vigil -f\n  Restart:  systemctl restart vigil\n  Update:   bash %s/deploy/install.sh\n' "$APP_DIR"
else
  log "Docker install"
  if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
  fi
  docker compose version >/dev/null 2>&1 || apt-get install -y -qq docker-compose-plugin >/dev/null
  docker compose up -d --build
  sleep 4
  docker compose logs --tail 30
  printf '\n  Logs:     cd %s && docker compose logs -f\n  Restart:  docker compose restart\n  Update:   bash %s/deploy/install.sh --docker\n' "$APP_DIR" "$APP_DIR"
fi

log "Done. Send /start to the bot, add it to the channel as administrator, then activate the channel from the card you receive."
