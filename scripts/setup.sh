#!/usr/bin/env bash
# =============================================================================
# setup.sh — one-time project bootstrap
#
# What it does (in order):
#   1. Checks required tools
#   2. Creates a GitHub repository and pushes the code
#   3. Generates a dedicated SSH deploy key
#   4. Copies the public key to the VPS
#   5. Adds all required GitHub Actions secrets
#   6. SSHs into the VPS and:
#      a. Clones the repo
#      b. Creates .env interactively
#      c. Starts PostgreSQL
#      d. Runs the first notifier pass (mark_only bootstrap)
#      e. Installs the systemd service + timer
#
# Requirements (install once):
#   - git
#   - gh  (GitHub CLI — https://cli.github.com)
#   - ssh, ssh-keygen, ssh-copy-id
#
# Usage:
#   bash scripts/setup.sh
# =============================================================================
set -euo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}▶ $*${RESET}"; }
success() { echo -e "${GREEN}✓ $*${RESET}"; }
warn()    { echo -e "${YELLOW}! $*${RESET}"; }
die()     { echo -e "${RED}✗ $*${RESET}"; exit 1; }
ask()     { echo -e "${BOLD}$*${RESET}"; }

# ── 1. dependency check ───────────────────────────────────────────────────────
info "Checking required tools..."
for tool in git gh ssh ssh-keygen ssh-copy-id; do
  command -v "$tool" >/dev/null 2>&1 \
    || die "'$tool' not found. Install it first.\n  gh: https://cli.github.com"
done

gh auth status >/dev/null 2>&1 \
  || die "Not logged in to GitHub CLI.\n  Run: gh auth login"

success "All tools available"
echo

# ── 2. GitHub repository ──────────────────────────────────────────────────────
info "=== Step 1/5: GitHub repository ==="
ask "Repository name (e.g. kaspi-notifier):"
read -r REPO_NAME
REPO_NAME="${REPO_NAME:-kaspi-notifier}"

ask "Private repository? [Y/n]:"
read -r PRIVATE_CHOICE
if [[ "${PRIVATE_CHOICE,,}" == "n" ]]; then
  VISIBILITY="--public"
else
  VISIBILITY="--private"
fi

GH_USER=$(gh api user --jq '.login')
REPO_FULL="${GH_USER}/${REPO_NAME}"
REPO_URL="https://github.com/${REPO_FULL}.git"

if gh repo view "$REPO_FULL" >/dev/null 2>&1; then
  warn "Repository ${REPO_FULL} already exists — skipping creation"
else
  info "Creating ${REPO_FULL}..."
  gh repo create "$REPO_NAME" $VISIBILITY --description "Kaspi Shop order notifier" --confirm 2>/dev/null \
    || gh repo create "$REPO_NAME" $VISIBILITY --description "Kaspi Shop order notifier"
  success "Repository created: https://github.com/${REPO_FULL}"
fi

# ── git init + push ───────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [ ! -d ".git" ]; then
  info "Initialising git..."
  git init
  git branch -M main
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "$REPO_URL"
else
  git remote set-url origin "$REPO_URL"
fi

info "Committing and pushing to origin/main..."
git add .
git diff --cached --quiet || git commit -m "feat: initial commit"
git push -u origin main --force-with-lease 2>/dev/null || git push -u origin main
success "Code pushed to ${REPO_URL}"
echo

# ── 3. VPS connection details ─────────────────────────────────────────────────
info "=== Step 2/5: VPS connection details ==="
ask "VPS host (IP or hostname):"
read -r VPS_HOST

ask "VPS SSH user (e.g. ubuntu):"
read -r VPS_USER

ask "VPS SSH port [22]:"
read -r VPS_PORT
VPS_PORT="${VPS_PORT:-22}"

ask "Deploy path on VPS [/opt/kaspi-notifier]:"
read -r VPS_DEPLOY_PATH
VPS_DEPLOY_PATH="${VPS_DEPLOY_PATH:-/opt/kaspi-notifier}"

SSH_OPTS="-p ${VPS_PORT} -o StrictHostKeyChecking=accept-new"

info "Testing SSH connection..."
ssh $SSH_OPTS "${VPS_USER}@${VPS_HOST}" "echo connected" \
  || die "SSH connection failed. Check host/user/port and try again."
success "SSH connection OK"
echo

# ── 4. Deploy SSH key ─────────────────────────────────────────────────────────
info "=== Step 3/5: Deploy SSH key ==="
KEY_FILE="${HOME}/.ssh/kaspi_deploy_${REPO_NAME}"

if [ -f "$KEY_FILE" ]; then
  warn "Key ${KEY_FILE} already exists — reusing it"
else
  ssh-keygen -t ed25519 -C "github-actions-${REPO_NAME}" -f "$KEY_FILE" -N ""
  success "Key pair generated: ${KEY_FILE}"
fi

info "Copying public key to VPS..."
ssh-copy-id -i "${KEY_FILE}.pub" -p "${VPS_PORT}" "${VPS_USER}@${VPS_HOST}" \
  || warn "ssh-copy-id failed (key may already be present — continuing)"
success "Public key installed on VPS"
echo

