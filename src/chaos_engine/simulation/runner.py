"""
ABTestRunner - Simplified Orchestrator for Phase 5 Simulation.
"""
import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from chaos_engine.simulation.apis import (
    call_simulated_inventory_api,
    call_simulated_payments_api,
    call_simulated_erp_api,
    call_simulated_shipping_api,
)
from chaos_engine.chaos.config import ChaosConfig

class ABTestRunner:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.workflow_steps = [
            ("inventory", self._step_inventory),
            ("payment", self._step_payment),
            ("erp", self._step_erp),
            ("shipping", self._step_shipping)
        ]

    async def run_experiment(self, agent_type: str, failure_rate: float, seed: int) -> Dict[str, Any]:
        start_time = time.time()
        steps_completed = []
        failed_at = None # ✅ Inicializado a None
        total_retries = 0
        max_retries = 2 if agent_type == "playbook" else 0
        
        base_chaos_config = ChaosConfig(enabled=True, failure_rate=failure_rate, seed=seed)
        status = "success"
        
        for step_name, step_func in self.workflow_steps:
            step_success = False
            for attempt in range(max_retries + 1):
                current_config = base_chaos_config
                if attempt > 0:
                    total_retries += 1
                    current_config = ChaosConfig(enabled=True, failure_rate=failure_rate, seed=seed + (attempt * 1000))
                
                result = await step_func(current_config)
                
                if result["status"] == "success":
                    step_success = True
                    break 
                
            if step_success:
                steps_completed.append(step_name)
            else:
                status = "failure"
                failed_at = step_name # ✅ Se asigna correctamente aquí
                break 
        
        duration_ms = (time.time() - start_time) * 1000
        
        return {
            "status": status,
            "steps_completed": steps_completed,
            "failed_at": failed_at, # ✅ Se devuelve aquí
            "duration_ms": duration_ms,
            "retries": total_retries,
            "outcome": status, 
            "agent_type": agent_type
        }

    async def _step_inventory(self, config): return await call_simulated_inventory_api("check_stock", {"sku": "W", "qty": 1}, config)
    async def _step_payment(self, config): return await call_simulated_payments_api("capture", {"amount": 100}, config)
    async def _step_erp(self, config): return await call_simulated_erp_api("create_order", {"user_id": "U1"}, config)
    async def _step_shipping(self, config): return await call_simulated_shipping_api("create_shipment", {"order_id": "O1", "address": "A1"}, config)