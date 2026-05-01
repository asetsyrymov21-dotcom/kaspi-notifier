import json
import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    kaspi_orders_url: str
    kaspi_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    database_url: str
    name: str = "default"
    http_timeout: int = 10
    dry_run: bool = False
    order_state: str | None = None
    order_status: str | None = None
    page_size: int | None = None
    initial_sync_mode: str = "notify_all"
    log_level: str = "INFO"
    lock_file_path: str = "/tmp/kaspi-notifier.lock"
    processed_retention_days: int | None = None


def load_config() -> Config:
    load_dotenv()
    kaspi_orders_url = _build_orders_url()
    kaspi_api_key = os.getenv("KASPI_API_KEY")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    database_url = os.getenv("DATABASE_URL")

    if not all([kaspi_orders_url, kaspi_api_key, telegram_bot_token, telegram_chat_id, database_url]):
        missing = [
            name
            for name, value in [
                ("KASPI_ORDERS_URL", kaspi_orders_url),
                ("KASPI_API_KEY", kaspi_api_key),
                ("TELEGRAM_BOT_TOKEN", telegram_bot_token),
                ("TELEGRAM_CHAT_ID", telegram_chat_id),
                ("DATABASE_URL", database_url),
            ]
            if not value
        ]
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    http_timeout = int(os.getenv("HTTP_TIMEOUT", "10"))
    dry_run = os.getenv("DRY_RUN", "0").lower() in ("1", "true", "yes")
    order_state = _optional_str("KASPI_ORDER_STATE")
    order_status = _optional_str("KASPI_ORDER_STATUS")
    page_size = _optional_int("KASPI_PAGE_SIZE")
    initial_sync_mode = os.getenv("INITIAL_SYNC_MODE", "notify_all").lower()
    if initial_sync_mode not in {"mark_only", "notify_all"}:
        raise ValueError("INITIAL_SYNC_MODE must be 'mark_only' or 'notify_all'")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    lock_file_path = os.getenv("LOCK_FILE_PATH", "/tmp/kaspi-notifier.lock")
    processed_retention_days = _optional_int("PROCESSED_RETENTION_DAYS")

    return Config(
        kaspi_orders_url=kaspi_orders_url,
        kaspi_api_key=kaspi_api_key,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        database_url=database_url,
        name="default",
        http_timeout=http_timeout,
        dry_run=dry_run,
        order_state=order_state,
        order_status=order_status,
        page_size=page_size,
        initial_sync_mode=initial_sync_mode,
        log_level=log_level,
        lock_file_path=lock_file_path,
        processed_retention_days=processed_retention_days,
    )


