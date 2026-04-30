# Kaspi Shop Notifier

A minimal one-shot script: fetch orders from the Kaspi API, send Telegram notifications for new orders, persist processed order IDs in SQLite, then exit. Supports multiple shops (multi-tenant mode) via a single `tenants.json` file.

## Quick start

```bash
cp .env.example .env        # fill in your credentials
docker compose up -d postgres   # start PostgreSQL
docker compose build
docker compose run --rm notifier
```

Logs go to stdout. Re-runs are safe: already-processed orders are never notified twice.

> **PostgreSQL is required.** The notifier uses a shared PostgreSQL database for all tenants. `docker compose up -d postgres` starts the bundled instance. To use an external database, set `DATABASE_URL` in `.env`.

## Single-tenant mode (default)

Set variables in `.env` as described below and run normally. No `tenants.json` needed.

## Multi-tenant mode

When a `tenants.json` file is present (or `TENANTS_FILE` env var points to one), the notifier runs through each tenant sequentially. Each tenant gets its own SQLite database and lock file.

1. Copy the example and edit it:
   ```bash
   cp tenants.json.example tenants.json
   ```
2. Add one JSON object per shop. Required fields per tenant:
   - `kaspi_api_key`
   - `kaspi_orders_url` (or `kaspi_base_url` + `kaspi_orders_path`)
   - `telegram_bot_token`
   - `telegram_chat_id`
3. Run:
   ```bash
   docker compose run --rm notifier
   ```

All tenants share the **same PostgreSQL database** (`DATABASE_URL`), isolated by the `tenant_id` column (`name` field) in the `processed_orders` table. Global defaults (`HTTP_TIMEOUT`, `DRY_RUN`, `LOG_LEVEL`, `INITIAL_SYNC_MODE`, `PROCESSED_RETENTION_DAYS`) are still read from the environment and can be overridden per-tenant inside the JSON.

### Tenant JSON fields

| Field | Required | Default | Description |
|---|---|---|---|
| `name` | no | `tenant{N}` | Identifier used in logs and default file paths |
| `kaspi_api_key` | yes | — | Kaspi API token |
| `kaspi_orders_url` | yes* | — | Full URL to the orders endpoint |
| `kaspi_base_url` | yes* | — | Alternative: base URL |
| `kaspi_orders_path` | yes* | — | Alternative: path appended to base URL |
| `telegram_bot_token` | yes | — | Telegram bot token |
| `telegram_chat_id` | yes | — | Telegram chat ID or @username |
| `lock_file_path` | no | `/tmp/kaspi-notifier-{name}.lock` | Lock file path |
| `http_timeout` | no | `HTTP_TIMEOUT` env | HTTP timeout in seconds |
| `dry_run` | no | `DRY_RUN` env | `true` to skip sends and DB writes |
| `order_state` | no | — | Kaspi `filter[orders][state]` |
| `order_status` | no | — | Kaspi `filter[orders][status]` |
| `page_size` | no | 10 | Kaspi `page[size]` |
| `initial_sync_mode` | no | `INITIAL_SYNC_MODE` env | `mark_only` or `notify_all` |
| `log_level` | no | `LOG_LEVEL` env | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `processed_retention_days` | no | `PROCESSED_RETENTION_DAYS` env | Days to keep processed order records |

*`kaspi_orders_url` OR (`kaspi_base_url` + `kaspi_orders_path`) is required.

## Environment variables (`.env`, single-tenant or global defaults)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | **Required.** PostgreSQL DSN, e.g. `postgresql://user:pass@host:5432/db` |
| `KASPI_ORDERS_URL` | — | Full orders endpoint URL |
| `KASPI_BASE_URL` | — | Base URL (alternative to `KASPI_ORDERS_URL`) |
| `KASPI_ORDERS_PATH` | — | Path appended to `KASPI_BASE_URL` |
| `KASPI_API_KEY` | — | API token |
| `KASPI_ORDER_STATE` | — | Optional order state filter |
| `KASPI_ORDER_STATUS` | — | Optional order status filter |
| `KASPI_PAGE_SIZE` | — | Optional page size |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token |
| `TELEGRAM_CHAT_ID` | — | Chat ID or @username |
| `HTTP_TIMEOUT` | `10` | HTTP timeout in seconds |
| `DRY_RUN` | `0` | `1` to log-only without sending or writing |
| `INITIAL_SYNC_MODE` | `mark_only` | `mark_only` or `notify_all` on first empty run |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `LOCK_FILE_PATH` | `/tmp/kaspi-notifier.lock` | Lock file path (single-tenant) |
| `PROCESSED_RETENTION_DAYS` | — | Days to keep processed records; empty = no cleanup |
| `TENANTS_FILE` | `tenants.json` | Path to the multi-tenant config file |

## Dry run

```bash
DRY_RUN=1 docker compose run --rm notifier
```

Logs show which notifications would have been sent without writing to Telegram or the database.

## Running on a schedule (Oracle VM / systemd)

1. Clone the repo, install Docker + docker-compose-plugin.
2. Create `/etc/systemd/system/kaspi-notifier.service`:
   ```ini
   [Unit]
   Description=Kaspi notifier one-shot
   After=docker.service

   [Service]
   Type=oneshot
   WorkingDirectory=/opt/kaspi-notifier
   ExecStart=/usr/bin/docker compose run --rm notifier
   ```
3. Create `/etc/systemd/system/kaspi-notifier.timer`:
   ```ini
   [Unit]
   Description=Run kaspi notifier every minute

   [Timer]
   OnCalendar=*-*-* *:*:00
   Unit=kaspi-notifier.service

   [Install]
   WantedBy=timers.target
   ```
4. Enable: `sudo systemctl daemon-reload && sudo systemctl enable --now kaspi-notifier.timer`

## Deduplication

All processed `order_id` values are stored in SQLite. Re-runs only notify on unseen orders. If `PROCESSED_RETENTION_DAYS` is set, records older than that are purged at startup.

## Bootstrap / first-run protection

- `INITIAL_SYNC_MODE=mark_only` (default): on a fresh empty database, all found orders are marked as processed without sending notifications. Prevents a flood of old-order notifications on first run.
- `INITIAL_SYNC_MODE=notify_all`: notifications are sent for all found orders even on the first run.

## Lock file

A lock file prevents two instances from running simultaneously for the same tenant. If the lock is already held, the notifier exits immediately (exit code 0). In multi-tenant mode each tenant has its own lock, so tenants never block each other.

## Project structure

```
app/
  main.py           — orchestrator; multi-tenant loop
  config.py         — Config dataclass, load_config(), load_tenants()
  kaspi_client.py   — Kaspi API requests and response normalisation
  storage.py        — SQLite persistence
  telegram_client.py — Telegram message sending
  logger.py         — stdout logger setup
  models.py         — Order dataclass
tenants.json.example — example multi-tenant config
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed component and data-flow description.
See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution rules.
