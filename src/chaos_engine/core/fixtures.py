"""Centralized mock data fixtures for the Petstore chaos workflow.

All three proxy classes (HTTP, MCP, A2A) and the deterministic/LLM
agents reference these fixtures instead of hardcoding SKU/order data.
"""
from __future__ import annotations

from typing import Any, Dict, Final

PRODUCT_ID: Final[str] = "SKU-1234"
ORDER_ID: Final[str] = "ORD-2026-001"

MOCK_PRODUCTS: Final[list[Dict[str, Any]]] = [
    {"id": "SKU-1234", "name": "Widget Pro", "price": 29.99, "status": "available"},
]

MOCK_INVENTORY: Final[Dict[str, Any]] = {
    "SKU-1234": {"available": 100, "reserved": 5},
}

MOCK_ORDER: Final[Dict[str, Any]] = {
    "orderId": "ORD-2026-001",
    "productId": "SKU-1234",
    "quantity": 1,
    "status": "placed",
}

MOCK_ORDER_CONFIRMATION: Final[Dict[str, Any]] = {
    "orderId": "ORD-2026-001",
    "status": "confirmed",
    "complete": True,
}

MOCK_DATA_BY_ACTION: Final[Dict[str, Any]] = {
    "find_product": MOCK_PRODUCTS,
    "check_inventory": MOCK_INVENTORY,
    "place_order": MOCK_ORDER,
    "confirm_order": MOCK_ORDER_CONFIRMATION,
}
