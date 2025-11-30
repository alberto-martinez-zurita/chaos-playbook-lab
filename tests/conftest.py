import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# 1. Asegurar que src está en el path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# 2. Mocks Reutilizables para Inyección de Dependencias
@pytest.fixture
def mock_llm_constructor():
    """
    Mock para el constructor de Gemini. 
    Devuelve un objeto que pasa por un modelo válido para ADK.
    """
    # Creamos un mock que simula ser una instancia de BaseLlm
    mock_model_instance = MagicMock()
    # Pydantic a veces chequea atributos específicos o herencia. 
    # Para simplificar, en el test usaremos un string real para el nombre del modelo.
    
    constructor_mock = MagicMock(return_value=mock_model_instance)
    return constructor_mock

@pytest.fixture
def mock_executor():
    """Simula un ChaosProxy/Executor que siempre devuelve éxito."""
    executor = MagicMock()
    executor.send_request = AsyncMock(return_value={
        "status": "success", 
        "code": 200, 
        "data": {"id": 12345}
    })
    return executor

@pytest.fixture
def mock_failing_executor():
    """Simula un Executor que siempre falla."""
    executor = MagicMock()
    executor.send_request = AsyncMock(return_value={
        "status": "error", 
        "code": 503, 
        "message": "Service Unavailable"
    })
    return executor

@pytest.fixture
def mock_llm_constructor():
    """Mock para el constructor de Gemini."""
    return MagicMock()

@pytest.fixture
def temp_playbook_file(tmp_path):
    """Crea un archivo playbook temporal para tests de I/O."""
    d = tmp_path / "assets" / "playbooks"
    d.mkdir(parents=True)
    f = d / "test_playbook.json"
    f.write_text('{"default": {"strategy": "retry"}}', encoding='utf-8')
    return str(f)