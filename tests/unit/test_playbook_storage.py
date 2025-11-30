import pytest
import json
import asyncio
from pathlib import Path
from chaos_engine.core.playbook_storage import PlaybookStorage

# --- FIXTURES ---

@pytest.fixture
def temp_storage_file(tmp_path):
    """Crea una ruta temporal para el archivo JSON del playbook."""
    d = tmp_path / "data"
    d.mkdir()
    return str(d / "test_chaos_playbook.json")

# --- TESTS ---

@pytest.mark.asyncio
async def test_storage_initialization_creates_file(temp_storage_file):
    """Verifica que si el archivo no existe, se crea una estructura vacía."""
    storage = PlaybookStorage(file_path=temp_storage_file)
    
    # El archivo debe haber sido creado en el init
    assert Path(temp_storage_file).exists()
    
    with open(temp_storage_file, 'r') as f:
        data = json.load(f)
        assert data == {"procedures": []}

@pytest.mark.asyncio
async def test_save_procedure(temp_storage_file):
    """Verifica que se puede guardar un procedimiento correctamente."""
    storage = PlaybookStorage(file_path=temp_storage_file)
    
    # Pasamos metadata explícita para probar que se guarda
    metadata = {"agent": "TestAgent", "version": "1.0"}
    
    proc_id = await storage.save_procedure(
        failure_type="timeout",
        api="inventory",
        recovery_strategy="Wait 5s",
        success_rate=0.95,
        metadata=metadata
    )
    
    assert proc_id.startswith("PROC-")
    
    # Verificar persistencia en disco
    with open(temp_storage_file, 'r') as f:
        data = json.load(f)
        saved_proc = data["procedures"][0]
        assert saved_proc["id"] == proc_id
        assert saved_proc["recovery_strategy"] == "Wait 5s"
        # Verificar que la metadata que pasamos se guardó
        assert saved_proc["metadata"]["agent"] == "TestAgent"

@pytest.mark.asyncio
async def test_get_best_procedure_logic(temp_storage_file):
    """
    CRÍTICO: Verifica que el sistema elige la MEJOR estrategia, 
    no solo la primera que encuentra.
    """
    storage = PlaybookStorage(file_path=temp_storage_file)
    
    # Usamos 'service_unavailable' que es un tipo válido, en lugar de '503'
    valid_failure = "service_unavailable"
    
    # Estrategia 1: Mediocre (50% éxito)
    await storage.save_procedure(
        failure_type=valid_failure,
        api="inventory",
        recovery_strategy="Retry immediately",
        success_rate=0.5
    )
    
    # Estrategia 2: Excelente (100% éxito)
    await storage.save_procedure(
        failure_type=valid_failure,
        api="inventory",
        recovery_strategy="Wait 2s and retry",
        success_rate=1.0
    )
    
    # Estrategia 3: Buena (80% éxito)
    await storage.save_procedure(
        failure_type=valid_failure,
        api="inventory",
        recovery_strategy="Wait 1s",
        success_rate=0.8
    )
    
    # Ejecutar búsqueda
    best = await storage.get_best_procedure(failure_type=valid_failure, api="inventory")
    
    # Debe devolver la Estrategia 2 (la de 1.0 success_rate)
    assert best is not None
    assert best["success_rate"] == 1.0
    assert best["recovery_strategy"] == "Wait 2s and retry"

@pytest.mark.asyncio
async def test_validation_errors(temp_storage_file):
    """Verifica que el sistema rechaza datos basura (Defensive Programming)."""
    storage = PlaybookStorage(file_path=temp_storage_file)
    
    # Caso 1: API inválida
    with pytest.raises(ValueError) as excinfo:
        await storage.save_procedure(
            failure_type="timeout",
            api="api_que_no_existe", # Inválido
            recovery_strategy="x"
        )
    assert "Invalid api" in str(excinfo.value)

    # Caso 2: Success Rate imposible
    with pytest.raises(ValueError) as excinfo:
        await storage.save_procedure(
            failure_type="timeout",
            api="inventory",
            recovery_strategy="x",
            success_rate=1.5 # Inválido (>1.0)
        )
    assert "Invalid success_rate" in str(excinfo.value)
    
    # Caso 3: Tipo de fallo inválido (el error que vimos antes)
    with pytest.raises(ValueError) as excinfo:
        await storage.save_procedure(
            failure_type="503", # Inválido
            api="inventory",
            recovery_strategy="x"
        )
    assert "Invalid failure_type" in str(excinfo.value)