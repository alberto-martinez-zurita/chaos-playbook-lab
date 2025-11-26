"""
chaos_agent_universal.py - v10 UNIVERSAL

Generic Chaos Agent that can simulate ANY OpenAPI 3.0 API.

Features:
- Auto-loads OpenAPI spec from URL or file
- Extracts endpoints and error codes automatically
- Simulates realistic success/error responses
- Deterministic chaos injection (seed-based)
- NO real API calls (full mock)
- Configuration-driven (YAML file)

Usage:
    # Load config
    config = ChaosAgentConfig.from_yaml("config/chaos_agent.yaml")
    
    # Initialize agent
    agent = ChaosAgent(config)
    
    # Simulate API call
    result = await agent.call(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=0.3,
        seed=42
    )

Author: chaos-playbook-engine Phase 3 (v10 UNIVERSAL)
Date: 2025-11-26
"""

import os
import random
import asyncio
import json
import yaml
import requests
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class ChaosAgentConfig:
    """Configuration for ChaosAgent."""
    
    # OpenAPI spec location
    openapi_spec_url: str
    
    # Default chaos settings
    default_failure_rate: float = 0.0
    default_seed: int = 42
    
    # Error code weights (for weighted random selection)
    error_weights: Dict[str, int] = field(default_factory=lambda: {
        "400": 40,  # Bad Request
        "404": 30,  # Not Found
        "422": 20,  # Validation
        "500": 10,  # Server Error
    })
    
    # Mock data generation settings
    mock_success_enabled: bool = True
    mock_list_size: int = 5
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> "ChaosAgentConfig":
        """Load configuration from YAML file."""
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        
        chaos_config = data.get("chaos_agent", {})
        return cls(
            openapi_spec_url=chaos_config.get("openapi_spec_url"),
            default_failure_rate=chaos_config.get("default_failure_rate", 0.0),
            default_seed=chaos_config.get("default_seed", 42),
            error_weights=chaos_config.get("error_weights", {
                "400": 40, "404": 30, "422": 20, "500": 10
            }),
            mock_success_enabled=chaos_config.get("mock_success_enabled", True),
            mock_list_size=chaos_config.get("mock_list_size", 5),
        )


# ============================================================================
# CHAOS AGENT
# ============================================================================

