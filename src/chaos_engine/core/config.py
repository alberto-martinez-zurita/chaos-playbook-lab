# config/config_loader.py

"""
Sistema de carga de configuración desde archivos YAML.
Soporta múltiples entornos (dev/prod) con variables de entorno.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

class ConfigLoader:
    """
    Carga configuración desde archivos YAML basado en el entorno.
    
    Uso:
        config = ConfigLoader.load()
        model = config['agent']['model']
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # Try cwd first (works for any install method), then fall back to __file__
            cwd_config = Path.cwd() / "config"
            if cwd_config.exists():
                self.config_dir = cwd_config
            else:
                # Derive from source layout: src/chaos_engine/core/config.py → ROOT/config
                project_root = Path(__file__).resolve().parents[3]
                self.config_dir = project_root / "config"

        if not self.config_dir.exists():
            import logging
            logging.getLogger(__name__).warning("Config dir not found at %s", self.config_dir)
        
    def load(self, environment: str = None) -> Dict[str, Any]:
        """
        Carga configuración del entorno especificado.
        """
        load_dotenv()
        
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "dev").lower()
        
        # Normalize aliases
        if environment == "development": environment = "dev"
        if environment == "production": environment = "prod"
        
        # ✅ INTENTO 1: Buscar nombre moderno (dev.yaml)
        config_file = self.config_dir / f"{environment}.yaml"
        
        # ✅ INTENTO 2: Buscar nombre legacy (dev_config.yaml) si el moderno falla
        if not config_file.exists():
             config_file_legacy = self.config_dir / f"{environment}_config.yaml"
             if config_file_legacy.exists():
                 config_file = config_file_legacy

        if not config_file.exists():
            raise FileNotFoundError(
                f"❌ No se encontró el archivo de configuración: {config_file}\n"
                f"   Archivos disponibles en {self.config_dir}:\n"
                f"   {list(self.config_dir.glob('*.yaml'))}"
            )
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        config = self._enrich_with_env_vars(config)
        return config
    
    def _enrich_with_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Return a new config dict enriched with environment variables.

        Does NOT mutate the input dict. API keys stay in os.environ only
        (never copied into the returned config to avoid accidental logging).
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY not found in environment.\n"
                "Create a '.env' file in the project root with:\n"
                "GOOGLE_API_KEY=your_api_key_here"
            )

        # Configure ADK environment variables
        os.environ.setdefault("GOOGLE_API_KEY", api_key)
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

        mock_mode_env = os.getenv("MOCK_MODE", "false").lower()

        return {
            **config,
            "use_vertex_ai": False,
            "mock_mode": mock_mode_env in ("true", "1", "yes"),
        }
    

# ============================================================================
# Convenience functions
# ============================================================================

def load_config(environment: str = None) -> Dict[str, Any]:
    """Load configuration for the given environment ('dev'/'prod')."""
    loader = ConfigLoader()
    return loader.load(environment)


def get_model_name(config: Dict[str, Any]) -> str:
    """Extract the model name from configuration."""
    return config['agent']['model']


def get_db_url(config: Dict[str, Any]) -> str:
    """Extract the database URL from configuration."""
    return config['session_service']['db_url']


def get_runner_type(config: Dict[str, Any]) -> str:
    """Extrae el tipo de runner de la configuración."""
    return config.get('runner', {}).get('type', 'InMemoryRunner')
