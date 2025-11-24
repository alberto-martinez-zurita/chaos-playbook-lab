"""Manual test script for basic order workflow - Phase 1.

This script demonstrates the OrderOrchestratorAgent processing a single order
through the complete 4-step workflow in happy-path mode.

Usage:
    poetry run python scripts/basic_order_runner.py
"""

import asyncio

from google.genai import types

from chaos_playbook_engine.services.runner_factory import create_runner

# App name constant (must match runner_factory.APP_NAME)
APP_NAME = "ChaosPlaybookEngine"


async def main() -> None:
    """Run a single order through OrderOrchestratorAgent."""
    print("\n" + "=" * 60)
    print("PHASE 1 - BASIC ORDER TEST")
    print("Happy-Path Workflow Validation")
    print("=" * 60 + "\n")

    # Create runner with basic mode (happy-path)
    print("[1/5] Creating runner...")
    runner = create_runner(mode="basic", env="dev")
    print(f"✅ Runner created with app_name: {runner.app_name}\n")

    # Create session before running
    print("[2/5] Creating session...")
    session_id = "test_session_001"
    user_id = "test_user"
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    print(f"✅ Session created: {session_id}\n")

    # Create order request message
    print("[3/5] Preparing order request...")
    order_request = (
        'Process order for user_id=U123, '
        'items=[{"sku": "WIDGET-A", "qty": 5, "price": 29.99}]'
    )
    message = types.Content(role="user", parts=[types.Part(text=order_request)])
    print(f"📦 Order: {order_request}\n")

    # Execute order workflow
    print("[4/5] Executing order workflow...")
    print("-" * 60)

    events = []
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
        events.append(event)
        
        # Log tool call events
        if hasattr(event, "tool_call"):
            tool_call = event.tool_call
            print(f"🔧 Tool Call: {tool_call.name}")
            
        if hasattr(event, "tool_response"):
            tool_response = event.tool_response
            status = "✅" if "success" in str(tool_response.content) else "❌"
            print(f"{status} Tool Response received\n")
        
        if hasattr(event, "is_final_response") and event.is_final_response():
            print("🏁 Final response received")
            break

    print("-" * 60 + "\n")

    # Retrieve and validate session
    print("[5/5] Validating results...")
    session = await runner.session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )

    print(f"📊 Total events: {len(events)}")
    print(f"🔧 Tool calls logged: {len(session.state.get('tool_calls', []))}\n")

    # Display order result
    order_result = session.state.get("order_result")
    if order_result:
        print("📋 ORDER RESULT:")
        print(f"   Status: {order_result.get('status', 'unknown')}")
        print(f"   Order ID: {order_result.get('order_id', 'N/A')}")
        print(
            f"   Steps Completed: {', '.join(order_result.get('steps_completed', []))}"
        )
        
        if "details" in order_result:
            print("\n   Details:")
            for step, details in order_result["details"].items():
                print(f"     - {step}: {details}")
    else:
        print("⚠️  No order_result found in session.state")

    # Display tool calls trace
    tool_calls = session.state.get("tool_calls", [])
    if tool_calls:
        print(f"\n🔍 TOOL CALLS TRACE ({len(tool_calls)} calls):")
        for i, call in enumerate(tool_calls, 1):
            print(
                f"   {i}. {call.get('api_name', 'unknown')}/"
                f"{call.get('endpoint', 'unknown')} → "
                f"{call.get('response_status', 'unknown')}"
            )

    # Validate success
    print("\n" + "=" * 60)
    try:
        assert order_result is not None, "order_result not found in session.state"
        assert (
            order_result.get("status") == "success"
        ), f"Order failed: {order_result}"
        assert len(order_result.get("steps_completed", [])) == 4, (
            f"Not all steps completed. "
            f"Expected 4, got {len(order_result.get('steps_completed', []))}"
        )
        assert len(tool_calls) >= 4, (
            f"Insufficient tool calls. Expected >=4, got {len(tool_calls)}"
        )

        print("✅ BASIC ORDER TEST PASSED")
        print("=" * 60 + "\n")
        return True

    except AssertionError as e:
        print(f"❌ BASIC ORDER TEST FAILED")
        print(f"   Error: {e}")
        print("=" * 60 + "\n")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
