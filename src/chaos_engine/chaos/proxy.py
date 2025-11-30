"""
Chaos Proxy - Middleware for Chaos Injection.
Updated for New Architecture (assets/knowledge_base).
"""
import random
import httpx
import json
import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path

import math

class ChaosProxy:
    def __init__(self, failure_rate: float, seed: int, mock_mode: bool = False, verbose: bool = False):
        self.failure_rate = failure_rate
        self.rng = random.Random(seed)
        self.mock_mode = mock_mode
        self.verbose = verbose
        self.logger = logging.getLogger("ChaosProxy")
        self.base_url = "https://petstore3.swagger.io/api/v3"
        self.error_codes = self._load_error_codes()
        self.base_delay = 1.0

    def _load_error_codes(self) -> Dict[str, str]:
        """Load HTTP error definitions from knowledge base."""
        try:
            # Calcular la raíz del proyecto desde: src/chaos_engine/chaos/proxy.py
            # Subimos 4 niveles: chaos -> chaos_engine -> src -> ROOT
            current_file = Path(__file__).resolve()
            project_root = current_file.parents[3]
            
            # ✅ RUTA NUEVA CORRECTA (assets/knowledge_base)
            json_path = project_root / "assets" / "knowledge_base" / "http_error_codes.json"
            
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)

            self.logger.warning(f"⚠️ http_error_codes.json not found at {json_path}. Using fallback.")
            return {"500": "Internal Server Error (Fallback)", "503": "Service Unavailable (Fallback)"}
                
        except Exception as e:
            self.logger.warning(f"⚠️ Error loading http_error_codes.json: {e}")
            return {"500": "Internal Server Error (Fallback)", "503": "Service Unavailable (Fallback)"}

    # ✅ NUEVO MÉTODO: Calcular Backoff con Jitter (Pilar IV)
    def calculate_jittered_backoff(self, seconds: float) -> float:
        """
        Calcula el tiempo de espera con Jitter (aleatoriedad).
        Usa el generador del proxy para mantener el determinismo del test.
        """
        # Añade un offset aleatorio de hasta el 50% del tiempo base.
        jitter_factor = 0.5  
        random_offset = self.rng.random() * seconds * jitter_factor
        
        # El backoff final es el tiempo base + el offset aleatorio.
        jittered_delay = seconds + random_offset
        return jittered_delay

    async def send_request(self, method: str, endpoint: str, params: dict = None, json_body: dict = None) -> Dict[str, Any]:
        """
        Proxy inteligente: 
        1. Decide si inyectar caos.
        2. Aplica Zero-Trust (Validación).
        3. Llama a la API real.
        """
        
        # ✅ PILAR V: SEGURIDAD (Validación de Esquema - Zero-Trust)
        if json_body and not isinstance(json_body.get('id'), int) and 'id' in json_body:
             self.logger.error("❌ SEGURIDAD: Esquema inválido detectado (ID no es entero).")
             return {"status": "error", "code": 400, "message": "Input validation failed: ID must be integer."}

        # 1. Chaos Check
        if self.rng.random() < self.failure_rate:
            keys = list(self.error_codes.keys())
            if not keys: keys = ["500"]
            
            error_code = self.rng.choice(keys)
            error_msg = self.error_codes.get(error_code, "Unknown Error")
            
            self.logger.info(f"🔥 CHAOS INJECTED: Simulating {error_code} on {endpoint}")
            return {"status": "error", "code": int(error_code), "message": f"Simulated Chaos: {error_msg}"}

        # 2. Mock Mode
        if self.mock_mode:
            self.logger.info(f"🎭 MOCK API CALL: {method} {endpoint} (Skipping network)")
            return self._generate_mock_response(method, endpoint)
        
        # 3. Real API Call
        self.logger.info(f"🌐 REAL API CALL: {method} {endpoint}")
        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    resp = await client.get(f"{self.base_url}{endpoint}", params=params, timeout=10.0)
                elif method == "POST":
                    resp = await client.post(f"{self.base_url}{endpoint}", json=json_body, timeout=10.0)
                elif method == "PUT":
                    resp = await client.put(f"{self.base_url}{endpoint}", json=json_body, timeout=10.0)
                
                if resp.status_code >= 400:
                    self.logger.warning(f"❌ API Error {resp.status_code}: {resp.text[:100]}")
                    return {"status": "error", "code": resp.status_code, "message": resp.text}
                
                return {"status": "success", "code": resp.status_code, "data": resp.json()}
            
            except Exception as e:
                 self.logger.error(f"💥 Network Exception: {str(e)}")
                 return {"status": "error", "code": 500, "message": str(e)}

    def _generate_mock_response(self, method: str, endpoint: str) -> Dict[str, Any]:
        if "inventory" in endpoint:
            return {"status": "success", "code": 200, "data": {"available": 100, "sold": 5, "pending": 2}}
        elif "findByStatus" in endpoint:
            return {"status": "success", "code": 200, "data": [{"id": 12345, "name": "MockPet", "status": "available"}]}
        elif "order" in endpoint:
            return {"status": "success", "code": 200, "data": {"id": 999, "petId": 12345, "status": "placed", "complete": True}}
        elif "pet" in endpoint and method == "PUT":
             return {"status": "success", "code": 200, "data": {"id": 12345, "name": "MockPet", "status": "sold"}}
        else:
            return {"status": "success", "code": 200, "data": {"message": "Mock success"}}