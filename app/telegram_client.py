import requests

from app.config import Config
from app.logger import setup_logger
from app.models import Order

logger = setup_logger()


class TelegramClient:
    def __init__(self, config: Config):
        self.token = config.telegram_bot_token
        self.chat_id = config.telegram_chat_id
        self.timeout = config.http_timeout
        self.dry_run = config.dry_run

    def send_order_notification(self, order: Order) -> None:
        if self.dry_run:
            logger.info(f"[dry-run] Would send notification for order {order.id}")
            return

        message = self._build_message(order)
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message}

        try:
            response = requests.post(url, data=payload, timeout=self.timeout)
            response.raise_for_status()
            logger.info(f"Sent Telegram notification for order {order.id}")
        except requests.RequestException as exc:
            logger.error(f"Failed to send Telegram message for order {order.id}: {exc}")
            raise

    @staticmethod
    def _build_message(order: Order) -> str:
        parts = [
            f"*Новый заказ* #{order.id}",
        ]
        if order.total_price is not None:
            parts.append(f"Сумма: {order.total_price}")
        if order.customer_name:
            parts.append(f"Покупатель: {order.customer_name}")
        if order.status:
            parts.append(f"Статус: {order.status}")
        if order.created_at:
            parts.append(f"Создан: {order.created_at}")
        return "\n".join(parts)
