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
from dotenv import load_dotenv

# Framework
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner

# Core Logic
from core.chaos_proxy import ChaosProxy
from config.config_loader import load_config, get_model_name

class PetstoreAgent:
    """
    Agente que opera sobre la API real de Petstore v3 a través de un ChaosProxy.
    """

    def __init__(self, playbook_path: str, mock_mode: bool = None):
        # 1. CARGA EXPLÍCITA DE CREDENCIALES Y CONFIG
        load_dotenv() 
        try:
            self.config = load_config()
            self.model_name = get_model_name(self.config)
        except Exception as e:
            print(f"⚠️ Config error: {e}. Using defaults.")
            self.model_name = "gemini-2.0-flash-exp"
            self.config = {"mock_mode": False}

        if not os.getenv("GOOGLE_API_KEY"):
             raise ValueError("❌ CRITICAL: GOOGLE_API_KEY not found.")

        self.playbook_path = playbook_path
        self.playbook_data = self._load_playbook()
        
        # 3. DETERMINAR MOCK MODE (Prioridad: Argumento > Config > False)
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = self.config.get('mock_mode', False)

        # ✅ ESTADO UNIFICADO (String, no booleano)
        self.workflow_status = "unknown" 

    def _load_playbook(self) -> Dict:
        try:
            with open(self.playbook_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading playbook {self.playbook_path}: {e}")
            return {}

    async def process_order(self, order_id: str, failure_rate: float, seed: int) -> Dict[str, Any]:
        
        # INYECCIÓN DE MOCK MODE AL PROXY
        proxy = ChaosProxy(failure_rate=failure_rate, seed=seed, mock_mode=self.mock_mode)
        
        # ✅ RESETEAR ESTADO AL INICIO DE CADA ORDEN
        self.workflow_status = "unknown"
        
        # --- TOOLS ---
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
            """Call ONLY if ALL 4 steps completed successfully."""
            print(f"🎉 SUCCESS REPORTED: {summary}")
            self.workflow_status = "success" # ✅ USO CORRECTO
            return {"status": "success", "message": "Workflow complete"}

        async def report_workflow_failure(reason: str) -> dict:
            """Call if you cannot proceed or playbook says 'fail_fast'."""
            print(f"💀 FAILURE REPORTED: {reason}")
            self.workflow_status = "failure" # ✅ USO CORRECTO
            return {"status": "success", "message": "Failure reported"}

        # --- AGENT ---
        try:
            adk_agent = LlmAgent(
                name="PetstoreChaosAgent",
                model=Gemini(
                    model=self.model_name,
                    temperature=0.0 # ✅ DETERMINISMO
                ),
                instruction=f"""
                Eres un agente de compras AUTÓNOMO. Orden: {order_id}
                
                FLUJO OBLIGATORIO (4 pasos):
                1. get_inventory
                2. find_pets_by_status (usa status='available')
                3. place_order (usa un ID válido del paso 2)
                4. update_pet_status (marca como 'sold')
                
                SI TERMINAS TODO BIEN:
                - Llama a `report_workflow_success`.
                
                SI FALLAS IRRECUPERABLEMENTE:
                - Llama a `report_workflow_failure`.
                
                MANEJO DE ERRORES:
                - Si falla una tool, USA `lookup_playbook`.
                - Si dice "retry", reintenta.
                - Si dice "fail_fast", llama a `report_workflow_failure` inmediatamente.
                """,
                tools=[
                    get_inventory, find_pets_by_status, place_order, update_pet_status, 
                    lookup_playbook, wait_seconds, report_workflow_success, report_workflow_failure
                ]
            )

            # ✅ FIX: Definir app_name explícitamente para evitar warnings
            runner = InMemoryRunner(agent=adk_agent, app_name="chaos_playbook")
            start_time = time.time()
        
            response = await runner.run_debug(f"Procesa la orden {order_id}.")
            
            # FIX DE SEGURIDAD: Si el LLM dice que acabó pero olvidó la tool
            response_text = str(response).lower()
            if self.workflow_status == "unknown": # ✅ USO CORRECTO
                if "completad" in response_text or "success" in response_text:
                     print("⚠️ WARNING: Agent claimed success in text but missed tool call.")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Determinar estado final
            status = self.workflow_status if self.workflow_status != "unknown" else "failure" # ✅ USO CORRECTO
            
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