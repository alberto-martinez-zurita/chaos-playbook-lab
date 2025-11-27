"""
Chaos Proxy - Middleware for Chaos Injection (Phase 6 Enhanced)
Includes Mock Mode and Knowledge-Based Error Injection.
"""
import random
import httpx
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

class ChaosProxy:
    def __init__(self, failure_rate: float, seed: int | None = None, mock_mode: bool = False):
        self.failure_rate = failure_rate
        self.rng = random.Random(seed) if seed is not None else random.Random()
        self.mock_mode = mock_mode
        self.base_url = "https://petstore3.swagger.io/api/v3"
        self.error_codes = self._load_error_codes()

    def _load_error_codes(self) -> Dict[str, str]:
        """Load HTTP error definitions from knowledge base."""
        try:
            # Busca el archivo relativo a la ubicación de este script (src/chaos_playbook_engine/core)
            # Sube 3 niveles para llegar a la raíz del proyecto y entra en data/
            current_dir = Path(__file__).resolve().parent
            project_root = current_dir.parent.parent.parent # Ajusta según tu estructura exacta
            
            # Intento robusto de encontrar el archivo
            possible_paths = [
                Path("data/http_error_codes.json"), # Desde root de ejecución
                current_dir.parent.parent / "data" / "http_error_codes.json", # Relativo
            ]
            
            json_path = None
            for p in possible_paths:
                if p.exists():
                    json_path = p
                    break
            
            if json_path:
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"⚠️ Warning: http_error_codes.json not found in {possible_paths}. Using fallback.")
                return {"500": "Internal Server Error (Fallback)", "503": "Service Unavailable (Fallback)"}
                
        except Exception as e:
            print(f"⚠️ Warning: Error loading http_error_codes.json: {e}")
            return {"500": "Internal Server Error (Fallback)", "503": "Service Unavailable (Fallback)"}

    async def send_request(self, method: str, endpoint: str, params: dict = None, json_body: dict = None) -> Dict[str, Any]:
        """
        Proxy inteligente con Mock Mode.
        """
        # 1. Deterministic Chaos Check
        if self.rng.random() < self.failure_rate:
            # Elegir un error de la lista cargada
            keys = list(self.error_codes.keys())
            if not keys: keys = ["500"] # Fallback safety
            
            error_code = self.rng.choice(keys)
            error_msg = self.error_codes.get(error_code, "Unknown Error")
            
            print(f"🔥 CHAOS INJECTED: Simulating {error_code} on {endpoint}")
            return {
                "status": "error",
                "code": int(error_code),
                "message": f"Simulated Chaos: {error_msg}"
            }

        # 2. Happy Path - MOCK MODE CHECK
        if self.mock_mode:
            print(f"🎭 MOCK API CALL: {method} {endpoint} (Skipping network)")
            return self._generate_mock_response(method, endpoint)
        
        # 3. Real API Call
        print(f"🌐 REAL API CALL: {method} {endpoint}")
        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    resp = await client.get(f"{self.base_url}{endpoint}", params=params, timeout=10.0)
                elif method == "POST":
                    resp = await client.post(f"{self.base_url}{endpoint}", json=json_body, timeout=10.0)
                elif method == "PUT":
                    resp = await client.put(f"{self.base_url}{endpoint}", json=json_body, timeout=10.0)
                
                if resp.status_code >= 400:
                    return {"status": "error", "code": resp.status_code, "message": resp.text}
                return {"status": "success", "code": resp.status_code, "data": resp.json()}
            
            except Exception as e:
                 return {"status": "error", "code": 500, "message": str(e)}

    def _generate_mock_response(self, method: str, endpoint: str) -> Dict[str, Any]:
        """Generate plausible mock data for 200 OK."""
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