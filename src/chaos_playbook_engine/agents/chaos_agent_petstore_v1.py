"""
chaos_agent_petstore.py - Chaos injection proxy using Google ADK + OpenAPI

PURPOSE:
    Transparent proxy that injects controlled failures into Petstore API calls.
    Uses ADK OpenAPIToolset to auto-generate tools from Swagger spec.

ARCHITECTURE:
    OrderAgent → call_chaos_proxy() → ChaosAgent (LlmAgent) → Petstore API
                                           ↑
                                      Injects chaos
                                   (deterministic via seed)

KEY FEATURES:
    - Uses ADK LlmAgent + OpenAPIToolset (no custom API clients)
    - Deterministic chaos injection (same seed = same failures)
    - Returns HTTP status codes + bodies (not natural language)
    - NO interpretation of business logic (transparent proxy)

USAGE:
    from chaos_playbook_engine.agents.chaos_agent_petstore import call_chaos_proxy
    
    result = await call_chaos_proxy(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=0.20,
        seed=42
    )
    
    # Result format:
    {
        "status_code": 200 | 400 | 404 | 500,
        "body": {...},
        "error": "error description" if status >= 400 else None
    }

AUTHOR: chaos-playbook-engine Phase 6
DATE: 2025-11-26
"""

import os
import random
import asyncio
import json
from typing import Dict, Any, Optional
from pathlib import Path

# ADK imports - CRITICAL: Use ADK, not google.genai
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset


# ============================================================================
# CONFIGURATION
# ============================================================================

PETSTORE_SWAGGER_URL = "https://petstore.swagger.io/v2/swagger.json"
GEMINI_MODEL = "gemini-2.0-flash-lite"


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
    
    Raises:
        ValueError: If GEMINI_API_KEY not set
        Exception: If OpenAPIToolset fails to load
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
    print(f"   Swagger: {PETSTORE_SWAGGER_URL}")
    
    # Create OpenAPIToolset from Petstore Swagger
    try:
        petstore_toolset = OpenAPIToolset(
            spec_str=PETSTORE_SWAGGER_URL,
            spec_str_type='url'
        )
        print(f"   ✅ OpenAPIToolset loaded from Petstore Swagger")
    except Exception as e:
        print(f"   ❌ Failed to load OpenAPIToolset: {e}")
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
- When injecting chaos for a tool, modify parameters to trigger realistic errors:
  
  * findPetsByStatus: Use invalid status → 400 Bad Request
  * getPetById: Use non-existent ID (999999) → 404 Not Found
  * addPet: Send incomplete/invalid data → 405 Validation Exception
  * updatePet: Use non-existent ID → 404 Not Found
  * deletePet: Use non-existent ID → 404 Not Found
  * placeOrder: Send invalid order data → 400 Invalid Order
  * getOrderById: Use non-existent order ID → 404 Not Found

**CRITICAL RULES**:
1. NO natural language responses - return raw API results
2. NO interpreting business logic - you're a dumb proxy
3. NO deciding which tool to call - caller specifies tool name
4. ALWAYS respect inject_chaos flag (deterministic behavior)
5. Return structured response with status_code and body

