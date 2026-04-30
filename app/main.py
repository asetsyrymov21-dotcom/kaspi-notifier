import errno
import os
import sys
from typing import List, Optional

if os.name == "nt":
    import msvcrt

from app.config import Config, load_tenants
from app.kaspi_client import KaspiClient
from app.logger import setup_logger
from app.storage import Storage
from app.telegram_client import TelegramClient

logger = setup_logger()


def main() -> int:
    try:
        tenants = load_tenants()
    except Exception as exc:
        logger.error(f"Failed to load config: {exc}")
        return 1

    setup_logger(tenants[0].log_level)  # adjust level after config is known

    exit_code = 0
    for config in tenants:
        result = run_tenant(config)
        if result != 0:
            exit_code = result
    return exit_code


def run_tenant(config: Config) -> int:
    """Execute one full pass for a single tenant. Returns 0 on success, 1 on error."""
    tenant_prefix = f"[{config.name}] " if config.name != "default" else ""

    lock = acquire_lock(config.lock_file_path)
    if lock is None:
        logger.warning("%sAnother instance is running; skipping", tenant_prefix)
        return 0

    storage = Storage(config.database_url, config.name)
    storage.cleanup(config.processed_retention_days)
    kaspi = KaspiClient(config)
    telegram = TelegramClient(config)

    total_orders = 0
    new_orders_count = 0
    sent_count = 0
    failed_count = 0
    bootstrap_performed = False
    exit_code = 0
    fetch_failed = False

    try:
        try:
            orders = kaspi.fetch_orders()
            total_orders = len(orders)
        except Exception:
            fetch_failed = True
            exit_code = 1
            return exit_code

        if not orders:
            logger.info("%sNo orders returned by API", tenant_prefix)
            return exit_code

        try:
            if storage.is_empty() and config.initial_sync_mode == "mark_only":
                bootstrap_performed = True
                order_ids = [order.id for order in orders if order.id]
                if config.dry_run:
                    logger.info(
                        "%s[dry-run] Bootstrap mark-only: would mark %d orders as processed",
                        tenant_prefix,
                        len(order_ids),
                    )
                else:
                    storage.mark_processed(order_ids)
                    logger.info(
                        "%sBootstrap mark-only: marked %d existing orders as processed",
                        tenant_prefix,
                        len(order_ids),
                    )
                return exit_code
        except Exception as exc:
            logger.error(f"{tenant_prefix}Bootstrap check failed: {exc}")
            exit_code = 1
            return exit_code

        processed_ids = storage.get_processed_ids()
        new_orders = [order for order in orders if order.id not in processed_ids]
        new_orders_count = len(new_orders)

        if not new_orders:
            logger.info("%sNo new orders to notify", tenant_prefix)
            return exit_code

        logger.info("%sFound %d new orders", tenant_prefix, new_orders_count)
        successful: List[str] = []

        for order in new_orders:
            try:
                telegram.send_order_notification(order)
                successful.append(order.id)
            except Exception:
                failed_count += 1
                continue
            sent_count += 1

        if config.dry_run:
            logger.info("%s[dry-run] Skipping DB write", tenant_prefix)
            return exit_code

        storage.mark_processed(successful)
        if not successful:
            logger.error("%sFailed to notify on all new orders", tenant_prefix)
            exit_code = 1
        return exit_code
    finally:
        summary_log(
            tenant_prefix=tenant_prefix,
            total_orders=total_orders,
            new_orders=new_orders_count,
            sent=sent_count,
            failed=failed_count,
            bootstrap=bootstrap_performed,
            fetch_failed=fetch_failed,
            exit_code=exit_code,
        )
        release_lock(lock)


def acquire_lock(path: str) -> Optional[tuple]:
    fd = None
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_RDWR)
        if os.name == "nt":
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                os.close(fd)
                if exc.errno in (errno.EACCES, errno.EDEADLK):
                    return None
                logger.error(f"Failed to acquire lock {path}: {exc}")
                return None
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                return None
            except OSError as exc:
                os.close(fd)
                logger.error(f"Failed to acquire lock {path}: {exc}")
                return None
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        return fd, path
    except OSError as exc:
        if fd is not None:
            os.close(fd)
        logger.error(f"Failed to acquire lock {path}: {exc}")
        return None


def release_lock(lock: Optional[tuple]) -> None:
    if lock is None:
        return
    fd, _ = lock
    try:
        if os.name == "nt":
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            os.close(fd)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
    except OSError as exc:
        logger.error(f"Failed to release lock: {exc}")


def summary_log(
    tenant_prefix: str,
    total_orders: int,
    new_orders: int,
    sent: int,
    failed: int,
    bootstrap: bool,
    fetch_failed: bool,
    exit_code: int,
) -> None:
    logger.info(
        "%sSummary: total=%d new=%d sent=%d failed=%d bootstrap=%s fetch_failed=%s exit_code=%d",
        tenant_prefix,
        total_orders,
        new_orders,
        sent,
        failed,
        str(bootstrap).lower(),
        str(fetch_failed).lower(),
        exit_code,
    )


if __name__ == "__main__":
    sys.exit(main())
