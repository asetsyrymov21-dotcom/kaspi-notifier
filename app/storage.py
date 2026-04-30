import psycopg2
from datetime import datetime, timezone
from typing import Iterable, Set

from app.logger import setup_logger

logger = setup_logger()


class Storage:
    def __init__(self, database_url: str, tenant_id: str):
        self.database_url = database_url
        self.tenant_id = tenant_id
        self._init_db()

    def _connect(self):
        return psycopg2.connect(self.database_url)

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS processed_orders ("
                    "  tenant_id    TEXT   NOT NULL,"
                    "  order_id     TEXT   NOT NULL,"
                    "  processed_at BIGINT NOT NULL,"
                    "  PRIMARY KEY (tenant_id, order_id)"
                    ");"
                )
            conn.commit()

    def cleanup(self, retention_days: int | None) -> None:
        if retention_days is None:
            return
        cutoff = int(datetime.now(timezone.utc).timestamp() - retention_days * 86400)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM processed_orders WHERE tenant_id = %s AND processed_at < %s;",
                    (self.tenant_id, cutoff),
                )
                deleted = cur.rowcount if cur.rowcount is not None else 0
            conn.commit()
        logger.info("Cleanup: tenant=%s retention_days=%d removed=%d", self.tenant_id, retention_days, deleted)

    def get_processed_ids(self) -> Set[str]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT order_id FROM processed_orders WHERE tenant_id = %s;",
                    (self.tenant_id,),
                )
                return {row[0] for row in cur.fetchall()}

    def is_empty(self) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM processed_orders WHERE tenant_id = %s LIMIT 1;",
                    (self.tenant_id,),
                )
                return cur.fetchone() is None

    def mark_processed(self, order_ids: Iterable[str]) -> None:
        order_ids = list(order_ids)
        if not order_ids:
            return

        now = int(datetime.now(timezone.utc).timestamp())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO processed_orders (tenant_id, order_id, processed_at)"
                    " VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;",
                    [(self.tenant_id, oid, now) for oid in order_ids],
                )
            conn.commit()
        logger.info("Saved %d processed orders for tenant=%s", len(order_ids), self.tenant_id)
