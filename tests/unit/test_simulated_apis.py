"""Unit tests for simulated APIs - Phase 1.

Tests verify that each simulated API returns correct response schemas
and handles all supported endpoints properly.
"""

import pytest

from tools.simulated_apis import (
    call_simulated_erp_api,
    call_simulated_inventory_api,
    call_simulated_payments_api,
    call_simulated_shipping_api,
)


@pytest.mark.asyncio
async def test_inventory_api_check_stock() -> None:
    """Test inventory API check_stock endpoint returns correct schema."""
    response = await call_simulated_inventory_api(
        endpoint="check_stock", payload={"sku": "WIDGET-A", "qty": 5}
    )

    assert response["status"] == "success"
    assert "data" in response
    assert response["data"]["sku"] == "WIDGET-A"
    assert response["data"]["available_stock"] >= 5
    assert "metadata" in response
    assert response["metadata"]["api"] == "inventory"
    assert response["metadata"]["endpoint"] == "check_stock"


@pytest.mark.asyncio
async def test_inventory_api_reserve_stock() -> None:
    """Test inventory API reserve_stock endpoint returns reservation ID."""
    response = await call_simulated_inventory_api(
        endpoint="reserve_stock", payload={"sku": "WIDGET-B", "qty": 10}
    )

    assert response["status"] == "success"
    assert "reservation_id" in response["data"]
    assert response["data"]["reservation_id"].startswith("RES-")
    assert response["data"]["reserved_qty"] == 10


@pytest.mark.asyncio
async def test_inventory_api_invalid_endpoint() -> None:
    """Test inventory API raises ValueError for invalid endpoint."""
    with pytest.raises(ValueError, match="Unsupported inventory endpoint"):
        await call_simulated_inventory_api(
            endpoint="invalid_endpoint", payload={}
        )


@pytest.mark.asyncio
async def test_payments_api_capture() -> None:
    """Test payments API capture endpoint processes payment correctly."""
    response = await call_simulated_payments_api(
        endpoint="capture", payload={"amount": 100.0, "currency": "USD"}
    )

    assert response["status"] == "success"
    assert "transaction_id" in response["data"]
    assert response["data"]["transaction_id"].startswith("PAY-")
    assert response["data"]["amount"] == 100.0
    assert response["data"]["currency"] == "USD"
    assert "authorization_code" in response["data"]


@pytest.mark.asyncio
async def test_payments_api_refund() -> None:
    """Test payments API refund endpoint processes refund correctly."""
    response = await call_simulated_payments_api(
        endpoint="refund",
        payload={"transaction_id": "PAY-123456", "amount": 50.0},
    )

    assert response["status"] == "success"
    assert "refund_id" in response["data"]
    assert response["data"]["refund_id"].startswith("REF-")
    assert response["data"]["original_transaction_id"] == "PAY-123456"
    assert response["data"]["refunded_amount"] == 50.0


@pytest.mark.asyncio
async def test_payments_api_invalid_endpoint() -> None:
    """Test payments API raises ValueError for invalid endpoint."""
    with pytest.raises(ValueError, match="Unsupported payments endpoint"):
        await call_simulated_payments_api(endpoint="invalid_endpoint", payload={})


@pytest.mark.asyncio
async def test_erp_api_create_order() -> None:
    """Test ERP API create_order endpoint generates order ID."""
    items = [{"sku": "WIDGET-A", "qty": 5, "price": 29.99}]
    response = await call_simulated_erp_api(
        endpoint="create_order", payload={"user_id": "U123", "items": items}
    )

    assert response["status"] == "success"
    assert "order_id" in response["data"]
    assert response["data"]["order_id"].startswith("ORD-")
    assert response["data"]["user_id"] == "U123"
    assert response["data"]["order_status"] == "CONFIRMED"
    assert "total_amount" in response["data"]


@pytest.mark.asyncio
async def test_erp_api_get_order() -> None:
    """Test ERP API get_order endpoint retrieves order details."""
    response = await call_simulated_erp_api(
        endpoint="get_order", payload={"order_id": "ORD-123"}
    )

    assert response["status"] == "success"
    assert response["data"]["order_id"] == "ORD-123"
    assert "order_status" in response["data"]
    assert "items" in response["data"]


@pytest.mark.asyncio
async def test_erp_api_invalid_endpoint() -> None:
    """Test ERP API raises ValueError for invalid endpoint."""
    with pytest.raises(ValueError, match="Unsupported ERP endpoint"):
        await call_simulated_erp_api(endpoint="invalid_endpoint", payload={})


@pytest.mark.asyncio
async def test_shipping_api_create_shipment() -> None:
    """Test shipping API create_shipment endpoint generates shipment ID."""
    address = {
        "street": "123 Main St",
        "city": "New York",
        "state": "NY",
        "zip": "10001",
    }
    response = await call_simulated_shipping_api(
        endpoint="create_shipment",
        payload={"order_id": "ORD-123", "address": address},
    )

    assert response["status"] == "success"
    assert "shipment_id" in response["data"]
    assert response["data"]["shipment_id"].startswith("SHIP-")
    assert "tracking_number" in response["data"]
    assert response["data"]["tracking_number"].startswith("TRK-")
    assert response["data"]["order_id"] == "ORD-123"


@pytest.mark.asyncio
async def test_shipping_api_track_shipment() -> None:
    """Test shipping API track_shipment endpoint returns tracking info."""
    response = await call_simulated_shipping_api(
        endpoint="track_shipment", payload={"shipment_id": "SHIP-123"}
    )

    assert response["status"] == "success"
    assert response["data"]["shipment_id"] == "SHIP-123"
    assert "current_status" in response["data"]
    assert "events" in response["data"]
    assert isinstance(response["data"]["events"], list)


@pytest.mark.asyncio
async def test_shipping_api_invalid_endpoint() -> None:
    """Test shipping API raises ValueError for invalid endpoint."""
    with pytest.raises(ValueError, match="Unsupported shipping endpoint"):
        await call_simulated_shipping_api(endpoint="invalid_endpoint", payload={})
