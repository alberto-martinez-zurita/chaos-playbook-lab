import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

class PlaybookManager:
    """
    Manages a JSON playbook file with structure:
    {
      "operation": {
        "status_code": {
          "strategy": "...",
          "reasoning": "...",
          "config": {...}
        }
      }
    }
    """
 
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.data: Dict[str, Any] = self._load()
 
    # -----------------------------
    # Internal Load/Save
    # -----------------------------
    def _load(self) -> Dict[str, Any]:
        """Load playbook from JSON file; return empty dict if missing."""
        if not self.filepath.exists():
            return {}
        with self.filepath.open("r", encoding="utf-8") as f:
            return json.load(f)
 
    def save(self) -> None:
        """Save playbook back to JSON file."""
        with self.filepath.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
 
    # -----------------------------
    # Public API
    # -----------------------------
    def add_operation_or_response(
        self,
        operation: str,
        status_code: str,
        strategy: str,
        reasoning: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add or update a response under an operation.
 
        If the operation does not exist → create it.
        If it exists → add or update the status code entry.
        """
 
        if operation not in self.data:
            self.data[operation] = {}
 
        self.data[operation][status_code] = {
            "strategy": strategy,
            "reasoning": reasoning,
            "config": config or {},
        }
 
    def get_operation(self, operation: str) -> Optional[Dict[str, Any]]:
        """Return the operation block or None if not present."""
        return self.data.get(operation)
 
    def has_operation(self, operation: str) -> bool:
        return operation in self.data
 
    def has_response(self, operation: str, status_code: str) -> bool:
        return (
            operation in self.data
            and status_code in self.data[operation]
        )
 
    def get_all(self) -> Dict[str, Any]:
        """
        Return the entire playbook structure as a dictionary.
        """
        return self.data
 