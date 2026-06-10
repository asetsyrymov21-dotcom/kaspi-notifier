import requests
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from app.config import Config
from app.logger import setup_logger
from app.models import Order

logger = setup_logger()


def normalize_order(raw_order: Dict[str, Any]) -> Order:
    """
    Map Kaspi API order fields into a stable internal model.
    Adjust this function if the API response changes.
    """
    attributes = raw_order.get("attributes", {})

    return Order(
        id=str(raw_order.get("id") or attributes.get("id")),
        code=attributes.get("code"),
        created_at=attributes.get("creationDate"),
        total_price=_extract_total_price(attributes),
        customer_name=_extract_customer_name(attributes),
        customer_phone=_extract_customer_phone(attributes),
        status=attributes.get("status"),
        state=attributes.get("state"),
        raw=raw_order,
    )


def _extract_total_price(attributes: Dict[str, Any]) -> float | None:
    total = attributes.get("totalPrice") or attributes.get("totalSum")
    try:
        return float(total) if total is not None else None
    except (TypeError, ValueError):
        return None


def _extract_customer_name(attributes: Dict[str, Any]) -> str | None:
    customer = attributes.get("customer") or {}
    return customer.get("name") or customer.get("fullName")


def _extract_customer_phone(attributes: Dict[str, Any]) -> str | None:
    customer = attributes.get("customer") or {}
    return customer.get("cellPhone")


class KaspiClient:
    def __init__(self, config: Config):
        self.orders_url = config.kaspi_orders_url
        self.api_key = config.kaspi_api_key
        self.timeout = config.http_timeout
        self.order_state = config.order_state
        self.order_status = config.order_status
        self.page_size = config.page_size

    def fetch_orders(self) -> List[Order]:
        headers = {
            "X-Auth-Token": self.api_key,
            "Accept": "application/vnd.api+json",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "User-Agent": "PostmanRuntime/7.52.0",
        }
        params = _build_params(
            state=self.order_state,
            status=self.order_status,
            page_size=self.page_size,
        )
        try:
            url = f"{self.orders_url}?{urlencode(params)}"
            logger.info("Fetching Kaspi orders: url=%s", url)
            logger.info("Kaspi headers keys: %s", list(headers.keys()))
            response = requests.get(
                url, headers=headers, timeout=(10, 20)
            )
            logger.info("Kaspi response received: status=%s", response.status_code)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error(f"Failed to fetch orders: {exc}")
            raise

        try:
            payload = response.json()
        except ValueError as exc:
            logger.error(f"Failed to parse orders JSON: {exc}")
            raise

        raw_orders = payload.get("data") or []
        orders = []
        for raw in raw_orders:
            order = normalize_order(raw)
            if not order.id:
                logger.warning("Skipping order without id")
                continue
            self._attach_order_entries(order)
            orders.append(order)
        return orders

    def _attach_order_entries(self, order: Order) -> None:
        entries_url = (
            order.raw.get("relationships", {})
            .get("entries", {})
            .get("links", {})
            .get("related")
        )
        if not entries_url:
            return

        headers = {
            "X-Auth-Token": self.api_key,
            "Accept": "application/vnd.api+json",
            "User-Agent": "PostmanRuntime/7.52.0",
        }
        try:
            response = requests.get(entries_url, headers=headers, timeout=(10, self.timeout))
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Failed to fetch order entries for order %s: %s", order.id, exc)
            return

        order.raw["entries"] = payload.get("data") or []


def _build_params(state: str | None, status: str | None, page_size: int | None) -> dict:
    params: dict[str, str] = {}
    params["filter[orders][creationDate][$ge]"] = str(_seven_days_ago_ms())
    params["page[number]"] = "0"
    params["page[size]"] = str(page_size) if page_size is not None else "10"
    return params


def _seven_days_ago_ms() -> int:
    dt = datetime.now(timezone.utc) - timedelta(days=7)
    return int(dt.timestamp() * 1000)
