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
from chaos_engine.chaos.proxy import ChaosProxy
from chaos_engine.core.config import load_config, get_model_name

class PetstoreAgent:
    """
    Agente que opera sobre la API real de Petstore v3 a través de un ChaosProxy.
    """

    def __init__(self, playbook_path: str, verbose: bool = False, mock_mode: bool = None):
        # 1. CARGA EXPLÍCITA DE CREDENCIALES Y CONFIG
        load_dotenv() 
        try:
            self.config = load_config()
            self.model_name = get_model_name(self.config)
        except Exception as e:
            if verbose: print(f"⚠️ Config error: {e}. Using defaults.")
            self.model_name = "gemini-2.0-flash-exp"
            self.config = {"mock_mode": False}

        if not os.getenv("GOOGLE_API_KEY"):
             raise ValueError("❌ CRITICAL: GOOGLE_API_KEY not found.")

        self.playbook_path = playbook_path
        self.playbook_data = self._load_playbook()
        self.verbose = verbose
        
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = self.config.get('mock_mode', False)

        # Estado interno
        self.successful_steps = set()
        self.failure_reason = None

    def _load_playbook(self) -> Dict:
        try:
            with open(self.playbook_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading playbook {self.playbook_path}: {e}")
            return {}

    async def process_order(self, order_id: str, failure_rate: float, seed: int) -> Dict[str, Any]:
        
        proxy = ChaosProxy(
            failure_rate=failure_rate, 
            seed=seed, 
            mock_mode=self.mock_mode,
            verbose=self.verbose
        )
        
        # Reiniciar estado por ejecución
        self.successful_steps = set()
        self.failure_reason = None
        
        # --- TOOLS (Con validación de éxito real) ---
        
        async def get_inventory() -> dict:
            """Returns a map of status codes to quantities."""
            res = await proxy.send_request("GET", "/store/inventory")
            if res.get("status") == "success":
                self.successful_steps.add("get_inventory")
            return res

        async def find_pets_by_status(status: str = "available") -> dict:
            """Finds Pets by status."""
            res = await proxy.send_request("GET", "/pet/findByStatus", params={"status": status})
            if res.get("status") == "success":
                self.successful_steps.add("find_pets_by_status")
            return res

        async def place_order(pet_id: int, quantity: int) -> dict:
            """Place an order for a pet."""
            body = {"petId": pet_id, "quantity": quantity, "status": "placed", "complete": False}
            res = await proxy.send_request("POST", "/store/order", json_body=body)
            if res.get("status") == "success":
                self.successful_steps.add("place_order")
            return res

        async def update_pet_status(pet_id: int, name: str, status: str) -> dict:
            """Update pet status."""
            body = {"id": pet_id, "name": name, "status": status, "photoUrls": []}
            res = await proxy.send_request("PUT", "/pet", json_body=body)
            if res.get("status") == "success":
                self.successful_steps.add("update_pet_status")
            return res

        async def wait_seconds(seconds: float) -> dict:
            """Pauses execution (Backoff strategy)."""
            if self.verbose: print(f"⏳ WAIT STRATEGY: {seconds}s...")
            await asyncio.sleep(seconds)
            return {"status": "success", "message": f"Waited {seconds} seconds"}

        async def lookup_playbook(tool_name: str, error_code: str) -> Dict[str, Any]:
            """Consults the Chaos Playbook."""
            if self.verbose: print(f"📖 PLAYBOOK LOOKUP: {tool_name} -> {error_code}")
            tool_config = self.playbook_data.get(tool_name, {})
            strategy = tool_config.get(str(error_code))
            if strategy:
                return {"status": "success", "found": True, "recommendation": strategy}
            default = self.playbook_data.get("default")
            return {"status": "success", "found": False, "recommendation": default}

        async def report_workflow_failure(reason: str) -> dict:
            """Call if you cannot proceed or playbook says 'fail_fast'."""
            if self.verbose: print(f"💀 FAILURE REPORTED: {reason}")
            self.failure_reason = reason
            return {"status": "success", "message": "Failure reported"}

        # --- AGENT ---
        try:
            adk_agent = LlmAgent(
                name="PetstoreChaosAgent",
                model=Gemini(
                    model=self.model_name,
                    temperature=0.0 
                ),
                instruction=f"""
                Eres un agente de compras AUTÓNOMO. Orden: {order_id}
                
                TU MISIÓN: Completar estos 4 pasos (en orden):
                1. get_inventory
                2. find_pets_by_status
                3. place_order
                4. update_pet_status
                
                SI COMPLETAS EL PASO 4 EXITOSAMENTE:
                - Tu trabajo ha terminado. Detente.
                
                SI ENCUENTRAS ERRORES:
                - Usa `lookup_playbook`.
                - Si es "retry", reintenta.
                - Si es "wait", usa `wait_seconds`.
                - Si es "fail_fast" o imposible, usa `report_workflow_failure`.
                """,
                tools=[
                    get_inventory, find_pets_by_status, place_order, update_pet_status, 
                    lookup_playbook, wait_seconds, report_workflow_failure
                ]
            )

            runner = InMemoryRunner(agent=adk_agent, app_name="chaos_playbook")
            start_time = time.time()
        
            await runner.run_debug(f"Procesa la orden {order_id}.")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # ✅ LÓGICA DE ÉXITO INFALIBLE
            # Si completó los 4 pasos críticos, es un éxito. Punto.
            REQUIRED_STEPS = {"get_inventory", "find_pets_by_status", "place_order", "update_pet_status"}
            
            # Verificamos si todos los pasos requeridos están en el conjunto de pasos exitosos
            is_complete = REQUIRED_STEPS.issubset(self.successful_steps)
            
            status = "success" if is_complete else "failure"
            
            # Debug visual
            if self.verbose:
                print(f"🔍 DEBUG: Steps: {len(self.successful_steps)}/4 -> {status}")
            
            return {
                "status": status,
                "steps_completed": list(self.successful_steps),
                "failed_at": "unknown" if status == "success" else "incomplete_workflow",
                "duration_ms": duration_ms
            }

        except Exception as e:
            print(f"❌ Excepción en runner: {e}")
            return {
                "status": "failure",
                "steps_completed": list(self.successful_steps),
                "failed_at": "exception",
                "error": str(e),
                "duration_ms": 0.0
            }