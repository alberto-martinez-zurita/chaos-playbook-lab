"""
Simulated APIs for chaos testing - Phase 5 (Unified with ChaosProxy).

This module provides simulated implementations of external APIs used by the
OrderOrchestratorAgent.

UNIFICATION UPDATE:
Now accepts an optional `chaos_proxy` instance to support stateful chaos 
(continuous random sequence) across an entire experiment workflow.
Fallbacks to salted-seed ephemeral proxies if no instance is provided.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

# Imports de configuración y Core
from chaos_engine.chaos.config import ChaosConfig
from chaos_engine.chaos.proxy import ChaosProxy

async def _check_chaos(
    endpoint_path: str, 
    method: str,
    chaos_config: Optional[ChaosConfig] = None,
    chaos_proxy: Optional[ChaosProxy] = None
) -> Optional[Dict[str, Any]]:
    """
    Helper privado que decide qué motor de caos usar.
    Prioridad: 
    1. chaos_proxy (Instancia persistente, mantiene estado del RNG).
    2. chaos_config (Instancia efímera, usa 'salting' para evitar correlación).
    """
    active_proxy = chaos_proxy
    
    # Si no hay proxy inyectado, creamos uno efímero (Fallback Legacy)
    if not active_proxy and chaos_config and chaos_config.enabled:
        # SALTING: Calculamos offset basado en el nombre para evitar que
        # Inventory y Payment fallen idénticamente si usan la misma semilla base.
        seed_offset = sum(ord(c) for c in endpoint_path)
        effective_seed = (chaos_config.seed or 0) + seed_offset
        
        active_proxy = ChaosProxy(
            failure_rate=chaos_config.failure_rate,
            seed=effective_seed,
            mock_mode=True,
            verbose=chaos_config.verbose
        )
    
    # Si tenemos un proxy (inyectado o efímero), lo usamos
    if active_proxy:
        # mock_mode=True fuerza al proxy a devolver un dict falso en éxito,
        # o un error de caos si toca fallar.
        result = await active_proxy.send_request(method, endpoint_path)
        
        if result["status"] == "error":
            # Enriquecemos para logs de Fase 5
            result["metadata"] = {
                "chaos_injected": True,
                "source": "ChaosProxy",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            return result
            
    return None

async def call_simulated_inventory_api(
    endpoint: str,
    payload: Dict[str, Any],
    chaos_config: Optional[ChaosConfig] = None,
    chaos_proxy: Optional[ChaosProxy] = None  # ✅ NEW: Inyección de Proxy
) -> Dict[str, Any]:
    """Simulate inventory API calls."""
    
    # 1. Chequeo de caos (inyectado o config)
    chaos_error = await _check_chaos(f"/store/inventory/{endpoint}", "GET", chaos_config, chaos_proxy)
    if chaos_error:
        return chaos_error
    
    # 2. Happy Path
    await asyncio.sleep(0.1)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if endpoint == "check_stock":
        sku = payload.get("sku", "UNKNOWN")
        return {
            "status": "success",
            "data": {
                "sku": sku,
                "available_stock": 100,
                "reserved": 0,
                "warehouse": "WH-001",
            },
            "metadata": {"api": "inventory", "endpoint": endpoint, "timestamp": timestamp}
        }
    elif endpoint == "reserve_stock":
        reservation_id = f"RES-{uuid4().hex[:8].upper()}"
        return {
            "status": "success",
            "data": {
                "sku": payload.get("sku"),
                "reserved_qty": payload.get("qty"),
                "reservation_id": reservation_id,
            },
            "metadata": {"api": "inventory", "endpoint": endpoint, "timestamp": timestamp}
        }
    else:
        raise ValueError(f"Unsupported inventory endpoint: {endpoint}")


async def call_simulated_payments_api(
    endpoint: str,
    payload: Dict[str, Any],
    chaos_config: Optional[ChaosConfig] = None,
    chaos_proxy: Optional[ChaosProxy] = None # ✅ NEW
) -> Dict[str, Any]:
    """Simulate payments API calls."""
    
    chaos_error = await _check_chaos(f"/store/payment/{endpoint}", "POST", chaos_config, chaos_proxy)
    if chaos_error:
        return chaos_error
    
    await asyncio.sleep(0.1)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if endpoint == "capture":
        return {
            "status": "success",
            "data": {
                "transaction_id": f"PAY-{uuid4().hex[:12].upper()}",
                "amount": payload.get("amount"),
                "currency": payload.get("currency", "USD"),
                "authorization_code": f"AUTH-{uuid4().hex[:6].upper()}",
            },
            "metadata": {"api": "payments", "endpoint": endpoint, "timestamp": timestamp}
        }
    elif endpoint == "refund":
        return {
            "status": "success",
            "data": {
                "refund_id": f"REF-{uuid4().hex[:12].upper()}",
                "original_transaction_id": payload.get("transaction_id"),
            },
            "metadata": {"api": "payments", "endpoint": endpoint, "timestamp": timestamp}
        }
    else:
        raise ValueError(f"Unsupported payments endpoint: {endpoint}")


async def call_simulated_erp_api(
    endpoint: str,
    payload: Dict[str, Any],
    chaos_config: Optional[ChaosConfig] = None,
    chaos_proxy: Optional[ChaosProxy] = None # ✅ NEW
) -> Dict[str, Any]:
    """Simulate ERP API calls."""
    
    chaos_error = await _check_chaos(f"/erp/{endpoint}", "POST", chaos_config, chaos_proxy)
    if chaos_error:
        return chaos_error
    
    await asyncio.sleep(0.1)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if endpoint == "create_order":
        return {
            "status": "success",
            "data": {
                "order_id": f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
                "user_id": payload.get("user_id"),
                "order_status": "CONFIRMED",
            },
            "metadata": {"api": "erp", "endpoint": endpoint, "timestamp": timestamp}
        }
    elif endpoint == "get_order":
        return {
            "status": "success",
            "data": {
                "order_id": payload.get("order_id"),
                "order_status": "CONFIRMED",
            },
            "metadata": {"api": "erp", "endpoint": endpoint, "timestamp": timestamp}
        }
    else:
        raise ValueError(f"Unsupported ERP endpoint: {endpoint}")


async def call_simulated_shipping_api(
    endpoint: str,
    payload: Dict[str, Any],
    chaos_config: Optional[ChaosConfig] = None,
    chaos_proxy: Optional[ChaosProxy] = None # ✅ NEW
) -> Dict[str, Any]:
    """Simulate shipping API calls."""
    
    chaos_error = await _check_chaos(f"/shipping/{endpoint}", "POST", chaos_config, chaos_proxy)
    if chaos_error:
        return chaos_error
    
    await asyncio.sleep(0.1)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if endpoint == "create_shipment":
        return {
            "status": "success",
            "data": {
                "shipment_id": f"SHIP-{uuid4().hex[:12].upper()}",
                "tracking_number": f"TRK-{uuid4().hex[:16].upper()}",
                "status": "LABEL_CREATED",
            },
            "metadata": {"api": "shipping", "endpoint": endpoint, "timestamp": timestamp}
        }
    elif endpoint == "track_shipment":
        return {
            "status": "success",
            "data": {
                "shipment_id": payload.get("shipment_id"),
                "current_status": "IN_TRANSIT",
            },
            "metadata": {"api": "shipping", "endpoint": endpoint, "timestamp": timestamp}
        }
    else:
        raise ValueError(f"Unsupported shipping endpoint: {endpoint}")