"""
Chaos Proxy - Middleware for Chaos Injection (Phase 6)
"""
import random
import httpx
from typing import Dict, Any, Optional

class ChaosProxy:
    def __init__(self, failure_rate: float, seed: int):
        self.failure_rate = failure_rate
        self.rng = random.Random(seed)
        self.base_url = "https://petstore3.swagger.io/api/v3" # URL extraída del petstore3_openapi.json

    async def send_request(self, method: str, endpoint: str, params: dict = None, json_body: dict = None) -> Dict[str, Any]:
        """
        Proxy transparente: Decide si fallar o llamar a la API real.
        """
        # 1. Deterministic Chaos Check
        if self.rng.random() < self.failure_rate:
            error_type = self.rng.choice([404, 503, 408, 429]) # Tipos de fallo soportados por el Playbook
            print(f"🔥 CHAOS INJECTED: Simulating {error_type} on {endpoint}")
            return {
                "status": "error",
                "code": error_type,
                "message": f"Simulated chaos error {error_type}"
            }

        # 2. Real API Call (Happy Path)
        print(f"🌐 REAL API CALL: {method} {endpoint}")
        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    resp = await client.get(f"{self.base_url}{endpoint}", params=params, timeout=10.0)
                elif method == "POST":
                    resp = await client.post(f"{self.base_url}{endpoint}", json=json_body, timeout=10.0)
                elif method == "PUT":
                    resp = await client.put(f"{self.base_url}{endpoint}", json=json_body, timeout=10.0)
                
                # Normalizamos la respuesta para el Agente
                if resp.status_code >= 400:
                    return {"status": "error", "code": resp.status_code, "message": resp.text}
                return {"status": "success", "code": resp.status_code, "data": resp.json()}
            
            except Exception as e:
                 return {"status": "error", "code": 500, "message": str(e)}