**OUTPUT FORMAT**:
Always respond with tool results. Let the API response speak for itself.
Do NOT add commentary like "Here's what happened" or "The API returned".
Just call the tool and let me extract the results.
"""
    )
    
    # Create InMemoryRunner with ADK
    session_service = InMemorySessionService()
    _chaos_runner_instance = InMemoryRunner(
        agent=_chaos_agent_instance,
        session_service=session_service
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
    
    Note:
        Same seed + same failure_rate = same decision (reproducible)
    """
    if failure_rate <= 0.0:
        return False
    if failure_rate >= 1.0:
        return True
    
    # Use seed for deterministic randomness
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
        params: Parameters for the API call (e.g., {"status": "available"})
        failure_rate: Probability of injecting chaos (0.0 to 1.0)
        seed: Random seed for reproducibility
    
    Returns:
        dict: API response in format:
            {
                "status_code": 200 | 400 | 404 | 500,
                "body": {...},
                "error": "error description" if status >= 400 else None,
                "tool_name": str,
                "chaos_injected": bool
            }
    
    Example:
        >>> result = await call_chaos_proxy(
        ...     tool_name="findPetsByStatus",
        ...     params={"status": "available"},
        ...     failure_rate=0.20,
        ...     seed=42
        ... )
        >>> print(result["status_code"])
        200
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
    
    print(f"   🔧 ChaosProxy: {tool_name}(params={params}, chaos={inject_chaos})")
    
    # Execute agent with ADK runner
    try:
        # Create session
        session_id = f"chaos_session_{seed}"
        
        # Run agent
        final_response = None
        tool_called = None
        tool_result = None
        
        async for event in runner.run_async(
            session_id=session_id,
            new_user_message=query
        ):
            # Track tool calls
            function_calls = event.get_function_calls()
            if function_calls:
                tool_called = function_calls[0].name if function_calls else None
                print(f"      → Agent called: {tool_called}")
            
            # Track tool responses
            function_responses = event.get_function_responses()
            if function_responses:
                tool_result = function_responses[0]
                print(f"      → Tool returned: {tool_result.response if hasattr(tool_result, 'response') else tool_result}")
            
            # Get final response
            if event.is_final_response():
                final_response = event.content
        
        # Parse result from tool response
        if tool_result:
            # Extract status code and body from tool result
            # OpenAPI tools return HTTP responses
            result = _parse_tool_result(tool_result, tool_name, inject_chaos)
            return result
        else:
            # No tool was called - this shouldn't happen
            print(f"      ⚠️  No tool called by agent")
            return {
                "status_code": 500,
                "body": {},
                "error": "Agent failed to call tool",
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
    """
    Parse tool result from OpenAPI tool call.
    
    Args:
        tool_result: Result from OpenAPI tool
        tool_name: Name of the tool that was called
        chaos_injected: Whether chaos was injected
    
    Returns:
        dict: Standardized response format
    """
    # OpenAPI tools return responses with status and body
    # Format varies, so we need to handle multiple cases
    
    try:
        # Case 1: Direct HTTP response object
        if hasattr(tool_result, 'status_code'):
            status_code = tool_result.status_code
            body = tool_result.json() if hasattr(tool_result, 'json') else {}
            error = None if status_code < 400 else f"HTTP {status_code}"
        
        # Case 2: Response in dict format
        elif hasattr(tool_result, 'response'):
            response_data = tool_result.response
            if isinstance(response_data, dict):
                status_code = response_data.get('status_code', 200)
                body = response_data.get('body', response_data)
                error = response_data.get('error')
            else:
                # Assume success if we got data back
                status_code = 200
                body = response_data
                error = None
        
        # Case 3: Raw dict
        elif isinstance(tool_result, dict):
            status_code = tool_result.get('status_code', 200)
            body = tool_result.get('body', tool_result)
            error = tool_result.get('error')
        
        # Case 4: Unknown format - assume success
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
        # Parsing failed - return error
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
    print(f"   Body: {result1['body']}")
    
    # Test 2: With chaos (should fail)
    print("\n[TEST 2] Call with chaos (failure_rate=1.0)")
    result2 = await call_chaos_proxy(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=1.0,
        seed=42
    )
    print(f"   Result: status={result2['status_code']}, chaos={result2['chaos_injected']}")
    print(f"   Error: {result2['error']}")
    
    # Test 3: Probabilistic chaos (seed makes it deterministic)
    print("\n[TEST 3] Probabilistic chaos (failure_rate=0.5, seed=100)")
    result3 = await call_chaos_proxy(
        tool_name="getPetById",
        params={"petId": 1},
        failure_rate=0.5,
        seed=100
    )
    print(f"   Result: status={result3['status_code']}, chaos={result3['chaos_injected']}")
    
    # Test 4: Same seed = same result (reproducibility)
    print("\n[TEST 4] Reproducibility test (same seed)")
    result4a = await call_chaos_proxy(
        tool_name="getPetById",
        params={"petId": 1},
        failure_rate=0.5,
        seed=100
    )
    result4b = await call_chaos_proxy(
        tool_name="getPetById",
        params={"petId": 1},
        failure_rate=0.5,
        seed=100
    )
    
    same_chaos = result4a['chaos_injected'] == result4b['chaos_injected']
    same_status = result4a['status_code'] == result4b['status_code']
    
    print(f"   Call A: chaos={result4a['chaos_injected']}, status={result4a['status_code']}")
    print(f"   Call B: chaos={result4b['chaos_injected']}, status={result4b['status_code']}")
    print(f"   Reproducible: {same_chaos and same_status}")
    
    print("\n" + "="*70)
    print("✅ CHAOS AGENT TEST COMPLETED")
    print("="*70)


if __name__ == "__main__":
    """Run tests when executed directly."""
    print("🧪 Testing ChaosAgent with Petstore API...")
    asyncio.run(test_chaos_proxy())
