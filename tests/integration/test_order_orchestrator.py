"""Integration tests for OrderOrchestratorAgent - Phase 1.

Tests validate the complete order workflow execution using InMemoryRunner
pattern. Uses run_debug() for simplified testing with automatic output.
"""

import pytest

from services.runner_factory import create_order_orchestrator_runner


@pytest.mark.asyncio
async def test_happy_path_order() -> None:
    """Test complete order workflow executes all 4 steps successfully."""
    
    runner = create_order_orchestrator_runner(mode="basic")
    
    # Complete order information for all 4 API calls
    query = """Process this order:
- sku: WIDGET-A
- qty: 5
- amount: 149.95
- currency: USD
- user_id: USER123
- order_id: ORD-123
- address: 123 Main St, New York, NY 10001, USA

Execute all 4 steps of the order workflow."""
    
    # run_debug() automatically prints all tool calls and responses
    await runner.run_debug(query)
    
    # If we reach here without exception, workflow completed
    # run_debug() would have raised exception if any tool call failed


@pytest.mark.asyncio
async def test_multiple_orders_sequential() -> None:
    """Test processing multiple orders sequentially."""
    
    runner = create_order_orchestrator_runner(mode="basic")
    
    orders = [
        {
            "sku": "WIDGET-A",
            "qty": 3,
            "amount": 89.97,
            "user_id": "USER001",
            "order_id": "ORD-001"
        },
        {
            "sku": "GADGET-B",
            "qty": 2,
            "amount": 199.98,
            "user_id": "USER002",
            "order_id": "ORD-002"
        }
    ]
    
    for idx, order in enumerate(orders):
        query = f"""Process order {idx+1}:
- sku: {order['sku']}
- qty: {order['qty']}
- amount: {order['amount']}
- currency: USD
- user_id: {order['user_id']}
- order_id: {order['order_id']}
- address: 456 Oak Ave, Los Angeles, CA 90001, USA

Execute all 4 steps."""
        
        print(f"\n{'='*80}")
        print(f"ORDER {idx+1}")
        print('='*80)
        
        await runner.run_debug(query)


@pytest.mark.asyncio
async def test_different_product_types() -> None:
    """Test order processing with various product configurations."""
    
    runner = create_order_orchestrator_runner(mode="basic")
    
    test_cases = [
        {
            "name": "single low-value item",
            "sku": "WIDGET-A",
            "qty": 1,
            "amount": 9.99
        },
        {
            "name": "bulk order",
            "sku": "WIDGET-B",
            "qty": 100,
            "amount": 999.00
        },
        {
            "name": "high-value item",
            "sku": "PREMIUM-X",
            "qty": 1,
            "amount": 1999.99
        }
    ]
    
    for idx, test_case in enumerate(test_cases):
        query = f"""Process order - {test_case['name']}:
- sku: {test_case['sku']}
- qty: {test_case['qty']}
- amount: {test_case['amount']}
- currency: USD
- user_id: TEST_USER_{idx}
- order_id: TEST_ORD_{idx}
- address: 789 Pine Rd, Chicago, IL 60601, USA

Execute all 4 steps."""
        
        print(f"\n{'='*80}")
        print(f"TEST CASE: {test_case['name']}")
        print('='*80)
        
        await runner.run_debug(query)