def load_tenants() -> list[Config]:
    """
    Load tenant configs.

    If TENANTS_FILE env var is set, or a file named 'tenants.json' exists in the
    current directory, each entry in the JSON array becomes a separate Config.
    All tenants share the same PostgreSQL database (DATABASE_URL), isolated by
    the tenant name stored in the 'tenant_id' column of the processed_orders table.

    Global defaults (DATABASE_URL, HTTP_TIMEOUT, DRY_RUN, INITIAL_SYNC_MODE,
    LOG_LEVEL, PROCESSED_RETENTION_DAYS) are read from environment variables and
    can be overridden per-tenant inside the JSON.

    Falls back to single-tenant mode via load_config() when no tenants file is found.

    Tenant JSON fields:
        name                  - tenant identifier used as tenant_id in the DB and in logs
        kaspi_api_key         - required
        kaspi_orders_url      - required (or kaspi_base_url + kaspi_orders_path)
        kaspi_base_url        - alternative base URL
        kaspi_orders_path     - alternative path appended to kaspi_base_url
        telegram_bot_token    - required
        telegram_chat_id      - required
        lock_file_path        - default: /tmp/kaspi-notifier-{name}.lock
        http_timeout          - default: HTTP_TIMEOUT env or 10
        dry_run               - default: DRY_RUN env or false
        order_state           - optional Kaspi filter
        order_status          - optional Kaspi filter
        page_size             - optional Kaspi page size
        initial_sync_mode     - default: INITIAL_SYNC_MODE env or 'notify_all'
        log_level             - default: LOG_LEVEL env or 'INFO'
        processed_retention_days - default: PROCESSED_RETENTION_DAYS env or null
    """
    load_dotenv()
    tenants_file = os.getenv("TENANTS_FILE", "tenants.json")

    if not os.path.isfile(tenants_file):
        return [load_config()]

    with open(tenants_file, encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{tenants_file}: must be a non-empty JSON array")

    # Shared database URL — required in environment for multi-tenant mode
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required for multi-tenant mode")

    # Global defaults from environment
    global_http_timeout = int(os.getenv("HTTP_TIMEOUT", "10"))
    global_dry_run = os.getenv("DRY_RUN", "0").lower() in ("1", "true", "yes")
    global_initial_sync_mode = os.getenv("INITIAL_SYNC_MODE", "notify_all").lower()
    if global_initial_sync_mode not in {"mark_only", "notify_all"}:
        raise ValueError("INITIAL_SYNC_MODE must be 'mark_only' or 'notify_all'")
    global_log_level = os.getenv("LOG_LEVEL", "INFO")
    global_retention = _optional_int("PROCESSED_RETENTION_DAYS")

    configs: list[Config] = []
    for i, entry in enumerate(raw):
        name = str(entry.get("name") or f"tenant{i + 1}")

        kaspi_orders_url = entry.get("kaspi_orders_url") or _build_orders_url_from_entry(entry)
        kaspi_api_key = entry.get("kaspi_api_key")
        telegram_bot_token = entry.get("telegram_bot_token")
        telegram_chat_id = str(entry.get("telegram_chat_id") or "")

        missing = [
            k
            for k, v in [
                ("kaspi_orders_url / kaspi_base_url+kaspi_orders_path", kaspi_orders_url),
                ("kaspi_api_key", kaspi_api_key),
                ("telegram_bot_token", telegram_bot_token),
                ("telegram_chat_id", telegram_chat_id),
            ]
            if not v
        ]
        if missing:
            raise ValueError(f"Tenant '{name}': missing required fields: {', '.join(missing)}")

        lock_file_path = entry.get("lock_file_path") or f"/tmp/kaspi-notifier-{name}.lock"

        http_timeout = int(entry["http_timeout"]) if entry.get("http_timeout") is not None else global_http_timeout
        dry_run_raw = entry.get("dry_run")
        dry_run = bool(dry_run_raw) if dry_run_raw is not None else global_dry_run

        order_state = entry.get("order_state") or None
        order_status = entry.get("order_status") or None
        page_size_raw = entry.get("page_size")
        page_size = int(page_size_raw) if page_size_raw is not None else None

        initial_sync_mode = str(entry.get("initial_sync_mode") or global_initial_sync_mode).lower()
        if initial_sync_mode not in {"mark_only", "notify_all"}:
            raise ValueError(f"Tenant '{name}': initial_sync_mode must be 'mark_only' or 'notify_all'")

        log_level = str(entry.get("log_level") or global_log_level)

        retention_raw = entry.get("processed_retention_days")
        processed_retention_days = int(retention_raw) if retention_raw is not None else global_retention

        configs.append(
            Config(
                name=name,
                kaspi_orders_url=kaspi_orders_url,
                kaspi_api_key=kaspi_api_key,
                telegram_bot_token=telegram_bot_token,
                telegram_chat_id=telegram_chat_id,
                database_url=database_url,
                http_timeout=http_timeout,
                dry_run=dry_run,
                order_state=order_state,
                order_status=order_status,
                page_size=page_size,
                initial_sync_mode=initial_sync_mode,
                log_level=log_level,
                lock_file_path=lock_file_path,
                processed_retention_days=processed_retention_days,
            )
        )

    return configs


def _build_orders_url() -> str | None:
    direct = os.getenv("KASPI_ORDERS_URL")
    if direct:
        return direct.rstrip("/")

    base = os.getenv("KASPI_BASE_URL")
    path = os.getenv("KASPI_ORDERS_PATH")
    if base and path:
        return f"{base.rstrip('/')}/{path.lstrip('/')}"
    return None


def _build_orders_url_from_entry(entry: dict) -> str | None:
    base = entry.get("kaspi_base_url")
    path = entry.get("kaspi_orders_path")
    if base and path:
        return f"{base.rstrip('/')}/{path.lstrip('/')}"
    return None


def _optional_str(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


def _optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Invalid int value for {name}: {value}")
