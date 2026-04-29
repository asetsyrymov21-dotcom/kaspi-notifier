from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Order:
    id: str
    code: Optional[str]
    created_at: Optional[str]
    total_price: Optional[float]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    status: Optional[str]
    state: Optional[str]
    raw: Dict[str, Any]