class ChaosAgent:
    """
    Generic Chaos Agent that can simulate ANY OpenAPI 3.0 API.
    
    Loads OpenAPI spec, extracts endpoints/errors, and simulates responses.
    """
    
    def __init__(self, config: ChaosAgentConfig):
        """
        Initialize ChaosAgent with configuration.
        
        Args:
            config: ChaosAgentConfig instance
        """
        self.config = config
        self.spec = self._load_openapi_spec(config.openapi_spec_url)
        self.base_url = self._extract_base_url(self.spec)
        self.endpoints = self._parse_endpoints(self.spec)
        self.chaos_strategies = self._build_chaos_strategies(self.spec)
        
        print(f"✅ ChaosAgent initialized:")
        print(f"   API: {self.spec.get('info', {}).get('title', 'Unknown')}")
        print(f"   Base URL: {self.base_url}")
        print(f"   Endpoints: {len(self.endpoints)}")
        print(f"   Error codes: {sum(len(v) for v in self.chaos_strategies.values())}")
    
    # ========================================================================
    # OPENAPI SPEC LOADING
    # ========================================================================
    
    def _load_openapi_spec(self, spec_url: str) -> dict:
        """Load OpenAPI 3.0 JSON from URL or file path."""
        print(f"📥 Loading OpenAPI spec from: {spec_url}")
        
        if spec_url.startswith("http"):
            response = requests.get(spec_url, timeout=10)
            response.raise_for_status()
            return response.json()
        else:
            with open(spec_url, 'r') as f:
                return json.load(f)
    
    def _extract_base_url(self, spec: dict) -> str:
        """Extract base URL from OpenAPI spec."""
        servers = spec.get("servers", [])
        if servers:
            return servers[0].get("url", "http://localhost")
        return "http://localhost"
    
    def _parse_endpoints(self, spec: dict) -> Dict[str, Dict[str, Any]]:
        """
        Parse endpoints from OpenAPI spec.
        
        Returns:
            {
                "findPetsByStatus": {
                    "path": "/pet/findByStatus",
                    "method": "GET",
                    "parameters": [...],
                    "responses": {...}
                },
                ...
            }
        """
        endpoints = {}
        
        for path, methods in spec.get("paths", {}).items():
            for method, operation in methods.items():
                if method.upper() not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    continue
                
                operation_id = operation.get("operationId")
                if not operation_id:
                    # Generate operationId from path and method
                    operation_id = f"{method}_{path.replace('/', '_')}"
                
                endpoints[operation_id] = {
                    "path": path,
                    "method": method.upper(),
                    "parameters": operation.get("parameters", []),
                    "requestBody": operation.get("requestBody"),
                    "responses": operation.get("responses", {}),
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                }
        
        return endpoints
    
    def _build_chaos_strategies(self, spec: dict) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Extract error codes from OpenAPI spec.
        
        Returns:
            {
                "findPetsByStatus": {
                    "400": {
                        "message": "Invalid status value",
                        "http_method": "GET",
                        "path": "/pet/findByStatus"
                    },
                    "404": {...}
                },
                ...
            }
        """
        strategies = {}
        
        for path, methods in spec.get("paths", {}).items():
            for method, operation in methods.items():
                if method.upper() not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    continue
                
                operation_id = operation.get("operationId")
                if not operation_id:
                    operation_id = f"{method}_{path.replace('/', '_')}"
                
                strategies[operation_id] = {}
                
                # Extract error responses (4xx, 5xx)
                for status_code, response_spec in operation.get("responses", {}).items():
                    if not status_code.startswith(("4", "5")):
                        continue
                    
                    error_message = response_spec.get("description", "No description")
                    strategies[operation_id][status_code] = {
                        "message": error_message,
                        "http_method": method.upper(),
                        "path": path
                    }
        
        return strategies
    
    # ========================================================================
    # CHAOS LOGIC
    # ========================================================================
    
    def _should_inject_chaos(self, failure_rate: float, seed: int) -> bool:
        """Deterministically decide whether to inject chaos."""
        if failure_rate <= 0.0:
            return False
        if failure_rate >= 1.0:
            return True
        
        rng = random.Random(seed)
        return rng.random() < failure_rate
    
    def _select_error_code(self, tool_name: str, seed: int) -> str:
        """
        Select which error code to inject for this tool.
        
        Uses weighted random selection based on config.error_weights.
        """
        if tool_name not in self.chaos_strategies:
            return "400"  # Default
        
        available_errors = list(self.chaos_strategies[tool_name].keys())
        if not available_errors:
            return "400"
        
        # Get weights for available errors
        weights = []
        for code in available_errors:
            weight = self.config.error_weights.get(code, 10)
            weights.append(weight)
        
        # Deterministic selection
        rng = random.Random(seed)
        return rng.choices(available_errors, weights=weights, k=1)[0]
    
    # ========================================================================
    # MOCK RESPONSES
    # ========================================================================
    
    def _generate_mock_success_data(self, tool_name: str) -> Any:
        """
        Generate realistic mock data for success response.
        
        Based on operation type and OpenAPI schema (if available).
        """
        if tool_name not in self.endpoints:
            return {"message": "Success"}
        
        endpoint = self.endpoints[tool_name]
        method = endpoint["method"]
        
        # GET operations: return list or single object
        if method == "GET":
            if "find" in tool_name.lower() or "list" in tool_name.lower():
                # Return list
                return [
                    {"id": i, "name": f"Item-{i}", "status": "active"}
                    for i in range(1, self.config.mock_list_size + 1)
                ]
            else:
                # Return single object
                return {"id": 1, "name": "Item-1", "status": "active"}
        
        # POST/PUT: return created/updated object with ID
        elif method in ["POST", "PUT"]:
            return {
                "id": random.randint(1000, 9999),
                "status": "success",
                "message": f"{method} operation completed"
            }
        
        # DELETE: return confirmation
        elif method == "DELETE":
            return {
                "status": "deleted",
                "message": "Resource deleted successfully"
            }
        
        return {"message": "Success"}
    
    def _mock_success_response(self, tool_name: str, params: dict) -> dict:
        """Return mocked success response (HTTP 200)."""
        if not self.config.mock_success_enabled:
            return {
                "status_code": 200,
                "body": {"message": "Success (mock disabled)"},
                "error": None,
                "tool_name": tool_name,
                "chaos_injected": False
            }
        
        body = self._generate_mock_success_data(tool_name)
        
        return {
            "status_code": 200,
            "body": body,
            "error": None,
            "tool_name": tool_name,
            "chaos_injected": False
        }
    
    def _mock_error_response(self, tool_name: str, error_code: str) -> dict:
        """Return mocked error response."""
        if tool_name not in self.chaos_strategies:
            # Unknown tool
            return {
                "status_code": 404,
                "body": {
                    "code": 404,
                    "type": "error",
                    "message": f"Unknown operation: {tool_name}"
                },
                "error": "Unknown operation",
                "tool_name": tool_name,
                "chaos_injected": False
            }
        
        strategy = self.chaos_strategies[tool_name].get(error_code)
        if not strategy:
            # Fallback to 500
            return {
                "status_code": 500,
                "body": {
                    "code": 500,
                    "type": "error",
                    "message": "Internal server error"
                },
                "error": "Internal error",
                "tool_name": tool_name,
                "chaos_injected": True
            }
        
        return {
            "status_code": int(error_code),
            "body": {
                "code": int(error_code),
                "type": "error",
                "message": strategy["message"]
            },
            "error": f"HTTP {error_code}",
            "tool_name": tool_name,
            "chaos_injected": True
        }
    
    # ========================================================================
    # PUBLIC API
    # ========================================================================
    
    async def call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        failure_rate: Optional[float] = None,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Simulate API call with optional chaos injection.
        
        Args:
            tool_name: Operation ID from OpenAPI spec
            params: Parameters for the API call
            failure_rate: Probability of error (0.0 to 1.0). 
                         Uses config default if None.
            seed: Random seed for determinism. 
                  Uses config default if None.
        
        Returns:
            dict: {
                "status_code": int,
                "body": dict,
                "error": str or None,
                "tool_name": str,
                "chaos_injected": bool
            }
        """
        # Use defaults from config if not provided
        if failure_rate is None:
            failure_rate = self.config.default_failure_rate
        if seed is None:
            seed = self.config.default_seed
        
        # Decide: inject chaos?
        inject_chaos = self._should_inject_chaos(failure_rate, seed)
        
        if not inject_chaos:
            # Return success mock
            return self._mock_success_response(tool_name, params)
        
        # Select error code and return error mock
        error_code = self._select_error_code(tool_name, seed)
        return self._mock_error_response(tool_name, error_code)
    
    def get_available_operations(self) -> List[str]:
        """Return list of all available operation IDs."""
        return list(self.endpoints.keys())
    
    def get_error_codes_for_operation(self, tool_name: str) -> List[str]:
        """Return list of error codes for a specific operation."""
        if tool_name not in self.chaos_strategies:
            return []
        return list(self.chaos_strategies[tool_name].keys())


