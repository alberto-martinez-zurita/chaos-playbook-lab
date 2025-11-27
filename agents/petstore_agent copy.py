"""
PetstoreAgent - Real API Chaos Implementation (Phase 6)
=======================================================
Wrapper compatible con run_agent_comparison.py que utiliza
la API real de Petstore con un ChaosProxy intermedio.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional

# Framework
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner

# Core Logic
from core.chaos_proxy import ChaosProxy

class PetstoreAgent:
    """
    Agente que opera sobre la API real de Petstore v3 a través de un ChaosProxy.
    Diseñado para ser instanciado por el framework de pruebas A/B.
    """

    def __init__(self, playbook_path: str):
        self.playbook_path = playbook_path
        self.playbook_data = self._load_playbook()
        print(f"  🤖 PetstoreAgent initialized with: {playbook_path}")

    def _load_playbook(self) -> Dict:
        try:
            with open(self.playbook_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading playbook {self.playbook_path}: {e}")
            return {}

    async def process_order(self, order_id: str, failure_rate: float, seed: int) -> Dict[str, Any]:
        """
        Ejecuta un flujo de compra completo bajo condiciones de caos controladas.
        Cumple con el contrato de interfaz de run_agent_comparison.py.
        """
        
        # 1. Configurar el Chaos Proxy para ESTA ejecución específica (Isolation)
        #    Esto asegura que el seed controle exactamente esta traza.
        proxy = ChaosProxy(failure_rate=failure_rate, seed=seed)
        
        # 2. Definir las Tools dinámicamente (Closures) para capturar el proxy y el playbook
        #    ADK necesita funciones limpias, así que las envolvemos aquí.
        
        async def get_inventory() -> dict:
            """Returns a map of status codes to quantities from the store."""
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
            """Update an existing pet status."""
            body = {
                "id": pet_id,
                "name": name,
                "status": status,
                "photoUrls": []
            }
            return await proxy.send_request("PUT", "/pet", json_body=body)

        async def wait_seconds(seconds: float) -> dict:
            """Pauses execution for a specified number of seconds (Backoff strategy)."""
            print(f"⏳ WAIT STRATEGY: {seconds}s...")
            await asyncio.sleep(seconds)
            return {"status": "success", "message": f"Waited {seconds} seconds"}

        async def lookup_playbook(tool_name: str, error_code: str) -> Dict[str, Any]:
            """Consults the Chaos Playbook for a recovery strategy."""
            print(f"📖 PLAYBOOK LOOKUP: {tool_name} -> {error_code}")
            
            # Buscar config específica o default
            tool_config = self.playbook_data.get(tool_name, {})
            strategy = tool_config.get(str(error_code))
            
            if strategy:
                return {"status": "success", "found": True, "recommendation": strategy}
            
            default = self.playbook_data.get("default")
            return {"status": "success", "found": False, "recommendation": default}

        # 3. Configurar el Agente ADK
        #    Usamos un modelo rápido para las pruebas. En prod sería gemini-1.5-pro.
        adk_agent = LlmAgent(
            name="PetstoreChaosAgent",
            model=Gemini(model="gemini-2.0-flash-lite"),
            instruction=f"""
            Eres un agente de compras AUTÓNOMO para la API Petstore.
            Estás procesando la orden: {order_id}
            
            FLUJO OBLIGATORIO:
            1. get_inventory
            2. find_pets_by_status
            3. place_order
            4. update_pet_status
            
            REGLAS DE RESILIENCIA:
            - Si recibes un error, USA `lookup_playbook`.
            - Si el playbook dice "retry", REINTENTA inmediatamente.
            - Si el playbook dice "wait", USA `wait_seconds` y luego reintenta.
            - NO pidas confirmación al usuario. Actúa autónomamente.
            
            Si completas los 4 pasos, responde con la palabra clave: "WORKFLOW_COMPLETE".
            Si fallas irremediablemente, responde con: "WORKFLOW_FAILED" y la razón.
            """,
            tools=[get_inventory, find_pets_by_status, place_order, update_pet_status, lookup_playbook, wait_seconds]
        )

        runner = InMemoryRunner(agent=adk_agent)

        # 4. Ejecutar
        import time
        start_time = time.time()
        
        try:
            # El prompt inicial dispara el proceso
            response = await runner.run_debug(f"Ejecuta el flujo de compra para la orden {order_id}.")
            response_text = str(response) # Simplificación, en ADK real inspeccionaríamos eventos
            
            duration_ms = (time.time() - start_time) * 1000
            
            # 5. Analizar Resultado (Parsing básico de la respuesta del LLM)
            #    En Fase 5 determinista, sabíamos el estado. En Fase 6 LLM, inferimos del output.
            status = "failure"
            failed_at = None
            steps_completed = []

            # Heurística de parsing de logs del runner (simulada aquí por el texto de respuesta)
            # En una implementación ideal, InMemoryRunner.history nos daría los tool calls exactos.
            # Para este MVP integrado, buscamos palabras clave en la respuesta final.
            
            if "WORKFLOW_COMPLETE" in response_text:
                status = "success"
                steps_completed = ["inventory", "find", "order", "update"]
            else:
                failed_at = "unknown_step" # Mejora futura: parsear historial de eventos
            
            return {
                "status": status,
                "steps_completed": steps_completed,
                "failed_at": failed_at,
                "duration_ms": duration_ms
            }

        except Exception as e:
            return {
                "status": "failure",
                "steps_completed": [],
                "failed_at": "exception",
                "error": str(e),
                "duration_ms": (time.time() - start_time) * 1000
            }