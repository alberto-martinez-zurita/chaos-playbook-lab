"""
Simulated APIs for chaos testing - Phase 2 (with chaos injection).

This module provides simulated implementations of external APIs used by the
OrderOrchestratorAgent.

Phase 1: All APIs operate in happy-path mode (chaos_config=None)
Phase 2: Chaos injection supported via optional chaos_config parameter

APIs implemented:
- Inventory API: Stock checking and reservation
- Payments API: Payment capture and refunds
- ERP API: Order creation and retrieval
- Shipping API: Shipment creation and tracking

Based on: ADR-006 (Chaos Injection Points Architecture)
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

# Phase 2: Chaos injection imports
from chaos_playbook_engine.config.chaos_config import ChaosConfig
from chaos_playbook_engine.tools.chaos_injection_helper import inject_chaos_failure


async def call_simulated_inventory_api(
    endpoint: str,
    payload: Dict[str, Any],
    chaos_config: Optional[ChaosConfig] = None  # Phase 2: NEW parameter
) -> Dict[str, Any]:
    """
    Simulate inventory API calls.
    
    Args:
        endpoint: API endpoint path ('check_stock', 'reserve_stock')
        payload: Request body with parameters
        chaos_config: Optional chaos configuration (None = happy-path)
    
    Returns:
        Simulated API response dictionary with status, data, and metadata
    
    Raises:
        ValueError: If endpoint is not supported
    
    Example:
        >>> response = await call_simulated_inventory_api(
        ...     endpoint="check_stock",
        ...     payload={"sku": "WIDGET-A", "qty": 5}
        ... )
        >>> response["status"]
        'success'
    """
    
    # ═════════════════════════════════════════════════════════════
    # PHASE 2: CHAOS INJECTION POINT
    # ═════════════════════════════════════════════════════════════
    
    if chaos_config and chaos_config.should_inject_failure():
        return await inject_chaos_failure("inventory", endpoint, chaos_config)
    
    # ═════════════════════════════════════════════════════════════
    # PHASE 1: HAPPY-PATH LOGIC (unchanged)
    # ═════════════════════════════════════════════════════════════
    
    await asyncio.sleep(0.8)  # V3: 0.05 → 0.8s (realistic network + DB)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if endpoint == "check_stock":
        sku = payload.get("sku", "UNKNOWN")
        qty = payload.get("qty", 0)
        
        return {
            "status": "success",
            "data": {
                "sku": sku,
                "available_stock": 100,  # Always sufficient in happy-path
                "reserved": 0,
                "warehouse": "WH-001",
            },
            "metadata": {
                "api": "inventory",
                "endpoint": endpoint,
                "timestamp": timestamp,
                "request_id": str(uuid4()),
            },
        }
    
    elif endpoint == "reserve_stock":
        sku = payload.get("sku", "UNKNOWN")
        qty = payload.get("qty", 0)
        reservation_id = f"RES-{uuid4().hex[:8].upper()}"
        
        return {
            "status": "success",
            "data": {
                "sku": sku,
                "reserved_qty": qty,
                "reservation_id": reservation_id,
                "expires_at": "2025-11-23T08:00:00Z",
            },
            "metadata": {
                "api": "inventory",
                "endpoint": endpoint,
                "timestamp": timestamp,
                "request_id": str(uuid4()),
            },
        }
    
    else:
        raise ValueError(f"Unsupported inventory endpoint: {endpoint}")


async def call_simulated_payments_api(
    endpoint: str,
    payload: Dict[str, Any],
    chaos_config: Optional[ChaosConfig] = None  # Phase 2: NEW parameter
) -> Dict[str, Any]:
    """
    Simulate payments API calls.
    
    Args:
        endpoint: API endpoint path ('capture', 'refund')
        payload: Request body with parameters
        chaos_config: Optional chaos configuration (None = happy-path)
    
    Returns:
        Simulated API response dictionary with status, data, and metadata
    
    Raises:
        ValueError: If endpoint is not supported
    
    Example:
        >>> response = await call_simulated_payments_api(
        ...     endpoint="capture",
        ...     payload={"amount": 100.0, "currency": "USD"}
        ... )
        >>> response["data"]["transaction_id"]
        'PAY-...'
    """
    
    # ═════════════════════════════════════════════════════════════
    # PHASE 2: CHAOS INJECTION POINT
    # ═════════════════════════════════════════════════════════════
    
    if chaos_config and chaos_config.should_inject_failure():
        return await inject_chaos_failure("payments", endpoint, chaos_config)
    
    # ═════════════════════════════════════════════════════════════
    # PHASE 1: HAPPY-PATH LOGIC (unchanged)
    # ═════════════════════════════════════════════════════════════
    
    await asyncio.sleep(1.2)  # V3: 0.08 → 1.2s (payment gateway + auth)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if endpoint == "capture":
        amount = payload.get("amount", 0.0)
        currency = payload.get("currency", "USD")
        transaction_id = f"PAY-{uuid4().hex[:12].upper()}"
        
        return {
            "status": "success",
            "data": {
                "transaction_id": transaction_id,
                "amount": amount,
                "currency": currency,
                "payment_method": "CREDIT_CARD",
                "authorization_code": f"AUTH-{uuid4().hex[:6].upper()}",
                "captured_at": timestamp,
            },
            "metadata": {
                "api": "payments",
                "endpoint": endpoint,
                "timestamp": timestamp,
                "request_id": str(uuid4()),
            },
        }
    
    elif endpoint == "refund":
        transaction_id = payload.get("transaction_id", "UNKNOWN")
        amount = payload.get("amount", 0.0)
        refund_id = f"REF-{uuid4().hex[:12].upper()}"
        
        return {
            "status": "success",
            "data": {
                "refund_id": refund_id,
                "original_transaction_id": transaction_id,
                "refunded_amount": amount,
                "refunded_at": timestamp,
            },
            "metadata": {
                "api": "payments",
                "endpoint": endpoint,
                "timestamp": timestamp,
                "request_id": str(uuid4()),
            },
        }
    
    else:
        raise ValueError(f"Unsupported payments endpoint: {endpoint}")


async def call_simulated_erp_api(
    endpoint: str,
    payload: Dict[str, Any],
    chaos_config: Optional[ChaosConfig] = None  # Phase 2: NEW parameter
) -> Dict[str, Any]:
    """
    Simulate ERP (Enterprise Resource Planning) API calls.
    
    Args:
        endpoint: API endpoint path ('create_order', 'get_order')
        payload: Request body with parameters
        chaos_config: Optional chaos configuration (None = happy-path)
    
    Returns:
        Simulated API response dictionary with status, data, and metadata
    
    Raises:
        ValueError: If endpoint is not supported
    
    Example:
        >>> response = await call_simulated_erp_api(
        ...     endpoint="create_order",
        ...     payload={"user_id": "U123", "items": [{"sku": "WIDGET-A"}]}
        ... )
        >>> response["data"]["order_id"]
        'ORD-...'
    """
    
    # ═════════════════════════════════════════════════════════════
    # PHASE 2: CHAOS INJECTION POINT
    # ═════════════════════════════════════════════════════════════
    
    if chaos_config and chaos_config.should_inject_failure():
        return await inject_chaos_failure("erp", endpoint, chaos_config)
    
    # ═════════════════════════════════════════════════════════════
    # PHASE 1: HAPPY-PATH LOGIC (unchanged)
    # ═════════════════════════════════════════════════════════════
    
    await asyncio.sleep(1.5)  # V3: 0.12 → 1.5s (complex business logic)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if endpoint == "create_order":
        user_id = payload.get("user_id", "UNKNOWN")
        items = payload.get("items", [])
        order_id = f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
        
        return {
            "status": "success",
            "data": {
                "order_id": order_id,
                "user_id": user_id,
                "items": items,
                "order_status": "CONFIRMED",
                "created_at": timestamp,
                "total_amount": sum(
                    item.get("price", 0) * item.get("qty", 1) for item in items
                ),
            },
            "metadata": {
                "api": "erp",
                "endpoint": endpoint,
                "timestamp": timestamp,
                "request_id": str(uuid4()),
            },
        }
    
    elif endpoint == "get_order":
        order_id = payload.get("order_id", "UNKNOWN")
        
        return {
            "status": "success",
            "data": {
                "order_id": order_id,
                "order_status": "CONFIRMED",
                "created_at": "2025-11-22T08:00:00Z",
                "items": [{"sku": "WIDGET-A", "qty": 5}],
            },
            "metadata": {
                "api": "erp",
                "endpoint": endpoint,
                "timestamp": timestamp,
                "request_id": str(uuid4()),
            },
        }
    
    else:
        raise ValueError(f"Unsupported ERP endpoint: {endpoint}")


async def call_simulated_shipping_api(
    endpoint: str,
    payload: Dict[str, Any],
    chaos_config: Optional[ChaosConfig] = None  # Phase 2: NEW parameter
) -> Dict[str, Any]:
    """
    Simulate shipping/logistics API calls.
    
    Args:
        endpoint: API endpoint path ('create_shipment', 'track_shipment')
        payload: Request body with parameters
        chaos_config: Optional chaos configuration (None = happy-path)
    
    Returns:
        Simulated API response dictionary with status, data, and metadata
    
    Raises:
        ValueError: If endpoint is not supported
    
    Example:
        >>> response = await call_simulated_shipping_api(
        ...     endpoint="create_shipment",
        ...     payload={"order_id": "ORD-123", "address": {...}}
        ... )
        >>> response["data"]["shipment_id"]
        'SHIP-...'
    """
    
    # ═════════════════════════════════════════════════════════════
    # PHASE 2: CHAOS INJECTION POINT
    # ═════════════════════════════════════════════════════════════
    
    if chaos_config and chaos_config.should_inject_failure():
        return await inject_chaos_failure("shipping", endpoint, chaos_config)
    
    # ═════════════════════════════════════════════════════════════
    # PHASE 1: HAPPY-PATH LOGIC (unchanged)
    # ═════════════════════════════════════════════════════════════
    
    await asyncio.sleep(1.0)  # V3: 0.10 → 1.0s (shipping provider API)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if endpoint == "create_shipment":
        order_id = payload.get("order_id", "UNKNOWN")
        address = payload.get("address", {})
        shipment_id = f"SHIP-{uuid4().hex[:12].upper()}"
        tracking_number = f"TRK-{uuid4().hex[:16].upper()}"
        
        return {
            "status": "success",
            "data": {
                "shipment_id": shipment_id,
                "order_id": order_id,
                "tracking_number": tracking_number,
                "carrier": "FastShip Express",
                "service_level": "STANDARD",
                "estimated_delivery": "2025-11-25T18:00:00Z",
                "shipping_address": address,
                "status": "LABEL_CREATED",
            },
            "metadata": {
                "api": "shipping",
                "endpoint": endpoint,
                "timestamp": timestamp,
                "request_id": str(uuid4()),
            },
        }
    
    elif endpoint == "track_shipment":
        shipment_id = payload.get("shipment_id", "UNKNOWN")
        
        return {
            "status": "success",
            "data": {
                "shipment_id": shipment_id,
                "tracking_number": f"TRK-{uuid4().hex[:16].upper()}",
                "current_status": "IN_TRANSIT",
                "location": "Distribution Center - Chicago, IL",
                "estimated_delivery": "2025-11-25T18:00:00Z",
                "events": [
                    {
                        "timestamp": "2025-11-22T10:00:00Z",
                        "status": "PICKED_UP",
                        "location": "Warehouse - Newark, NJ",
                    },
                    {
                        "timestamp": "2025-11-22T14:30:00Z",
                        "status": "IN_TRANSIT",
                        "location": "Distribution Center - Chicago, IL",
                    },
                ],
            },
            "metadata": {
                "api": "shipping",
                "endpoint": endpoint,
                "timestamp": timestamp,
                "request_id": str(uuid4()),
            },
        }
    
    else:
        raise ValueError(f"Unsupported shipping endpoint: {endpoint}")
