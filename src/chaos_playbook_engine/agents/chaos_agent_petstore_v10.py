"""
chaos_agent_petstore.py - ChaosAgent for Petstore API with Chaos Injection

FIXED: 
- Remove problematic endpoint #7 (uploadFile)
- Remove OAuth2 security requirements
- FORCE base server URL (replace partial URLs)

PURPOSE:
    Transparent chaos injection proxy for Petstore API.
    - Wraps OpenAPI endpoints with controlled failure injection
    - Uses Google ADK with Gemini 2.0 Flash Lite
    - Deterministic chaos based on failure_rate and seed

USAGE:
    # Test ChaosAgent
    poetry run python src/chaos_playbook_engine/agents/chaos_agent_petstore.py
    
    # Use in code
    from chaos_playbook_engine.agents.chaos_agent_petstore import call_chaos_proxy
    
    result = await call_chaos_proxy(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=0.2,
        seed=42
    )

AUTHOR: chaos-playbook-engine Phase 3 (ADK API v8 FINAL FIX)
DATE: 2025-11-26
"""

import os
import random
import asyncio
import json
import requests
from typing import Dict, Any, Optional
from pathlib import Path

# ADK imports
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset


# ============================================================================
# CONFIGURATION
# ============================================================================

PETSTORE_OPENAPI_URL = "https://petstore3.swagger.io/api/v3/openapi.json"
PETSTORE_OPENAPI_LOCAL = "apis/petstore3_openapi.json"
PETSTORE_BASE_URL = "https://petstore3.swagger.io"  # Base URL for API calls
GEMINI_MODEL = "gemini-2.0-flash-lite"

# Endpoints to exclude (known to cause issues with Gemini API)
EXCLUDED_ENDPOINTS = [
    ("/pet/{petId}/uploadImage", "post"),  # Endpoint #7 - causes INVALID_ARGUMENT error
]


# ============================================================================
# SWAGGER/OPENAPI LOADER & CLEANER
# ============================================================================

def _force_server_url(spec_dict: Dict[str, Any], base_url: str) -> Dict[str, Any]:
    """
    Force base server URL in OpenAPI spec.
    
    OpenAPI specs may have partial or incorrect server URLs.
    ALWAYS replace with the correct full base URL.
    
    Args:
        spec_dict: Parsed OpenAPI spec
        base_url: Full base URL for the API (e.g., https://petstore3.swagger.io)
    
    Returns:
        dict: Spec with corrected server URL
    """
    cleaned = spec_dict.copy()
    
    # ALWAYS set servers to the correct base URL
    # (Don't check if it exists - just replace it)
    cleaned['servers'] = [
        {
            "url": base_url,
            "description": "Chaos-injected Petstore API"
        }
    ]
    print(f"   🌐 Set server URL: {base_url}")
    
    return cleaned


