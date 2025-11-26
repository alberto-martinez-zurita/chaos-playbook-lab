"""
chaos_agent_petstore.py - FINAL PRODUCTION VERSION

Direct HTTP implementation with realistic error responses for ALL Petstore API error codes.

COVERAGE:
- HTTP 400: Bad Request (invalid params, validation errors)
- HTTP 404: Not Found (missing resources)
- HTTP 422: Validation Exception (business logic errors)
- HTTP 500: Internal Server Error (server failures)

CHAOS MODES:
- No chaos (failure_rate=0.0): Real API calls, pass-through
- With chaos (failure_rate>0.0): Inject realistic errors matching Petstore API spec

AUTHOR: chaos-playbook-engine Phase 3 (v9 PRODUCTION)
DATE: 2025-11-26
"""

import os
import random
import asyncio
import json
import requests
from typing import Dict, Any, Optional
from pathlib import Path


# ============================================================================
# CONFIGURATION
# ============================================================================

PETSTORE_BASE_URL = "https://petstore3.swagger.io"

# Tool → Endpoint mapping (from Swagger spec)
TOOL_TO_ENDPOINT = {
    # Pet operations
    "updatePet": ("/api/v3/pet", "PUT"),
    "addPet": ("/api/v3/pet", "POST"),
    "findPetsByStatus": ("/api/v3/pet/findByStatus", "GET"),
    "findPetsByTags": ("/api/v3/pet/findByTags", "GET"),
    "getPetById": ("/api/v3/pet/{petId}", "GET"),
    "updatePetWithForm": ("/api/v3/pet/{petId}", "POST"),
    "deletePet": ("/api/v3/pet/{petId}", "DELETE"),
    "uploadFile": ("/api/v3/pet/{petId}/uploadImage", "POST"),
    
    # Store operations
    "getInventory": ("/api/v3/store/inventory", "GET"),
    "placeOrder": ("/api/v3/store/order", "POST"),
    "getOrderById": ("/api/v3/store/order/{orderId}", "GET"),
    "deleteOrder": ("/api/v3/store/order/{orderId}", "DELETE"),
    
    # User operations
    "createUser": ("/api/v3/user", "POST"),
    "createUsersWithListInput": ("/api/v3/user/createWithList", "POST"),
    "loginUser": ("/api/v3/user/login", "GET"),
    "logoutUser": ("/api/v3/user/logout", "GET"),
    "getUserByName": ("/api/v3/user/{username}", "GET"),
    "updateUser": ("/api/v3/user/{username}", "PUT"),
    "deleteUser": ("/api/v3/user/{username}", "DELETE"),
}

# Chaos injection strategies per tool
CHAOS_STRATEGIES = {
    # Pet operations - 400 errors
    "findPetsByStatus": {
        "400": {"param": "status", "value": "invalid_status_xyz", "message": "Invalid status value"},
        "404": None,  # GET, not applicable
    },
    "findPetsByTags": {
        "400": {"param": "tags", "value": "invalid_tag_xyz", "message": "Invalid tag value"},
        "404": None,
    },
    "getPetById": {
        "400": {"param": "petId", "value": "invalid_id", "message": "Invalid ID supplied"},
        "404": {"param": "petId", "value": 999999, "message": "Pet not found"},
    },
    "updatePet": {
        "400": {"body_field": "id", "value": "invalid_id", "message": "Invalid ID supplied"},
        "404": {"body_field": "id", "value": 999999, "message": "Pet not found"},
        "422": {"body_field": "name", "value": None, "message": "Validation exception"},
    },
    "addPet": {
        "400": {"body_field": "name", "value": "", "message": "Invalid input"},
        "422": {"body_field": "photoUrls", "value": None, "message": "Validation exception"},
    },
    "updatePetWithForm": {
        "400": {"body_field": "name", "value": "", "message": "Invalid input"},
    },
    "deletePet": {
        "400": {"param": "petId", "value": "invalid_id", "message": "Invalid pet value"},
        "404": {"param": "petId", "value": 999999, "message": "Pet not found"},
    },
    "uploadFile": {
        "400": {"param": "file", "value": None, "message": "No file uploaded"},
        "404": {"param": "petId", "value": 999999, "message": "Pet not found"},
    },
    
    # Store operations
    "getInventory": {
        "400": {"trigger": "server_error", "message": "No description"},
        "404": {"trigger": "server_error", "message": "No description"},
        "500": {"trigger": "server_error", "message": "Internal server error"},
    },
    "placeOrder": {
        "400": {"body_field": "quantity", "value": -1, "message": "Invalid input"},
        "422": {"body_field": "shipDate", "value": None, "message": "Validation exception"},
    },
    "getOrderById": {
        "400": {"param": "orderId", "value": "invalid_id", "message": "Invalid ID supplied"},
        "404": {"param": "orderId", "value": 999999, "message": "Order not found"},
    },
    "deleteOrder": {
        "400": {"param": "orderId", "value": "invalid_id", "message": "Invalid ID supplied"},
        "404": {"param": "orderId", "value": 999999, "message": "Order not found"},
    },
    
    # User operations
    "createUser": {
        "400": {"body_field": "username", "value": "", "message": "Invalid username"},
        "404": {"trigger": "server_error", "message": "No description"},
        "500": {"trigger": "server_error", "message": "Internal server error"},
    },
    "createUsersWithListInput": {
        "400": {"body_field": "users", "value": [], "message": "Empty list"},
        "404": {"trigger": "server_error", "message": "No description"},
        "500": {"trigger": "server_error", "message": "Internal server error"},
    },
    "loginUser": {
        "400": {"param": "username", "value": "invalid_user", "message": "Invalid username/password supplied"},
    },
    "logoutUser": {
        "400": {"trigger": "server_error", "message": "No description"},
        "404": {"trigger": "server_error", "message": "No description"},
        "500": {"trigger": "server_error", "message": "Internal server error"},
    },
    "getUserByName": {
        "400": {"param": "username", "value": "invalid_user", "message": "Invalid username supplied"},
        "404": {"param": "username", "value": "nonexistent_user_xyz", "message": "User not found"},
    },
    "updateUser": {
        "400": {"body_field": "email", "value": "invalid_email", "message": "bad request"},
        "404": {"param": "username", "value": "nonexistent_user_xyz", "message": "user not found"},
    },
    "deleteUser": {
        "400": {"param": "username", "value": "invalid_user", "message": "Invalid username supplied"},
        "404": {"param": "username", "value": "nonexistent_user_xyz", "message": "User not found"},
    },
}


