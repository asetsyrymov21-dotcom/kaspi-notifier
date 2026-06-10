import requests
from datetime import datetime

from app.config import Config
from app.logger import setup_logger
from app.models import Order

logger = setup_logger()


class TelegramClient:
    def __init__(self, config: Config):
        self.token = config.telegram_bot_token
        self.chat_ids = [chat_id.strip() for chat_id in config.telegram_chat_id.split(",") if chat_id.strip()]
        self.timeout = config.http_timeout
        self.dry_run = config.dry_run

    def send_order_notification(self, order: Order) -> None:
        if self.dry_run:
            logger.info(f"[dry-run] Would send notification for order {order.id}")
            return

        message = self._build_message(order)
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        try:
            for chat_id in self.chat_ids:
                payload = {"chat_id": chat_id, "text": message}
                response = requests.post(url, data=payload, timeout=self.timeout)
                response.raise_for_status()
            logger.info(f"Sent Telegram notification for order {order.id}")
        except requests.RequestException as exc:
            logger.error(f"Failed to send Telegram message for order {order.id}: {exc}")
            raise

    @staticmethod
    def _build_message(order: Order) -> str:
        attributes = order.raw.get("attributes", {})
        parts = [
            f"Новый заказ #{order.code or order.id}",
        ]
        items = _format_items(order.raw.get("entries") or [])
        if items:
            parts.append(f"Товар: {items}")
        if order.total_price is not None:
            parts.append(f"Сумма: {order.total_price}")
        if order.customer_name:
            parts.append(f"Покупатель: {order.customer_name}")
        if order.customer_phone:
            parts.append(f"Телефон: {order.customer_phone}")
        if attributes.get("deliveryMode"):
            parts.append(f"Доставка: {attributes.get('deliveryMode')}")
        address = _format_address(attributes.get("deliveryAddress"))
        if address:
            parts.append(f"Адрес: {address}")
        if order.status:
            parts.append(f"Статус: {order.status}")
        if order.state:
            parts.append(f"Тип: {order.state}")
        created_at = _format_datetime(order.created_at)
        if created_at:
            parts.append(f"Создан: {created_at}")
        return "\n".join(parts)


def _format_items(entries: list[dict]) -> str | None:
    items = []
    for entry in entries:
        attributes = entry.get("attributes", {})
        offer = attributes.get("offer") or {}
        name = offer.get("name") or offer.get("code")
        if not name:
            continue
        quantity = attributes.get("quantity")
        total = attributes.get("totalPrice") or attributes.get("basePrice")
        item = str(name)
        if quantity:
            item = f"{item} x{quantity}"
        if total is not None:
            item = f"{item} ({total})"
        items.append(item)

    return "; ".join(items) if items else None


def _format_address(address: object) -> str | None:
    if isinstance(address, dict):
        formatted = address.get("formattedAddress") or ", ".join(
            str(part)
            for part in [
                address.get("town"),
                address.get("streetName"),
                address.get("streetNumber"),
                address.get("building"),
                address.get("apartment"),
            ]
            if part
        )
        return formatted.strip(" ,") if formatted else None
    return str(address) if address else None


def _format_datetime(value: object) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(value)