def _remove_auth_requirements(spec_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove OAuth2 security requirements from OpenAPI spec.
    
    Petstore API security is for production. For testing/chaos purposes,
    we remove security requirements to avoid auth errors.
    
    Args:
        spec_dict: Parsed OpenAPI spec
    
    Returns:
        dict: Spec without security requirements
    """
    cleaned = spec_dict.copy()
    
    # Remove global security
    if 'security' in cleaned:
        del cleaned['security']
        print(f"   🔓 Removed global security requirements")
    
    # Remove security from each endpoint
    if 'paths' in cleaned:
        for path, methods in cleaned['paths'].items():
            for method, operation in methods.items():
                if method not in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                    continue
                
                if 'security' in operation:
                    del operation['security']
    
    return cleaned


def _remove_problematic_endpoints(spec_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove endpoints that cause Gemini API errors.
    
    OpenAPIToolset may generate invalid function declarations for certain
    endpoints. Remove them before passing to ADK.
    
    Args:
        spec_dict: Parsed OpenAPI spec
    
    Returns:
        dict: Cleaned OpenAPI spec
    """
    cleaned = spec_dict.copy()
    
    removed_count = 0
    
    if 'paths' in cleaned:
        for path, method_lowercase in EXCLUDED_ENDPOINTS:
            if path in cleaned['paths']:
                if method_lowercase in cleaned['paths'][path]:
                    operation_id = cleaned['paths'][path][method_lowercase].get('operationId', 'UNKNOWN')
                    del cleaned['paths'][path][method_lowercase]
                    removed_count += 1
                    print(f"   ⚠️  Excluded problematic endpoint: {method_lowercase.upper()} {path} ({operation_id})")
                
                # Remove path if no methods left
                if not cleaned['paths'][path]:
                    del cleaned['paths'][path]
    
    if removed_count > 0:
        print(f"   📋 Excluded {removed_count} problematic endpoint(s)")
    
    return cleaned


def _download_and_cache_swagger(url: str, local_path: str, base_url: str) -> str:
    """
    Download Swagger JSON from URL, clean it, and cache locally.
    
    Args:
        url: Swagger JSON URL
        local_path: Local file path to cache
        base_url: Full base URL for API server
    
    Returns:
        str: Cleaned Swagger JSON as string
    """
    local_file = Path(local_path)
    
    # Always re-download to ensure we get cleaned version
    print(f"   📥 Downloading Swagger from: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        swagger_json = response.text
        
        # Parse and clean the spec
        spec_dict = json.loads(swagger_json)
        
        print(f"   🧹 Cleaning OpenAPI spec...")
        cleaned_spec = _remove_problematic_endpoints(spec_dict)
        cleaned_spec = _remove_auth_requirements(cleaned_spec)
        cleaned_spec = _force_server_url(cleaned_spec, base_url)
        
        cleaned_json = json.dumps(cleaned_spec, indent=2)
        
        # Cache cleaned version
        local_file.parent.mkdir(parents=True, exist_ok=True)
        with open(local_file, 'w', encoding='utf-8') as f:
            f.write(cleaned_json)
        
        print(f"   ✅ Cached cleaned Swagger to: {local_path}")
        print(f"   ✅ OpenAPI spec ready (base URL: {base_url})")
        
        return cleaned_json
    
    except requests.RequestException as e:
        print(f"   ❌ Failed to download Swagger: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"   ❌ Failed to parse Swagger JSON: {e}")
        raise


# ============================================================================
# CHAOS AGENT SINGLETON
# ============================================================================

_chaos_agent_instance: Optional[LlmAgent] = None
_chaos_runner_instance: Optional[InMemoryRunner] = None


def _initialize_chaos_agent() -> tuple[LlmAgent, InMemoryRunner]:
    """
    Initialize ChaosAgent (singleton pattern).
    
    Returns:
        tuple: (LlmAgent, InMemoryRunner)
    """
    global _chaos_agent_instance, _chaos_runner_instance
    
    if _chaos_agent_instance is not None and _chaos_runner_instance is not None:
        return _chaos_agent_instance, _chaos_runner_instance
    
    # Validate API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable not set. "
            "Set it with: export GEMINI_API_KEY='your_key_here'"
        )
    
    print(f"🔧 Initializing ChaosAgent...")
    print(f"   Model: {GEMINI_MODEL}")
    print(f"   Swagger: {PETSTORE_OPENAPI_URL}")
    print(f"   Base URL: {PETSTORE_BASE_URL}")
    
    # Download/load OpenAPI spec (cleaned)
    try:
        openapi_json_str = _download_and_cache_swagger(
            PETSTORE_OPENAPI_URL,
            PETSTORE_OPENAPI_LOCAL,
            PETSTORE_BASE_URL
        )
    except Exception as e:
        print(f"   ❌ Failed to load OpenAPI: {e}")
        raise
    
    # Create OpenAPIToolset from cleaned OpenAPI 3.0 JSON STRING
    try:
        petstore_toolset = OpenAPIToolset(
            spec_str=openapi_json_str,  # ← STRING, OpenAPI 3.0 JSON (cleaned)
            spec_str_type='json'         # ← 'json'
        )
        print(f"   ✅ OpenAPIToolset loaded ({len(openapi_json_str)} bytes)")
    except Exception as e:
        print(f"   ❌ Failed to create OpenAPIToolset: {e}")
        raise
    
    # Create ChaosAgent with ADK
    _chaos_agent_instance = LlmAgent(
        name="ChaosAgent",
        model=GEMINI_MODEL,
        tools=[petstore_toolset],
        instruction="""You are a transparent chaos injection proxy for Petstore API.

**YOUR ROLE**:
You receive tool calls with chaos parameters and either:
1. Pass params unchanged (no chaos) → Call Petstore API → Return success
2. Modify params to trigger errors (chaos) → Call Petstore API → Return error

**CHAOS INJECTION RULES**:
- Use the `inject_chaos` flag to decide: if True, inject chaos; if False, pass through
- When injecting chaos, modify parameters to trigger realistic errors

**CRITICAL RULES**:
1. NO natural language responses - return raw API results
2. NO interpreting business logic - you're a dumb proxy
3. NO deciding which tool to call - caller specifies tool name
4. ALWAYS respect inject_chaos flag (deterministic behavior)
5. Return structured response with status_code and body

**OUTPUT FORMAT**:
Always respond with tool results. Let the API response speak for itself.
"""
    )
    
    # Create InMemoryRunner with ADK
    _chaos_runner_instance = InMemoryRunner(
        agent=_chaos_agent_instance
    )
    
    print(f"   ✅ ChaosAgent initialized (ADK)")
    print(f"   ✅ InMemoryRunner created")
    
    return _chaos_agent_instance, _chaos_runner_instance


# ============================================================================
# CHAOS DECISION LOGIC
# ============================================================================

def should_inject_chaos(failure_rate: float, seed: int) -> bool:
    """
    Deterministically decide whether to inject chaos.
    
    Args:
        failure_rate: Probability of failure (0.0 to 1.0)
        seed: Random seed for reproducibility
    
    Returns:
        bool: True if chaos should be injected, False otherwise
    """
    if failure_rate <= 0.0:
        return False
    if failure_rate >= 1.0:
        return True
    
    rng = random.Random(seed)
    return rng.random() < failure_rate


# ============================================================================
# CHAOS PROXY API
# ============================================================================

async def call_chaos_proxy(
    tool_name: str,
    params: Dict[str, Any],
    failure_rate: float = 0.0,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Call Petstore API through ChaosAgent with optional chaos injection.
    
    Args:
        tool_name: Petstore API operation (e.g., "findPetsByStatus")
        params: Parameters for the API call
        failure_rate: Probability of injecting chaos (0.0 to 1.0)
        seed: Random seed for reproducibility
    
    Returns:
        dict: API response
    """
    # Initialize agent (singleton)
    agent, runner = _initialize_chaos_agent()
    
    # Decide: inject chaos or not?
    inject_chaos = should_inject_chaos(failure_rate, seed)
    
    # Build user query for ChaosAgent
    query = f"""Call tool '{tool_name}' with these parameters: {json.dumps(params)}

inject_chaos: {inject_chaos}

If inject_chaos is True, modify parameters to trigger an error.
If inject_chaos is False, use parameters exactly as provided.

Call the tool now."""
    
    print(f"   🔧 ChaosProxy: {tool_name}(chaos={inject_chaos})")
    
    # Execute agent with ADK InMemoryRunner
    try:
        # run_debug() es el método correcto para InMemoryRunner
        response = await runner.run_debug(query)
        
        # Parse response for tool calls and results
        tool_called = None
        tool_result = None
        
        # Check if response contains tool call information
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                for part in candidate.content.parts:
                    # Check for function call
                    if hasattr(part, 'function_call') and part.function_call:
                        tool_called = part.function_call.name
                        print(f"      → Agent called: {tool_called}")
                    
                    # Check for function response
                    if hasattr(part, 'function_response') and part.function_response:
                        tool_result = part.function_response.response
        
        # Parse result from tool response
        if tool_result:
            print(f"tool_result: {tool_result}")
            result = _parse_tool_result(tool_result, tool_name, inject_chaos)
            return result
        else:
            # If no explicit tool result, parse the text response
            return {
                "status_code": 200,
                "body": {"response": str(response)},
                "error": None,
                "tool_name": tool_name,
                "chaos_injected": inject_chaos
            }
    
    except Exception as e:
        print(f"      ❌ Error in ChaosProxy: {e}")
        return {
            "status_code": 500,
            "body": {},
            "error": f"ChaosProxy error: {str(e)}",
            "tool_name": tool_name,
            "chaos_injected": inject_chaos
        }


def _parse_tool_result(tool_result: Any, tool_name: str, chaos_injected: bool) -> Dict[str, Any]:
    """Parse tool result from OpenAPI tool call."""
    try:
        if hasattr(tool_result, 'status_code'):
            status_code = tool_result.status_code
            body = tool_result.json() if hasattr(tool_result, 'json') else {}
            error = None if status_code < 400 else f"HTTP {status_code}"
        
        elif hasattr(tool_result, 'response'):
            response_data = tool_result.response
            if isinstance(response_data, dict):
                status_code = response_data.get('status_code', 200)
                body = response_data.get('body', response_data)
                error = response_data.get('error')
            else:
                status_code = 200
                body = response_data
                error = None
        
        elif isinstance(tool_result, dict):
            status_code = tool_result.get('status_code', 200)
            body = tool_result.get('body', tool_result)
            error = tool_result.get('error')
        
        else:
            status_code = 200
            body = {"result": str(tool_result)}
            error = None
        
        return {
            "status_code": status_code,
            "body": body,
            "error": error,
            "tool_name": tool_name,
            "chaos_injected": chaos_injected
        }
    
    except Exception as e:
        return {
            "status_code": 500,
            "body": {},
            "error": f"Failed to parse tool result: {str(e)}",
            "tool_name": tool_name,
            "chaos_injected": chaos_injected
        }


# ============================================================================
# TESTING
# ============================================================================

async def test_chaos_proxy():
    """Test ChaosAgent with and without chaos injection."""
    print("\n" + "="*70)
    print("CHAOS AGENT TEST - Petstore API Proxy")
    print("="*70)
    
    # Test 1: No chaos (should succeed)
    print("\n[TEST 1] Call without chaos (failure_rate=0.0)")
    result1 = await call_chaos_proxy(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=0.0,
        seed=42
    )
    print(f"   Result: status={result1['status_code']}, chaos={result1['chaos_injected']}")
    if result1.get('body'):
        body_str = str(result1['body'])
        preview = body_str[:150] + "..." if len(body_str) > 150 else body_str
        print(f"   Body preview: {preview}")
    
    # Test 2: With chaos (should fail)
    print("\n[TEST 2] Call with chaos (failure_rate=1.0)")
    result2 = await call_chaos_proxy(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=1.0,
        seed=42
    )
    print(f"   Result: status={result2['status_code']}, chaos={result2['chaos_injected']}")
    if result2.get('error'):
        print(f"   Error: {result2['error']}")
    
    # Test 3: Probabilistic chaos
    print("\n[TEST 3] Probabilistic chaos (failure_rate=0.5, seed=100)")
    result3 = await call_chaos_proxy(
        tool_name="getPetById",
        params={"petId": 1},
        failure_rate=0.5,
        seed=100
    )
    print(f"   Result: status={result3['status_code']}, chaos={result3['chaos_injected']}")
    
    print("\n" + "="*70)
    print("✅ CHAOS AGENT TEST COMPLETED")
    print("="*70)


if __name__ == "__main__":
    """Run tests when executed directly."""
    print("🧪 Testing ChaosAgent with Petstore API...")
    asyncio.run(test_chaos_proxy())
