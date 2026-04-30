# Deployment Guide

## Overview

```
Local machine  ──push──▶  GitHub (main)  ──Actions──▶  VPS
                                                         │
                                              git pull + docker compose build
```

---

## One-time setup (automated)

### Prerequisites

Install **GitHub CLI** once:

| OS | Command |
|---|---|
| Windows | `winget install GitHub.cli` or download from https://cli.github.com |
| macOS | `brew install gh` |
| Ubuntu/Debian | `sudo apt install gh` |

Then authenticate:
```bash
gh auth login
```

### Run the setup script

From the project root:

```bash
bash scripts/setup.sh
```

The script will ask you interactively for:
- GitHub repository name and visibility
- VPS host, user, port, deploy path
- App credentials: `KASPI_ORDERS_URL`, `KASPI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

Then it fully automates:

| Step | What happens |
|---|---|
| 1 | Creates the GitHub repository |
| 2 | Commits and pushes all code to `main` |
| 3 | Generates a dedicated SSH deploy key (`~/.ssh/kaspi_deploy_<repo>`) |
| 4 | Installs the public key on the VPS via `ssh-copy-id` |
| 5 | Sets all 5 GitHub Secrets (`VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_PORT`, `VPS_DEPLOY_PATH`) |
| 6 | Clones the repo on the VPS |
| 7 | Creates `.env` on the VPS with your credentials |
| 8 | Starts PostgreSQL via docker compose |
| 9 | Runs the first notifier pass (mark-only bootstrap, no spam) |
| 10 | Installs and enables the systemd timer (runs every minute) |

Total time: ~2 minutes.

---

## Day-to-day workflow

```bash
git add .
git commit -m "fix: ..."
git push          # triggers auto-deploy to VPS via GitHub Actions
```

GitHub Actions will:
1. SSH into the VPS
2. `git pull origin main`
3. `docker compose build --no-cache notifier`
4. `docker compose up -d postgres`

---

## Manual setup (if needed)

See the original step-by-step instructions in `scripts/setup.sh` comments
or follow these commands:

```bash
# On VPS
cd /opt && git clone https://github.com/<you>/kaspi-notifier.git
cd kaspi-notifier
cp .env.example .env && nano .env
docker compose up -d postgres
docker compose run --rm notifier
```

---

## Useful VPS commands

```bash
# View recent notifier logs
journalctl -u kaspi-notifier.service -n 50

# Manual one-off run
cd /opt/kaspi-notifier && docker compose run --rm notifier

# Dry-run (no Telegram sends, no DB writes)
DRY_RUN=1 docker compose run --rm notifier

# Check systemd timer
sudo systemctl list-timers kaspi-notifier.timer

# Connect to postgres
docker compose exec postgres psql -U kaspi -d kaspi
```
