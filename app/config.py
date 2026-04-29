import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    kaspi_orders_url: str
    kaspi_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    db_path: str = "/data/state.db"
    http_timeout: int = 10
    dry_run: bool = False
    order_state: str | None = None
    order_status: str | None = None
    page_size: int | None = None
    initial_sync_mode: str = "mark_only"
    log_level: str = "INFO"
    lock_file_path: str = "/tmp/kaspi-notifier.lock"
    processed_retention_days: int | None = None


def load_config() -> Config:
    load_dotenv()
    kaspi_orders_url = _build_orders_url()
    kaspi_api_key = os.getenv("KASPI_API_KEY")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not all([kaspi_orders_url, kaspi_api_key, telegram_bot_token, telegram_chat_id]):
        missing = [
            name
            for name, value in [
                ("KASPI_ORDERS_URL", kaspi_orders_url),
                ("KASPI_API_KEY", kaspi_api_key),
                ("TELEGRAM_BOT_TOKEN", telegram_bot_token),
                ("TELEGRAM_CHAT_ID", telegram_chat_id),
            ]
            if not value
        ]
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    db_path = os.getenv("DB_PATH", "/data/state.db")
    http_timeout = int(os.getenv("HTTP_TIMEOUT", "10"))
    dry_run = os.getenv("DRY_RUN", "0").lower() in ("1", "true", "yes")
    order_state = _optional_str("KASPI_ORDER_STATE")
    order_status = _optional_str("KASPI_ORDER_STATUS")
    page_size = _optional_int("KASPI_PAGE_SIZE")
    initial_sync_mode = os.getenv("INITIAL_SYNC_MODE", "mark_only").lower()
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
        db_path=db_path,
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


def _build_orders_url() -> str | None:
    direct = os.getenv("KASPI_ORDERS_URL")
    if direct:
        return direct.rstrip("/")

    base = os.getenv("KASPI_BASE_URL")
    path = os.getenv("KASPI_ORDERS_PATH")
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