# ============================================================================
# CHAOS DECISION LOGIC
# ============================================================================

def should_inject_chaos(failure_rate: float, seed: int) -> bool:
    """Deterministically decide whether to inject chaos."""
    if failure_rate <= 0.0:
        return False
    if failure_rate >= 1.0:
        return True
    
    rng = random.Random(seed)
    return rng.random() < failure_rate


def select_error_code(tool_name: str, seed: int) -> str:
    """
    Select which error code to inject for this tool.
    
    Prioritizes common errors:
    - 40% chance: 400 (Bad Request)
    - 30% chance: 404 (Not Found)
    - 20% chance: 422 (Validation)
    - 10% chance: 500 (Server Error)
    """
    if tool_name not in CHAOS_STRATEGIES:
        return "400"  # Default
    
    available_errors = list(CHAOS_STRATEGIES[tool_name].keys())
    if not available_errors:
        return "400"
    
    # Weight common errors higher
    weights = []
    for code in available_errors:
        if code == "400":
            weights.append(40)
        elif code == "404":
            weights.append(30)
        elif code == "422":
            weights.append(20)
        elif code == "500":
            weights.append(10)
        else:
            weights.append(10)
    
    # Deterministic selection
    rng = random.Random(seed)
    return rng.choices(available_errors, weights=weights, k=1)[0]


# ============================================================================
# CHAOS INJECTION
# ============================================================================

def inject_chaos_into_params(
    tool_name: str,
    params: Dict[str, Any],
    error_code: str
) -> Dict[str, Any]:
    """
    Modify params to trigger the specified error code.
    
    Returns modified params dict.
    """
    if tool_name not in CHAOS_STRATEGIES:
        return params
    
    strategy = CHAOS_STRATEGIES[tool_name].get(error_code)
    if not strategy:
        return params
    
    modified_params = params.copy()
    
    # Inject chaos based on strategy
    if "param" in strategy:
        modified_params[strategy["param"]] = strategy["value"]
    
    elif "body_field" in strategy:
        # For POST/PUT with body
        if strategy["value"] is not None:
            modified_params[strategy["body_field"]] = strategy["value"]
        else:
            # Remove field to trigger validation error
            modified_params.pop(strategy["body_field"], None)
    
    elif "trigger" in strategy and strategy["trigger"] == "server_error":
        # For server errors, we'll simulate them in the response
        modified_params["_force_error_code"] = error_code
    
    return modified_params


# ============================================================================
# API CALL
# ============================================================================

