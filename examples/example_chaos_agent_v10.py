"""
example_chaos_agent_v10.py

Complete example showing how to use ChaosAgent v10 Universal
with OrderAgent in a chaos-playbook experiment.

This demonstrates:
1. Loading configuration from YAML
2. Initializing ChaosAgent
3. Using ChaosAgent from OrderAgent
4. Running experiments with different failure rates
5. Comparing results with/without playbook

Author: chaos-playbook-engine Phase 3 (v10 UNIVERSAL)
Date: 2025-11-26
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List
import sys

# Import ChaosAgent v10
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src" / "chaos_playbook_engine" / "agents"))

from chaos_agent_universal_v10 import ChaosAgent, ChaosAgentConfig


# ============================================================================
# MOCK ORDER AGENT (simplified version for demonstration)
# ============================================================================

class OrderAgent:
    """
    Simplified OrderAgent that uses ChaosAgent as a tool.
    
    In real implementation, this would be an ADK agent with
    full retry logic from playbooks.
    """
    
    def __init__(self, chaos_agent: ChaosAgent, playbook: Dict[str, Any] = None):
        """
        Initialize OrderAgent.
        
        Args:
            chaos_agent: ChaosAgent instance to use as tool
            playbook: Optional playbook with retry strategies
        """
        self.chaos_agent = chaos_agent
        self.playbook = playbook or {}
        self.metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retries": 0,
            "total_latency_ms": 0
        }
    
    async def execute_order(
        self,
        operation: str,
        params: Dict[str, Any],
        failure_rate: float = 0.3,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        Execute an order operation using ChaosAgent.
        
        Applies retry logic from playbook if available.
        """
        import time
        
        self.metrics["total_calls"] += 1
        start_time = time.time()
        
        # Get retry strategy from playbook
        retry_strategy = self._get_retry_strategy(operation, "400")
        max_retries = retry_strategy.get("max_retries", 0)
        backoff_seconds = retry_strategy.get("backoff_seconds", 1)
        
        # Execute with retries
        attempt = 0
        last_error = None
        
        while attempt <= max_retries:
            if attempt > 0:
                self.metrics["retries"] += 1
                await asyncio.sleep(backoff_seconds)
                print(f"   ⚠️  Retry {attempt}/{max_retries} for {operation}")
            
            # Call ChaosAgent
            result = await self.chaos_agent.call(
                tool_name=operation,
                params=params,
                failure_rate=failure_rate,
                seed=seed + attempt
            )
            
            # Check if success
            if result["status_code"] == 200:
                self.metrics["successful_calls"] += 1
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics["total_latency_ms"] += elapsed_ms
                return result
            
            # Failed
            last_error = result
            attempt += 1
        
        # All retries exhausted
        self.metrics["failed_calls"] += 1
        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics["total_latency_ms"] += elapsed_ms
        return last_error
    
    def _get_retry_strategy(self, tool_name: str, error_code: str) -> Dict[str, Any]:
        """Get retry strategy from playbook."""
        if not self.playbook:
            return {"max_retries": 0, "backoff_seconds": 1}
        
        for procedure in self.playbook.get("procedures", []):
            if (procedure.get("tool") == tool_name and 
                procedure.get("error_code") == error_code):
                return {
                    "max_retries": procedure.get("max_retries", 0),
                    "backoff_seconds": procedure.get("backoff_seconds", 1)
                }
        
        return {"max_retries": 0, "backoff_seconds": 1}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Return collected metrics."""
        avg_latency = (
            self.metrics["total_latency_ms"] / self.metrics["total_calls"]
            if self.metrics["total_calls"] > 0
            else 0
        )
        
        success_rate = (
            self.metrics["successful_calls"] / self.metrics["total_calls"] * 100
            if self.metrics["total_calls"] > 0
            else 0
        )
        
        return {
            **self.metrics,
            "avg_latency_ms": avg_latency,
            "success_rate": success_rate
        }


# ============================================================================
# EXPERIMENT RUNNER
# ============================================================================

async def run_experiment(
    config_path: str = "config/chaos_agent.yaml",
    playbook_path: str = None,
    num_iterations: int = 10,
    failure_rate: float = 0.3
):
    """
    Run chaos experiment with ChaosAgent v10.
    """
    print("\n" + "="*70)
    print("CHAOS EXPERIMENT - ChaosAgent v10 Universal")
    print("="*70)
    
    # Load configuration
    print(f"\n📋 Loading configuration from: {config_path}")
    config = ChaosAgentConfig.from_yaml(config_path)
    
    # Load playbook (if provided)
    playbook = None
    if playbook_path:
        print(f"📖 Loading playbook from: {playbook_path}")
        with open(playbook_path, 'r') as f:
            playbook = json.load(f)
    
    # Initialize ChaosAgent
    print(f"\n🚀 Initializing ChaosAgent...")
    chaos_agent = ChaosAgent(config)
    
    # Initialize OrderAgent
    order_agent = OrderAgent(chaos_agent=chaos_agent, playbook=playbook)
    
    # Run iterations
    print(f"\n🧪 Running {num_iterations} iterations (failure_rate={failure_rate})...")
    
    operations = [
        ("findPetsByStatus", {"status": "available"}),
        ("getPetById", {"petId": 123}),
        ("addPet", {"name": "Fluffy", "photoUrls": ["url1"]}),
        ("placeOrder", {"petId": 123, "quantity": 1}),
        ("getOrderById", {"orderId": 456}),
    ]
    
    for i in range(num_iterations):
        op_name, params = operations[i % len(operations)]
        seed = 1000 + i
        
        result = await order_agent.execute_order(
            operation=op_name,
            params=params,
            failure_rate=failure_rate,
            seed=seed
        )
        
        status_emoji = "✅" if result["status_code"] == 200 else "❌"
        print(f"   [{i+1:3d}] {status_emoji} {op_name:20s} → HTTP {result['status_code']}")
    
    # Print metrics
    print("\n" + "="*70)
    print("EXPERIMENT RESULTS")
    print("="*70)
    
    metrics = order_agent.get_metrics()
    print(f"\n📊 Metrics:")
    print(f"   Total calls:       {metrics['total_calls']}")
    print(f"   Successful calls:  {metrics['successful_calls']}")
    print(f"   Failed calls:      {metrics['failed_calls']}")
    print(f"   Retries:           {metrics['retries']}")
    print(f"   Success rate:      {metrics['success_rate']:.1f}%")
    print(f"   Avg latency:       {metrics['avg_latency_ms']:.2f} ms")
    
    print("\n" + "="*70)
    print("✅ EXPERIMENT COMPLETED")
    print("="*70)
    
    return metrics


# ============================================================================
# COMPARISON: WITH vs WITHOUT PLAYBOOK
# ============================================================================

async def run_comparison():
    """Compare experiment results with and without playbook."""
    print("\n" + "="*80)
    print(" COMPARISON: WITH PLAYBOOK vs WITHOUT PLAYBOOK")
    print("="*80)
    
    # Experiment 1: WITHOUT playbook
    print("\n" + "-"*80)
    print(" Experiment 1: WITHOUT PLAYBOOK")
    print("-"*80)
    metrics_without = await run_experiment(
        config_path="config/chaos_agent.yaml",
        playbook_path=None,
        num_iterations=20,
        failure_rate=0.4
    )
    
    # Experiment 2: WITH playbook
    print("\n" + "-"*80)
    print(" Experiment 2: WITH PLAYBOOK")
    print("-"*80)
    metrics_with = await run_experiment(
        config_path="config/chaos_agent.yaml",
        playbook_path="data/playbook_petstore_default.json",
        num_iterations=20,
        failure_rate=0.4
    )
    
    # Compare results
    print("\n" + "="*80)
    print(" COMPARISON RESULTS")
    print("="*80)
    
    print(f"\n📈 Success Rate:")
    print(f"   Without playbook: {metrics_without['success_rate']:6.1f}%")
    print(f"   With playbook:    {metrics_with['success_rate']:6.1f}%")
    improvement = metrics_with['success_rate'] - metrics_without['success_rate']
    print(f"   Improvement:      {improvement:+6.1f}%")
    
    print(f"\n⏱️  Average Latency:")
    print(f"   Without playbook: {metrics_without['avg_latency_ms']:6.2f} ms")
    print(f"   With playbook:    {metrics_with['avg_latency_ms']:6.2f} ms")
    diff = metrics_with['avg_latency_ms'] - metrics_without['avg_latency_ms']
    print(f"   Difference:       {diff:+6.2f} ms")
    
    print(f"\n🔄 Retries:")
    print(f"   Without playbook: {metrics_without['retries']:6d}")
    print(f"   With playbook:    {metrics_with['retries']:6d}")
    
    print("\n" + "="*80)


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main entry point."""
    
    # Example 1: Basic usage
    print("="*80)
    print(" Example 1: Basic ChaosAgent Usage")
    print("="*80)
    
    config = ChaosAgentConfig(
        openapi_spec_url="https://petstore3.swagger.io/api/v3/openapi.json",
        default_failure_rate=0.3
    )
    
    agent = ChaosAgent(config)
    
    # Test call
    result = await agent.call(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=0.3,
        seed=42
    )
    
    print(f"\n✅ Result: HTTP {result['status_code']}")
    print(f"   Chaos injected: {result['chaos_injected']}")
    print(f"   Body: {str(result['body'])[:100]}...")
    
    # Example 2: Full experiment (if config file exists)
    config_path = Path("config/chaos_agent.yaml")
    if config_path.exists():
        print("\n" + "="*80)
        print(" Example 2: Full Experiment with Configuration")
        print("="*80)
        
        await run_experiment(
            config_path=str(config_path),
            playbook_path="data/playbook_petstore_default.json",
            num_iterations=10,
            failure_rate=0.3
        )
    
    # Example 3: Comparison (if files exist)
    playbook_path = Path("data/playbook_petstore_default.json")
    if config_path.exists() and playbook_path.exists():
        await run_comparison()


if __name__ == "__main__":
    asyncio.run(main())
