"""Runner factory for OrderOrchestratorAgent - Phase 1 Implementation.

Creates InMemoryRunner instances using the pattern from ADK labs.
This simplified approach provides reliable tool execution.

Phase 1 uses InMemoryRunner instead of Runner + App pattern based on
implementation learnings (see order_orchestrator.py docstring).
"""

import os
from dotenv import load_dotenv

from google.adk.runners import InMemoryRunner

from agents.order_orchestrator import create_order_orchestrator_agent


def create_order_orchestrator_runner(mode: str = "basic") -> InMemoryRunner:
    """
    Create InMemoryRunner with OrderOrchestratorAgent.
    
    Uses simplified InMemoryRunner pattern from ADK labs for reliable
    tool execution. Validates GOOGLE_API_KEY is configured before creation.
    
    Args:
        mode: Agent mode ('basic' for Phase 1 happy-path)
        
    Returns:
        Configured InMemoryRunner ready for use
        
    Raises:
        ValueError: If GOOGLE_API_KEY not found in environment
        
    Example:
        >>> runner = create_order_orchestrator_runner(mode="basic")
        >>> await runner.run_debug("Process order: sku=WIDGET-A...")
    """
    # Load and validate environment
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not found in environment. "
            "Ensure .env file exists with GOOGLE_API_KEY=your_key_here"
        )
    
    # Create agent with specified mode
    agent = create_order_orchestrator_agent(mode=mode)
    
    # Return InMemoryRunner (simplified pattern)
    return InMemoryRunner(agent=agent)
