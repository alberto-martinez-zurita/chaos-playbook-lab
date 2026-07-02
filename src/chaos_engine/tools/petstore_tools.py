from __future__ import annotations

import asyncio

async def get_inventory(chaos_proxy) -> dict:
    """Returns a map of status codes to quantities from the store."""
    return await chaos_proxy.send_request("GET", "/store/inventory")

async def find_pets_by_status(chaos_proxy, status: str = "available") -> dict:
    """Finds Pets by status.
   
    Args:
        status: Status values that need to be considered for filter (available, pending, sold).
    """
    return await chaos_proxy.send_request("GET", "/pet/findByStatus", params={"status": status})

async def place_order(chaos_proxy, pet_id: int, quantity: int) -> dict:
    """Place an order for a pet.
   
    Args:
        pet_id: ID of the pet that needs to be ordered.
        quantity: Quantity of the pet to order.
    """
    body = {
        "petId": pet_id,
        "quantity": quantity,
        "status": "placed",
        "complete": False
    }
    return await chaos_proxy.send_request("POST", "/store/order", json_body=body)

async def update_pet_status(chaos_proxy, pet_id: int, name: str, status: str) -> dict:
    """Update an existing pet status.
   
    Args:
        pet_id: ID of the pet.
        name: Name of the pet (required by API).
        status: New status (available, pending, sold).
    """
    body = {
        "id": pet_id,
        "name": name,
        "status": status,
        "photoUrls": [] # Required by schema
    }
    return await chaos_proxy.send_request("PUT", "/pet", json_body=body)

async def wait_seconds(chaos_proxy,seconds: float) -> dict:
    """Pauses execution for a specified number of seconds.
   
    Use this when a playbook strategy recommends waiting or backing off
    before retrying an operation.
    """
    import logging
    jittered_seconds=chaos_proxy.calculate_jittered_backoff(seconds)
    logging.getLogger(__name__).info("AGENT WAITING: %.2fs (Executing Backoff Strategy)", jittered_seconds)
    await asyncio.sleep(jittered_seconds)
    return {"status": "success", "message": f"Waited {seconds} seconds"}