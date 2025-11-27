from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner

import httpx
import random
import json
import asyncio
from typing import Any, Dict, Optional

from core.chaos_proxy import ChaosProxy

# Instancia global para el MVP (en prod se inyectaría)
chaos_proxy = ChaosProxy(failure_rate=0.2, seed=42) # 20% Chaos

# Tool 1: GET /store/inventory
async def get_inventory() -> dict:
    """Returns a map of status codes to quantities from the store."""
    return await chaos_proxy.send_request("GET", "/store/inventory")

# Tool 2: GET /pet/findByStatus
async def find_pets_by_status(status: str = "available") -> dict:
    """Finds Pets by status.
    
    Args:
        status: Status values that need to be considered for filter (available, pending, sold).
    """
    return await chaos_proxy.send_request("GET", "/pet/findByStatus", params={"status": status})

# Tool 3: POST /store/order
async def place_order(pet_id: int, quantity: int) -> dict:
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

# Tool 4: PUT /pet (Update an existing pet)
# Nota: Usamos PUT según tu documento de decisión para el paso 5 "UPDATE_PET_STATUS"
async def update_pet_status(pet_id: int, name: str, status: str) -> dict:
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

# Nueva Tool: Permite al agente ejecutar la estrategia de backoff
async def wait_seconds(seconds: float) -> dict:
    """Pauses execution for a specified number of seconds.
    
    Use this when a playbook strategy recommends waiting or backing off
    before retrying an operation.
    """
    print(f"⏳ AGENT WAITING: {seconds}s (Executing Backoff Strategy)...")
    await asyncio.sleep(seconds)
    return {"status": "success", "message": f"Waited {seconds} seconds"}

# Tool 5: Lookup Playbook (RAG)
async def lookup_playbook(tool_name: str, error_code: str) -> Dict[str, Any]:
    """
    Consults the Chaos Playbook for a recovery strategy.
    
    Args:
        tool_name: The name of the tool that failed (e.g., 'place_order').
        error_code: The HTTP status code or error type (e.g., '503', 'timeout').
    """
    print(f"📖 PLAYBOOK LOOKUP: {tool_name} -> {error_code}")
    
    try:
        with open("../data/playbook_phase6_petstore_2.json", 'r') as f:
            playbook = json.load(f)
        
        # 1. Buscar configuración específica de la tool
        tool_config = playbook.get(tool_name, {})
        
        # 2. Buscar estrategia para ese código de error
        strategy = tool_config.get(str(error_code))
        
        if strategy:
            return {"status": "success", "found": True, "recommendation": strategy}
        
        # 3. Fallback a estrategia default
        return {"status": "success", "found": False, "recommendation": playbook.get("default")}
        
    except Exception as e:
        return {"status": "error", "message": f"Playbook read error: {str(e)}"}


async def run_phase6_mvp():
    agent = LlmAgent(
        name="PetstoreChaosAgent",
        model=Gemini(model="gemini-2.0-flash-lite"),
        instruction="""
        Eres un agente de compras robusto. Tu objetivo es completar el ciclo de compra de una mascota.
        
        FLUJO DE COMPRA:
        1. Consulta el inventario (get_inventory).
        2. Busca una mascota disponible (find_pets_by_status). Elige un ID de la lista.
        3. Compra esa mascota (place_order).
        4. Marca la mascota como vendida (update_pet_status) para mantener consistencia.
        
        PROTOCOLO DE RECUPERACIÓN (CRÍTICO):
        1. Si una herramienta falla, USA INMEDIATAMENTE `lookup_playbook`.
        2. Si el playbook recomienda una estrategia (ej. retry, wait):
           - EJECÚTALA TÚ MISMO INMEDIATAMENTE.
           - NO PIDAS PERMISO AL USUARIO.
           - Si dice "wait", usa la herramienta `wait_seconds`.
           - Si dice "retry", vuelve a llamar a la herramienta fallida con los mismos parámetros.
        3. Solo detente y pregunta al usuario si:
           - El playbook dice explícitamente "escalate_to_human".
           - Has reintentado más de 3 veces sin éxito.
           
        ¡Tu éxito se mide por completar la compra AUTOMÁTICAMENTE a pesar del caos!
        """,
        tools=[get_inventory, find_pets_by_status, place_order, update_pet_status, lookup_playbook, wait_seconds]
    )

    runner = InMemoryRunner(agent=agent)
    
    print("\n🏁 STARTING REAL WORLD CHAOS TEST (Petstore v3)...")
    await runner.run_debug("Compra una mascota disponible.")

if __name__ == "__main__":
    asyncio.run(run_phase6_mvp())