# ============================================================================
# TESTING
# ============================================================================

async def test_chaos_agent():
    """Test ChaosAgent with Petstore API."""
    print("\n" + "="*70)
    print("CHAOS AGENT v10 - Universal OpenAPI 3.0 Simulator")
    print("="*70)
    
    # Load config
    config = ChaosAgentConfig(
        openapi_spec_url="https://petstore3.swagger.io/api/v3/openapi.json",
        default_failure_rate=0.0,
        default_seed=42
    )
    
    # Initialize agent
    agent = ChaosAgent(config)
    
    print(f"\n📋 Available operations: {len(agent.get_available_operations())}")
    print(f"   Examples: {agent.get_available_operations()[:5]}")
    
    # Test 1: Success (no chaos)
    print("\n[TEST 1] No chaos - findPetsByStatus")
    result1 = await agent.call(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=0.0,
        seed=42
    )
    print(f"   Status: {result1['status_code']}, Chaos: {result1['chaos_injected']}")
    print(f"   Body: {str(result1['body'])[:100]}...")
    
    # Test 2: Chaos (400 error)
    print("\n[TEST 2] With chaos - findPetsByStatus (30% failure rate)")
    result2 = await agent.call(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=1.0,  # Force chaos
        seed=42
    )
    print(f"   Status: {result2['status_code']}, Chaos: {result2['chaos_injected']}")
    print(f"   Error: {result2.get('error')}")
    print(f"   Body: {result2['body']}")
    
    # Test 3: Different error code
    print("\n[TEST 3] With chaos - getPetById (different seed)")
    result3 = await agent.call(
        tool_name="getPetById",
        params={"petId": 1},
        failure_rate=1.0,
        seed=100
    )
    print(f"   Status: {result3['status_code']}, Chaos: {result3['chaos_injected']}")
    print(f"   Error: {result3.get('error')}")
    print(f"   Body: {result3['body']}")
    
    # Test 4: Available error codes
    print("\n[TEST 4] Available error codes for operations:")
    for op in ["findPetsByStatus", "getPetById", "placeOrder"]:
        codes = agent.get_error_codes_for_operation(op)
        print(f"   {op}: {codes}")
    
    print("\n" + "="*70)
    print("✅ CHAOS AGENT v10 TEST COMPLETED")
    print("="*70)


if __name__ == "__main__":
    print("🧪 Testing ChaosAgent v10 (Universal)...")
    asyncio.run(test_chaos_agent())
