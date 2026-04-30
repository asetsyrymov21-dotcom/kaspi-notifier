# Architecture

## Overview

Kaspi Shop Notifier is a **stateless one-shot process**. It runs, performs one polling pass over all configured tenants, and exits. Scheduling (cron, systemd timer, Kubernetes CronJob) is external.

## Component map

```
┌─────────────────────────────────────────────────────────────┐
│  app/main.py  ─  entry point & orchestrator                 │
│                                                             │
│  load_tenants()  →  [Config, Config, ...]                   │
│                          │                                  │
│         ┌────────────────┘                                  │
│         │  for each tenant (sequential):                    │
│         ▼                                                   │
│    run_tenant(config)                                       │
│         │                                                   │
│    ┌────┴──────────────────────────────────┐               │
│    │  acquire_lock(config.lock_file_path)  │               │
│    ├───────────────────────────────────────┤               │
│    │  Storage(config.db_path)              │               │
│    │    .cleanup()  ─  purge old records   │               │
│    ├───────────────────────────────────────┤               │
│    │  KaspiClient(config)                  │               │
│    │    .fetch_orders()  ─  HTTP GET       │               │
│    ├───────────────────────────────────────┤               │
│    │  bootstrap check (first-run logic)    │               │
│    ├───────────────────────────────────────┤               │
│    │  filter new orders (not in SQLite)    │               │
│    ├───────────────────────────────────────┤               │
│    │  TelegramClient(config)               │               │
│    │    .send_order_notification(order)    │               │
│    ├───────────────────────────────────────┤               │
│    │  Storage.mark_processed(sent_ids)     │               │
│    └───────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

## Modules

| Module | Responsibility |
|---|---|
| `app/main.py` | Entry point; multi-tenant loop; lock management; summary logging |
| `app/config.py` | `Config` dataclass; `load_config()` (env); `load_tenants()` (JSON + env) |
| `app/kaspi_client.py` | HTTP request to Kaspi API; JSON normalisation into `Order` objects |
| `app/storage.py` | SQLite CRUD; deduplication; retention cleanup |
| `app/telegram_client.py` | Format and POST message to Telegram Bot API |
| `app/models.py` | `Order` dataclass — shared data contract between modules |
| `app/logger.py` | Configure single named logger (`kaspi-notifier`) to stdout |

## Data flow (per tenant)

```
Kaspi REST API
      │
      │  GET /orders?filter[...]&page[...]
      │  X-Auth-Token: {kaspi_api_key}
      ▼
KaspiClient.fetch_orders()
      │  returns List[Order]
      ▼
deduplicate against SQLite processed_orders table
      │  new orders only
      ▼
TelegramClient.send_order_notification(order)
      │  POST api.telegram.org/bot{token}/sendMessage
      ▼
Storage.mark_processed(successful_ids)
      │  INSERT OR IGNORE into processed_orders
      ▼
exit
```

## Multi-tenancy design

### Configuration loading

```
TENANTS_FILE env var
       │
       ├── not set or file missing  →  load_config()  →  single Config from .env
       │
       └── file exists  →  load_tenants()  →  List[Config]
                               │
                               ├── global defaults read from .env
                               └── per-tenant overrides from JSON fields
```

### Isolation

| Resource | Scope | Detail |
|---|---|---|
| PostgreSQL database | Shared | All tenants use `DATABASE_URL`; isolated by `tenant_id` column |
| Lock file | Per-tenant | `/tmp/kaspi-notifier-{name}.lock` (or `lock_file_path` field) |
| Kaspi credentials | Per-tenant | `kaspi_api_key`, `kaspi_orders_url` |
| Telegram destination | Per-tenant | `telegram_bot_token`, `telegram_chat_id` |

Tenants share nothing at runtime. A failure in one tenant (Kaspi API error, Telegram error) is logged and returns a non-zero exit code for that tenant, but does not stop subsequent tenants from running.

### Execution model

```
main()
  └── for tenant in tenants:          # sequential
        run_tenant(tenant)
          ├── acquire per-tenant lock
          ├── one polling pass
          └── release lock
```

Parallelism is intentionally absent — sequential execution is simpler to debug and sufficient for typical polling intervals (≥ 1 minute). If parallel execution becomes necessary in the future, the `run_tenant()` interface is compatible with `concurrent.futures.ThreadPoolExecutor`.

## Lock mechanism

A POSIX advisory lock (`fcntl.flock`) or Windows byte-range lock (`msvcrt.locking`) is acquired on a file before any work begins. If the lock is already held (another instance of the same tenant is still running), the notifier exits cleanly with code 0. This prevents duplicate processing when the scheduler fires faster than one pass completes.

## PostgreSQL schema

```sql
CREATE TABLE IF NOT EXISTS processed_orders (
    tenant_id    TEXT   NOT NULL,
    order_id     TEXT   NOT NULL,
    processed_at BIGINT NOT NULL,   -- Unix timestamp (UTC)
    PRIMARY KEY (tenant_id, order_id)
);
```

All tenants share one database. The `tenant_id` column (set to `config.name`) provides row-level isolation — every query filters or inserts by `tenant_id`. All writes use `ON CONFLICT DO NOTHING`, making every run idempotent.

The table is created automatically on first run via `Storage._init_db()`. No migration tool is required for a fresh deployment.

### Migration note (SQLite → PostgreSQL)

If you have an existing SQLite deployment and need to preserve processed order history to avoid duplicate notifications, export and import as follows:

```bash
# Export from SQLite (run on the old host)
sqlite3 /data/state.db "SELECT 'default', order_id, processed_at FROM processed_orders;" \
  | sed "s/|/,/g" > export.csv

# Import into PostgreSQL
psql "$DATABASE_URL" -c "\copy processed_orders(tenant_id,order_id,processed_at) FROM 'export.csv' CSV;"
```

Adjust `'default'` to match the `name` you assigned in `tenants.json` if you are also enabling multi-tenant mode at the same time.

## Kaspi API integration

The integration point is `KaspiClient.fetch_orders()` and the `normalize_order()` function in `app/kaspi_client.py`. If the Kaspi API response shape changes, only `normalize_order()` needs to be updated — all downstream code works with the stable `Order` dataclass.

## Adding a new integration

To add a second notification channel (e.g. email, SMS):

1. Create `app/{channel}_client.py` with a class similar to `TelegramClient`.
2. Add required config fields to `Config` (and `load_config()` / `load_tenants()`).
3. Instantiate and call it in `run_tenant()` alongside the existing Telegram call.
4. Document new env/JSON fields in `README.md`.