# ── 5. GitHub Secrets ─────────────────────────────────────────────────────────
info "=== Step 4/5: GitHub Secrets ==="

gh secret set VPS_HOST        --body "$VPS_HOST"         --repo "$REPO_FULL"
gh secret set VPS_USER        --body "$VPS_USER"         --repo "$REPO_FULL"
gh secret set VPS_PORT        --body "$VPS_PORT"         --repo "$REPO_FULL"
gh secret set VPS_DEPLOY_PATH --body "$VPS_DEPLOY_PATH"  --repo "$REPO_FULL"
gh secret set VPS_SSH_KEY     < "$KEY_FILE"              --repo "$REPO_FULL"

success "All 5 GitHub Secrets set"
echo

# ── 6. VPS bootstrap ─────────────────────────────────────────────────────────
info "=== Step 5/5: VPS bootstrap ==="

# 6a. Collect .env values interactively
echo
warn "Enter the application credentials for .env on the VPS."
warn "These stay on the VPS only — never pushed to GitHub.\n"

ask "DATABASE_URL [postgresql://kaspi:kaspi@postgres:5432/kaspi]:"
read -r DB_URL
DB_URL="${DB_URL:-postgresql://kaspi:kaspi@postgres:5432/kaspi}"

ask "KASPI_ORDERS_URL (e.g. https://kaspi.kz/shop/api/orders):"
read -r KASPI_URL

ask "KASPI_API_KEY:"
read -r -s KASPI_KEY; echo

ask "TELEGRAM_BOT_TOKEN:"
read -r -s TG_TOKEN; echo

ask "TELEGRAM_CHAT_ID:"
read -r TG_CHAT

# 6b. Run remote setup
info "Running VPS setup (clone, .env, docker, systemd)..."

ssh $SSH_OPTS "${VPS_USER}@${VPS_HOST}" bash -s \
  "$VPS_DEPLOY_PATH" "$REPO_FULL" \
  "$DB_URL" "$KASPI_URL" "$KASPI_KEY" "$TG_TOKEN" "$TG_CHAT" << 'REMOTE'
set -euo pipefail
DEPLOY_PATH="$1"
REPO_FULL="$2"
DB_URL="$3"
KASPI_URL="$4"
KASPI_KEY="$5"
TG_TOKEN="$6"
TG_CHAT="$7"

echo "--- clone or update repo ---"
if [ -d "$DEPLOY_PATH/.git" ]; then
  cd "$DEPLOY_PATH" && git pull origin main
else
  git clone "https://github.com/${REPO_FULL}.git" "$DEPLOY_PATH"
  cd "$DEPLOY_PATH"
fi

echo "--- create .env ---"
cat > .env << ENV
DATABASE_URL=${DB_URL}
KASPI_ORDERS_URL=${KASPI_URL}
KASPI_API_KEY=${KASPI_KEY}
TELEGRAM_BOT_TOKEN=${TG_TOKEN}
TELEGRAM_CHAT_ID=${TG_CHAT}
HTTP_TIMEOUT=10
DRY_RUN=0
INITIAL_SYNC_MODE=mark_only
LOG_LEVEL=INFO
LOCK_FILE_PATH=/tmp/kaspi-notifier.lock
PROCESSED_RETENTION_DAYS=180
TENANTS_FILE=tenants.json
ENV
echo ".env created"

echo "--- start postgres ---"
docker compose up -d postgres

echo "--- wait for postgres to be healthy ---"
for i in $(seq 1 20); do
  docker compose exec postgres pg_isready -U kaspi >/dev/null 2>&1 && break
  echo "  waiting ($i/20)..."
  sleep 3
done

echo "--- first run (bootstrap mark_only) ---"
docker compose run --rm notifier || true

echo "--- install systemd service + timer ---"
sudo tee /etc/systemd/system/kaspi-notifier.service > /dev/null << SVC
[Unit]
Description=Kaspi notifier one-shot
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=${DEPLOY_PATH}
ExecStart=/usr/bin/docker compose run --rm notifier
SVC

sudo tee /etc/systemd/system/kaspi-notifier.timer > /dev/null << TMR
[Unit]
Description=Run kaspi notifier every minute

[Timer]
OnCalendar=*-*-* *:*:00
Unit=kaspi-notifier.service

[Install]
WantedBy=timers.target
TMR

sudo systemctl daemon-reload
sudo systemctl enable --now kaspi-notifier.timer
echo "systemd timer enabled"
REMOTE

success "VPS setup complete"
echo

# ── done ─────────────────────────────────────────────────────────────────────
echo -e "${GREEN}${BOLD}"
echo "======================================================"
echo " Setup complete!"
echo "======================================================"
echo -e "${RESET}"
echo "  GitHub repo : https://github.com/${REPO_FULL}"
echo "  VPS deploy  : ${VPS_USER}@${VPS_HOST}:${VPS_DEPLOY_PATH}"
echo
echo "  Next push to main will auto-deploy via GitHub Actions."
echo
echo "  Useful commands on the VPS:"
echo "    journalctl -u kaspi-notifier.service -n 50"
echo "    cd ${VPS_DEPLOY_PATH} && docker compose run --rm notifier"
