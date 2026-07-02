"""
Unified Protocol definitions for the Chaos Playbook Engine.

Single source of truth for all interface contracts (DRY).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class Executor(Protocol):
    """Contract for HTTP request executors.

    Satisfied by ChaosProxy, CircuitBreakerProxy, HttpExecutor, and test doubles.
    """

    async def send_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]: ...

    def calculate_jittered_backoff(self, seconds: float) -> float: ...


@runtime_checkable
class AgentRunner(Protocol):
    """Contract for agent execution backends.

    Abstracts away the specific LLM framework (Google ADK, LangChain, etc.)
    so domain agents don't import framework types directly (A.29).

    Implementations:
    - ``Adk InMemoryRunner`` adapter (wraps ``google.adk.runners.InMemoryRunner``)
    - Test doubles for unit testing without LLM calls
    """

    async def run(self, prompt: str) -> str:
        """Execute the agent with the given prompt and return the text output."""
        ...


@runtime_checkable
class WorkflowAgent(Protocol):
    """Contract for workflow agents that execute multi-step processes.

    Satisfied by DeterministicAgent and PetstoreAgent.
    """

    async def run(self) -> Dict[str, Any]:
        """Execute the agent's workflow and return an ExperimentResult-compatible dict."""
        ...


@runtime_checkable
class MCPToolExecutor(Protocol):
    """Contract for MCP tool call executors.

    Wraps Model Context Protocol server connections. Satisfied by
    MCPChaosProxy, real MCP clients, and test doubles.
    """

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call an MCP tool and return the result."""
        ...

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools on the MCP server."""
        ...


@runtime_checkable
class A2AExecutor(Protocol):
    """Contract for Agent-to-Agent communication executors.

    Wraps inter-agent messaging. Satisfied by A2AChaosProxy,
    real A2A transports, and test doubles.
    """

    async def send_task(
        self,
        agent_id: str,
        task: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send a task to a remote agent and return the response."""
        ...

    async def query_status(
        self,
        agent_id: str,
        task_id: str,
    ) -> Dict[str, Any]:
        """Query the status of a previously sent task."""
        ...


@runtime_checkable
class LLMClientConstructor(Protocol):
    """Contract for LLM client constructors.

    Abstracts away the specific LLM provider so agents can accept
    any constructor that takes (model, temperature) and returns a client.
    """

    def __call__(self, model: str, temperature: float) -> Any: ...


@runtime_checkable
class ChaosInjector(Protocol):
    """Base contract shared by all chaos proxies (HTTP, MCP, A2A).

    Captures the common DI surface: failure_rate, seed-controlled RNG,
    and mock_mode flag. Concrete proxies extend with protocol-specific methods.
    """

    failure_rate: float
    mock_mode: bool

    def should_inject(self) -> bool:
        """Return True if chaos should be injected on this call."""
        ...
