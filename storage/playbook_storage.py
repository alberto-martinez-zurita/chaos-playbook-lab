"""
Chaos Playbook Storage Module.

Provides JSON-based storage for chaos recovery procedures.
Thread-safe operations with asyncio.Lock.

Location: src/chaos_playbook_engine/data/playbook_storage.py
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class PlaybookStorage:
    """
    JSON-based storage for chaos recovery procedures.
    
    Schema:
    {
        "procedures": [
            {
                "id": "PROC-001",
                "failure_type": "timeout",
                "api": "inventory",
                "recovery_strategy": "retry 3x with exponential backoff",
                "success_rate": 0.85,
                "created_at": "2025-11-22T15:00:00Z",
                "metadata": {...}
            }
        ]
    }
    """
    
    # Valid failure types from chaos framework
    VALID_FAILURE_TYPES = {
        "timeout",
        "service_unavailable",
        "rate_limit_exceeded",
        "invalid_request",
        "network_error"
    }
    
    # Valid APIs
    VALID_APIS = {
        "inventory",
        "payments",
        "erp",
        "shipping"
    }
    
    def __init__(self, file_path: str = "data/chaos_playbook.json"):
        """
        Initialize storage with file path.
        
        Args:
            file_path: Path to JSON storage file
        """
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        """Ensure data directory and file exist."""
        # Create data directory if missing
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create empty playbook if file doesn't exist
        if not self.file_path.exists():
            initial_data = {"procedures": []}
            with open(self.file_path, 'w') as f:
                json.dump(initial_data, f, indent=2)
    
    async def _read_playbook(self) -> Dict[str, Any]:
        """Read playbook from disk (thread-safe)."""
        async with self._lock:
            with open(self.file_path, 'r') as f:
                return json.load(f)
    
    async def _write_playbook(self, data: Dict[str, Any]):
        """Write playbook to disk (thread-safe)."""
        async with self._lock:
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=2)
    
    def _generate_procedure_id(self, existing_procedures: List[Dict]) -> str:
        """
        Generate unique procedure ID.
        
        Args:
            existing_procedures: List of existing procedures
        
        Returns:
            Unique ID like "PROC-001", "PROC-002", etc.
        """
        if not existing_procedures:
            return "PROC-001"
        
        # Extract numbers from existing IDs
        max_num = 0
        for proc in existing_procedures:
            proc_id = proc.get("id", "PROC-000")
            try:
                num = int(proc_id.split("-")[1])
                max_num = max(max_num, num)
            except (IndexError, ValueError):
                continue
        
        # Return next ID
        return f"PROC-{max_num + 1:03d}"
    
    def _validate_inputs(
        self,
        failure_type: str,
        api: str,
        success_rate: float
    ):
        """
        Validate procedure inputs.
        
        Raises:
            ValueError: If inputs are invalid
        """
        if failure_type not in self.VALID_FAILURE_TYPES:
            raise ValueError(
                f"Invalid failure_type: {failure_type}. "
                f"Must be one of {self.VALID_FAILURE_TYPES}"
            )
        
        if api not in self.VALID_APIS:
            raise ValueError(
                f"Invalid api: {api}. "
                f"Must be one of {self.VALID_APIS}"
            )
        
        if not 0.0 <= success_rate <= 1.0:
            raise ValueError(
                f"Invalid success_rate: {success_rate}. "
                f"Must be between 0.0 and 1.0"
            )
    
    async def save_procedure(
        self,
        failure_type: str,
        api: str,
        recovery_strategy: str,
        success_rate: float = 1.0,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Save recovery procedure to Playbook.
        
        Args:
            failure_type: Type of failure (timeout, service_unavailable, etc.)
            api: API that failed (inventory, payments, erp, shipping)
            recovery_strategy: Description of recovery strategy
            success_rate: Success rate of strategy (0.0-1.0)
            metadata: Optional metadata dict
        
        Returns:
            procedure_id: Unique procedure ID (e.g., "PROC-001")
        
        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        self._validate_inputs(failure_type, api, success_rate)
        
        # Read current playbook
        playbook = await self._read_playbook()
        procedures = playbook.get("procedures", [])
        
        # Generate unique ID
        procedure_id = self._generate_procedure_id(procedures)
        
        # Create procedure entry
        procedure = {
            "id": procedure_id,
            "failure_type": failure_type,
            "api": api,
            "recovery_strategy": recovery_strategy,
            "success_rate": success_rate,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "metadata": metadata or {}
        }
        
        # Add to playbook
        procedures.append(procedure)
        playbook["procedures"] = procedures
        
        # Write back to disk
        await self._write_playbook(playbook)
        
        return procedure_id
    
    async def load_procedures(
        self,
        failure_type: Optional[str] = None,
        api: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Load procedures from Playbook with optional filtering.
        
        Args:
            failure_type: Filter by failure type (optional)
            api: Filter by API (optional)
        
        Returns:
            List of matching procedures
        """
        # Read playbook
        playbook = await self._read_playbook()
        procedures = playbook.get("procedures", [])
        
        # Apply filters
        if failure_type:
            procedures = [
                p for p in procedures
                if p.get("failure_type") == failure_type
            ]
        
        if api:
            procedures = [
                p for p in procedures
                if p.get("api") == api
            ]
        
        return procedures
    
    async def get_best_procedure(
        self,
        failure_type: str,
        api: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get best procedure for given failure type and API.
        
        Best = highest success_rate among matching procedures.
        
        Args:
            failure_type: Type of failure
            api: API name
        
        Returns:
            Best matching procedure or None if not found
        """
        # Load matching procedures
        procedures = await self.load_procedures(
            failure_type=failure_type,
            api=api
        )
        
        if not procedures:
            return None
        
        # Sort by success_rate descending, return best
        best = max(procedures, key=lambda p: p.get("success_rate", 0.0))
        return best
