import os
import sqlite3
from datetime import datetime, timezone
from typing import Iterable, Set

from app.logger import setup_logger

logger = setup_logger()


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self) -> None:
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_orders (
                    order_id TEXT PRIMARY KEY,
                    processed_at INTEGER NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def cleanup(self, retention_days: int | None) -> None:
        if retention_days is None:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            cutoff = int(datetime.now(timezone.utc).timestamp() - retention_days * 86400)
            cursor = conn.execute(
                "DELETE FROM processed_orders WHERE processed_at < ?;", (cutoff,)
            )
            conn.commit()
            logger.info(
                "Cleanup: retention_days=%d removed=%d",
                retention_days,
                cursor.rowcount if cursor.rowcount is not None else 0,
            )
        finally:
            conn.close()

    def get_processed_ids(self) -> Set[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT order_id FROM processed_orders;")
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

    def is_empty(self) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT 1 FROM processed_orders LIMIT 1;")
            return cursor.fetchone() is None
        finally:
            conn.close()

    def mark_processed(self, order_ids: Iterable[str]) -> None:
        order_ids = list(order_ids)
        if not order_ids:
            return

        now = int(datetime.now(timezone.utc).timestamp())
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                "INSERT OR IGNORE INTO processed_orders (order_id, processed_at) VALUES (?, ?);",
                [(oid, now) for oid in order_ids],
            )
            conn.commit()
            logger.info(f"Saved {len(order_ids)} processed orders")
        finally:
            conn.close()
