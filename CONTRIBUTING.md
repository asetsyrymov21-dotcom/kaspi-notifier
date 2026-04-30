# Contributing

## Development setup

```bash
git clone <repo>
cd kaspi-notifier
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # fill in real or test credentials
```

Run a single pass locally:
```bash
python -m app.main
```

Dry-run (no Telegram sends, no DB writes):
```bash
DRY_RUN=1 python -m app.main
```

## Project rules

### 1. One-shot design — keep it that way

The notifier is intentionally stateless between runs. It starts, does one pass, and exits. Do not add long-running loops, background threads, or in-process schedulers. Scheduling belongs to systemd timers, cron, or Kubernetes CronJobs.

### 2. Minimal diffs

Make the smallest correct change. Do not refactor code that is not related to the issue at hand. Do not rename symbols, reorganize files, or change coding style unless explicitly required.

### 3. No new dependencies without justification

Before adding a package to `requirements.txt`, explain why the existing stack (stdlib + `requests` + `python-dotenv`) cannot solve the problem. Keep the dependency surface small.

### 4. Configuration via environment / tenants.json

All runtime configuration must come from environment variables or `tenants.json`. No hardcoded credentials, URLs, or magic numbers in source code. Defaults must be documented in `README.md`.

### 5. Adding a new per-tenant field

1. Add the field to the `Config` dataclass in `app/config.py` with a sensible default.
2. Read it in both `load_config()` (from env) and `load_tenants()` (from JSON + env fallback).
3. Update the tenant field table in `README.md`.
4. Update `tenants.json.example` if the field is non-trivial.

### 6. Adding a new environment variable

1. Add reading logic in `load_config()` in `app/config.py`.
2. Add a default value in `.env.example` (even if blank).
3. Document it in the environment variable table in `README.md`.

### 7. Error handling

- Errors inside a single tenant must not abort other tenants. `run_tenant()` catches and logs failures and returns a non-zero exit code; `main()` aggregates exit codes.
- Log at `ERROR` level for failures that affect correctness; `WARNING` for expected degraded states (e.g. lock held); `INFO` for normal operation.
- Never swallow exceptions silently; always log before continuing.

### 8. Logging

Use the shared `setup_logger()` logger (named `kaspi-notifier`). In multi-tenant contexts, prefix messages with `[{config.name}]`. Do not use `print()`.

### 9. PostgreSQL and data integrity

- All tenants share one PostgreSQL database. Tenant isolation is enforced by the `tenant_id` column — every query in `Storage` must filter by `self.tenant_id`.
- Use `ON CONFLICT DO NOTHING` to remain idempotent on re-runs.
- The schema lives in `Storage._init_db()` and is applied automatically on first run. Schema changes must be additive (new nullable columns or new tables only) — never drop or rename columns in a patch.
- Never share a connection object between Storage instances or between tenants.

### 10. Preserve backward compatibility

Single-tenant mode (plain `.env`, no `tenants.json`) must continue to work exactly as before. Any change to `load_config()` must not break existing deployments.

## Code style

- Follow PEP 8. Line length ≤ 100 characters.
- Use type hints on all function signatures.
- Keep functions short and focused; extract helpers when a function grows beyond ~40 lines.
- Prefer f-strings for interpolation, `%`-style for `logger.*` calls (avoids string formatting when log level is suppressed).

## Testing

There is no test suite yet. When adding tests:

- Place them under `tests/`.
- Name files `test_<module>.py`.
- Use `pytest`.
- Mock external calls (`requests.get`, SQLite) rather than hitting real services.
- Run: `pytest tests/`

## Commit conventions

```
<type>: <short imperative description>

[optional body — what and why, not how]
```

Types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`.

Examples:
```
feat: add multi-tenant support via tenants.json
fix: skip orders without id instead of crashing
docs: document PROCESSED_RETENTION_DAYS in README
```

## Pull request checklist

- [ ] All new config fields documented in `README.md`
- [ ] `.env.example` updated if new env vars added
- [ ] `tenants.json.example` updated if new tenant fields added
- [ ] Backward compatibility with single-tenant mode preserved
- [ ] No new dependencies unless justified in the PR description
- [ ] `python -m py_compile app/*.py` passes (no syntax errors)