async def call_chaos_proxy(
    tool_name: str,
    params: Dict[str, Any],
    failure_rate: float = 0.0,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Call Petstore API with optional chaos injection.
    
    Args:
        tool_name: API operation name (e.g., "findPetsByStatus")
        params: Parameters for the API call
        failure_rate: Probability of chaos (0.0 to 1.0)
        seed: Random seed for determinism
    
    Returns:
        dict: {status_code, body, error, tool_name, chaos_injected}
    """
    # Get endpoint info
    if tool_name not in TOOL_TO_ENDPOINT:
        return {
            "status_code": 404,
            "body": {"code": 404, "type": "error", "message": f"Unknown tool: {tool_name}"},
            "error": "Unknown tool",
            "tool_name": tool_name,
            "chaos_injected": False
        }
    
    endpoint, http_method = TOOL_TO_ENDPOINT[tool_name]
    
    # Decide: inject chaos?
    inject_chaos = should_inject_chaos(failure_rate, seed)
    error_code = None
    
    if inject_chaos:
        error_code = select_error_code(tool_name, seed)
        params = inject_chaos_into_params(tool_name, params, error_code)
        print(f"   🎲 Injecting chaos: {tool_name} → HTTP {error_code}")
    
    # Build URL
    url = PETSTORE_BASE_URL + endpoint
    for param_name, param_value in params.items():
        if f"{{{param_name}}}" in url:
            url = url.replace(f"{{{param_name}}}", str(param_value))
    
    # Handle forced error codes (for server errors)
    if "_force_error_code" in params:
        forced_code = params.pop("_force_error_code")
        return {
            "status_code": int(forced_code),
            "body": {
                "code": int(forced_code),
                "type": "error",
                "message": CHAOS_STRATEGIES[tool_name][forced_code]["message"]
            },
            "error": f"HTTP {forced_code}",
            "tool_name": tool_name,
            "chaos_injected": True
        }
    
    # Make API request
    try:
        if http_method == "GET":
            response = requests.get(url, params=params, timeout=5)
        elif http_method == "POST":
            response = requests.post(url, json=params, timeout=5)
        elif http_method == "PUT":
            response = requests.put(url, json=params, timeout=5)
        elif http_method == "DELETE":
            response = requests.delete(url, timeout=5)
        else:
            raise ValueError(f"Unsupported HTTP method: {http_method}")
        
        # Parse response
        try:
            body = response.json()
        except:
            body = {"raw": response.text} if response.text else {}
        
        return {
            "status_code": response.status_code,
            "body": body,
            "error": None if response.ok else f"HTTP {response.status_code}",
            "tool_name": tool_name,
            "chaos_injected": inject_chaos
        }
    
    except requests.Timeout:
        return {
            "status_code": 504,
            "body": {"code": 504, "type": "error", "message": "Gateway Timeout"},
            "error": "Request timeout",
            "tool_name": tool_name,
            "chaos_injected": inject_chaos
        }
    
    except requests.ConnectionError:
        return {
            "status_code": 503,
            "body": {"code": 503, "type": "error", "message": "Service Unavailable"},
            "error": "Connection failed",
            "tool_name": tool_name,
            "chaos_injected": inject_chaos
        }
    
    except Exception as e:
        return {
            "status_code": 500,
            "body": {"code": 500, "type": "error", "message": str(e)},
            "error": f"Internal error: {str(e)}",
            "tool_name": tool_name,
            "chaos_injected": inject_chaos
        }


# ============================================================================
# TESTING
# ============================================================================

async def test_chaos_proxy():
    """Test ChaosProxy with different scenarios."""
    print("\n" + "="*70)
    print("CHAOS PROXY TEST - Petstore API (Direct HTTP)")
    print("="*70)
    
    # Test 1: No chaos (should succeed)
    print("\n[TEST 1] No chaos - findPetsByStatus")
    result1 = await call_chaos_proxy(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=0.0,
        seed=42
    )
    print(f"   Status: {result1['status_code']}, Chaos: {result1['chaos_injected']}")
    if result1.get('body'):
        body_str = str(result1['body'])[:100]
        print(f"   Body: {body_str}...")
    
    # Test 2: With chaos (400 error)
    print("\n[TEST 2] With chaos - findPetsByStatus (expect 400)")
    result2 = await call_chaos_proxy(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=1.0,
        seed=42
    )
    print(f"   Status: {result2['status_code']}, Chaos: {result2['chaos_injected']}")
    print(f"   Error: {result2.get('error')}")
    print(f"   Body: {result2['body']}")
    
    # Test 3: 404 error
    print("\n[TEST 3] With chaos - getPetById (expect 404)")
    result3 = await call_chaos_proxy(
        tool_name="getPetById",
        params={"petId": 1},
        failure_rate=1.0,
        seed=100
    )
    print(f"   Status: {result3['status_code']}, Chaos: {result3['chaos_injected']}")
    print(f"   Error: {result3.get('error')}")
    print(f"   Body: {result3['body']}")
    
    # Test 4: 422 validation error
    print("\n[TEST 4] With chaos - addPet (expect 422)")
    result4 = await call_chaos_proxy(
        tool_name="addPet",
        params={"name": "doggie", "photoUrls": ["url1"]},
        failure_rate=1.0,
        seed=200
    )
    print(f"   Status: {result4['status_code']}, Chaos: {result4['chaos_injected']}")
    print(f"   Error: {result4.get('error')}")
    print(f"   Body: {result4['body']}")
    
    # Test 5: 500 server error
    print("\n[TEST 5] With chaos - getInventory (expect 500)")
    result5 = await call_chaos_proxy(
        tool_name="getInventory",
        params={},
        failure_rate=1.0,
        seed=300
    )
    print(f"   Status: {result5['status_code']}, Chaos: {result5['chaos_injected']}")
    print(f"   Error: {result5.get('error')}")
    print(f"   Body: {result5['body']}")
    
    print("\n" + "="*70)
    print("✅ CHAOS PROXY TEST COMPLETED")
    print("="*70)


if __name__ == "__main__":
    print("🧪 Testing ChaosProxy (Direct HTTP)...")
    asyncio.run(test_chaos_proxy())
