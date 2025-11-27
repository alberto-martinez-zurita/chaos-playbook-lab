from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "ChaosPlaybookEngine"
    environment: str = "development"

    # Data paths
    playbook_json_path: Path = Path("./data/playbook.json")
    chaos_scenarios_path: Path = Path("./data/chaos_scenarios.json")

    # Gemini API (Optional for import, required at runtime)
    google_api_key: Optional[str] = None

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Phase 4+ (Optional)
    gcp_project_id: Optional[str] = None
    gcp_region: Optional[str] = "us-central1"
    agent_engine_id: Optional[str] = None
    database_url: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Factory function to create settings
def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
