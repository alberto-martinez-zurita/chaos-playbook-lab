"""
PetstoreAgent - Real API Chaos Implementation (Phase 6)
=======================================================
Wrapper compatible con run_agent_comparison.py que utiliza
la API real de Petstore v3 a través de un ChaosProxy intermedio.
"""

import asyncio
import json
import time
import os
from typing import Dict, Any
from dotenv import load_dotenv  # <--- IMPORTANTE

# Framework
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner

# Core Logic
from core.chaos_proxy import ChaosProxy

from config.config_loader import load_config, get_model_name

class PetstoreAgent:
    def __init__(self, playbook_path: str, mock_mode: bool = False): # Añadido mock_mode
        load_dotenv()
        
        # Cargar config
        self.config = load_config()
        self.model_name = get_model_name(self.config) # "gemini-2.0-flash-exp" desde yaml
        
        self.playbook_path = playbook_path
        self.playbook_data = self._load_playbook()
        self.mock_mode = mock_mode
    """
    Agente que opera sobre la API real de Petstore v3 a través de un ChaosProxy.
    """

    def __init__(self, playbook_path: str):
        # 1. CARGA EXPLÍCITA DE CREDENCIALES
        load_dotenv() 
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("❌ CRITICAL: GOOGLE_API_KEY not found in environment. Check your .env file.")

        self.playbook_path = playbook_path
        self.playbook_data = self._load_playbook()
        self.workflow_succeeded = False 

    def _load_playbook(self) -> Dict:
        try:
            with open(self.playbook_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading playbook {self.playbook_path}: {e}")
            return {}

    async def process_order(self, order_id: str, failure_rate: float, seed: int) -> Dict[str, Any]:
        
        # Pasar mock_mode al proxy
        proxy = ChaosProxy(failure_rate=failure_rate, seed=seed, mock_mode=self.mock_mode)
        self.workflow_succeeded = False 
        
        # --- TOOLS (Definidas dentro del scope para capturar el proxy) ---
        
        async def get_inventory() -> dict:
            """Returns a map of status codes to quantities."""
            return await proxy.send_request("GET", "/store/inventory")

        async def find_pets_by_status(status: str = "available") -> dict:
            """Finds Pets by status."""
            return await proxy.send_request("GET", "/pet/findByStatus", params={"status": status})

        async def place_order(pet_id: int, quantity: int) -> dict:
            """Place an order for a pet."""
            body = {
                "petId": pet_id,
                "quantity": quantity,
                "status": "placed",
                "complete": False
            }
            return await proxy.send_request("POST", "/store/order", json_body=body)

        async def update_pet_status(pet_id: int, name: str, status: str) -> dict:
            """Update pet status."""
            body = {
                "id": pet_id,
                "name": name,
                "status": status,
                "photoUrls": []
            }
            return await proxy.send_request("PUT", "/pet", json_body=body)

        async def wait_seconds(seconds: float) -> dict:
            """Pauses execution (Backoff strategy)."""
            print(f"⏳ WAIT STRATEGY: {seconds}s...")
            await asyncio.sleep(seconds)
            return {"status": "success", "message": f"Waited {seconds} seconds"}

        async def lookup_playbook(tool_name: str, error_code: str) -> Dict[str, Any]:
            """Consults the Chaos Playbook."""
            print(f"📖 PLAYBOOK LOOKUP: {tool_name} -> {error_code}")
            tool_config = self.playbook_data.get(tool_name, {})
            strategy = tool_config.get(str(error_code))
            if strategy:
                return {"status": "success", "found": True, "recommendation": strategy}
            default = self.playbook_data.get("default")
            return {"status": "success", "found": False, "recommendation": default}

        async def report_workflow_success(summary: str) -> dict:
            """Call this ONLY when ALL 4 steps are complete."""
            print(f"🎉 WORKFLOW SUCCESS REPORTED: {summary}")
            self.workflow_succeeded = True
            return {"status": "success", "message": "Workflow marked as complete"}

        # --- AGENT ---
        try:
            adk_agent = LlmAgent(
                name="PetstoreChaosAgent",
                model=Gemini(model=self.model_name), # O gemini-1.5-flash
                instruction=f"""
                Eres un agente de compras AUTÓNOMO. Procesando orden: {order_id}
                
                TU MISIÓN: Ejecutar estos 4 pasos en orden:
                1. get_inventory
                2. find_pets_by_status (usa status='available')
                3. place_order (usa un ID válido del paso 2)
                4. update_pet_status (marca como 'sold')
                
                SI TERMINAS LOS 4 PASOS:
                - LLAMA INMEDIATAMENTE A LA HERRAMIENTA `report_workflow_success("Orden completada")`.
                - NO te detengas hasta llamar a esta herramienta.
                
                MANEJO DE ERRORES (Resiliencia):
                - Si una herramienta falla, USA `lookup_playbook`.
                - Si dice "retry", reintenta.
                - Si dice "wait", usa `wait_seconds`.
                """,
                tools=[
                    get_inventory, find_pets_by_status, place_order, update_pet_status, 
                    lookup_playbook, wait_seconds, report_workflow_success
                ]
            )

            runner = InMemoryRunner(agent=adk_agent)
            start_time = time.time()
        
            # Ejecutamos el agente
            await runner.run_debug(f"Inicia el flujo de compra para {order_id}.")
            
            duration_ms = (time.time() - start_time) * 1000
            status = "success" if self.workflow_succeeded else "failure"
            
            return {
                "status": status,
                "steps_completed": [],
                "failed_at": None if status == "success" else "unknown",
                "duration_ms": duration_ms
            }

        except Exception as e:
            print(f"❌ Excepción en runner: {e}")
            return {
                "status": "failure",
                "steps_completed": [],
                "failed_at": "exception",
                "error": str(e),
                "duration_ms": 0.0
            }