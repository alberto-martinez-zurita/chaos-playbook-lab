# 📚 Manual de Usuario - Chaos Playbook Engine

**Versión:** 2.0  
**Fecha:** 24 Noviembre 2025  
**Autor:** Albert - Stanford Google Cloud AI Capstone

---

## 📋 Índice

1. [Introducción](#introducción)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Instalación y Configuración](#instalación-y-configuración)
4. [Comandos Principales](#comandos-principales)
5. [Módulos y Componentes](#módulos-y-componentes)
6. [Experimentos Paramétricos](#experimentos-paramétricos)
7. [Generación de Reportes](#generación-de-reportes)
8. [Tests y Cobertura](#tests-y-cobertura)
9. [Configuración Avanzada](#configuración-avanzada)
10. [Troubleshooting](#troubleshooting)
11. [Apéndices](#apéndices)

---

## 🎯 Introducción

### ¿Qué es Chaos Playbook Engine?

Chaos Playbook Engine es un framework de experimentación para agentes AI que permite:

- **Inyección controlada de fallos** en APIs simuladas
- **Comparación A/B** entre agentes (Baseline vs Playbook)
- **Experimentos paramétricos** con múltiples failure rates
- **Generación automática de métricas** y dashboards interactivos
- **Validación de resilencia** de agentes AI

### Propósito

Validar que los agentes AI equipados con "playbooks" (estrategias de recuperación de errores) son más efectivos que agentes baseline sin estrategias.

### Caso de Uso Principal

Sistema de pedidos de comida con:
- **APIs simuladas**: Inventory, Payment, Shipping
- **Fallos controlados**: Timeouts, errores HTTP, inconsistencias
- **Métricas**: Success rate, latency, data consistency

---

## 🏗️ Arquitectura del Sistema

### Estructura de Directorios

```
chaos-playbook-engine/
├── src/                          # Código fuente principal
│   ├── core/                     # Componentes core
│   │   ├── ab_test_runner.py    # Runner de experimentos A/B
│   │   ├── aggregate_metrics.py # Agregación de métricas
│   │   ├── chaos_config.py      # Configuración de chaos
│   │   ├── chaos_injection_helper.py
│   │   └── retry_wrapper.py     # Wrapper de reintentos
│   ├── agents/                   # Agentes AI
│   │   ├── order_orchestrator.py
│   │   └── experiment_judge.py
│   ├── storage/                  # Persistencia
│   │   └── playbook_storage.py
│   └── apis/                     # APIs simuladas
│       └── simulated_apis.py
├── tests/                        # Tests unitarios
│   ├── test_ab_runner.py
│   ├── test_aggregate_metrics.py
│   ├── test_chaos_injection.py
│   └── conftest.py
├── scripts/                      # Scripts de utilidad
│   ├── run_parametric_experiments.py
│   └── generate_dashboard.py
├── playbooks/                    # Playbooks JSON
│   └── chaos_playbook.json
├── results/                      # Resultados de experimentos
│   └── parametric_experiments/
│       └── run_YYYYMMDD_HHMMSS/
│           ├── raw_results.csv
│           ├── aggregated_metrics.json
│           └── dashboard.html
├── pyproject.toml                # Dependencias Poetry
└── README.md
```

### Flujo de Datos

```
1. Configuración
   ├─> chaos_config.py (failure rates, scenarios)
   └─> chaos_playbook.json (estrategias de recuperación)

2. Ejecución
   ├─> run_parametric_experiments.py
   │   ├─> ab_test_runner.py (ejecuta experimentos)
   │   │   ├─> order_orchestrator.py (baseline/playbook)
   │   │   │   ├─> simulated_apis.py (APIs con fallos)
   │   │   │   └─> chaos_injection_helper.py (inyecta fallos)
   │   │   └─> experiment_judge.py (valida resultados)
   │   └─> aggregate_metrics.py (agrega métricas)

3. Análisis
   ├─> generate_dashboard.py (genera HTML)
   └─> Dashboard interactivo (Plotly)
```

---

## ⚙️ Instalación y Configuración

### Requisitos Previos

- **Python**: 3.10+
- **Poetry**: 1.5+
- **Google Cloud SDK** (opcional, para Vertex AI)

### Instalación Inicial

```powershell
# 1. Clonar repositorio
git clone https://github.com/your-repo/chaos-playbook-engine.git
cd chaos-playbook-engine

# 2. Instalar dependencias con Poetry
poetry install

# 3. Activar entorno virtual
poetry shell

# 4. Verificar instalación
poetry run python --version
poetry run pytest --version
```

### Configuración de Variables de Entorno

Crear archivo `.env`:

```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Vertex AI
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_MODEL=gemini-1.5-flash-002

# Chaos Configuration
DEFAULT_FAILURE_RATE=0.3
CHAOS_SEED=42
```

### Verificación de Instalación

```powershell
# Ejecutar tests rápidos
poetry run pytest tests/ -v --tb=short

# Verificar módulos importables
poetry run python -c "from src.core.ab_test_runner import ABTestRunner; print('OK')"
```

---

## 🚀 Comandos Principales

### 1. Ejecutar Experimento Paramétrico

**Comando básico:**

```powershell
poetry run python scripts/run_parametric_experiments.py
```

**Con opciones:**

```powershell
# Especificar failure rates personalizados
poetry run python scripts/run_parametric_experiments.py \
    --failure-rates 0.1 0.3 0.5

# Número de experimentos por configuración
poetry run python scripts/run_parametric_experiments.py \
    --n-experiments 5

# Timeout personalizado
poetry run python scripts/run_parametric_experiments.py \
    --timeout 120

# Verbose mode
poetry run python scripts/run_parametric_experiments.py --verbose
```

**Opciones disponibles:**

| Opción | Descripción | Valor por defecto |
|--------|-------------|-------------------|
| `--failure-rates` | Lista de failure rates (0.0-1.0) | `[0.1, 0.3, 0.5]` |
| `--n-experiments` | Número de experimentos por rate | `2` |
| `--timeout` | Timeout en segundos | `60` |
| `--output-dir` | Directorio de salida | `results/parametric_experiments` |
| `--verbose` | Modo detallado | `False` |
| `--seed` | Semilla para reproducibilidad | `42` |

**Salida esperada:**

```
🎯 Starting Parametric Experiment Suite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Configuration:
   • Failure Rates: [0.1, 0.3, 0.5]
   • Experiments per rate: 2
   • Total experiments: 12 (6 baseline + 6 playbook)

🔬 Running Experiments...
   ✓ Failure Rate 10.0% - Baseline [1/2] ... DONE (2.34s)
   ✓ Failure Rate 10.0% - Baseline [2/2] ... DONE (2.41s)
   ...

📈 Aggregating Metrics...
   ✓ Aggregated metrics saved to: results/.../aggregated_metrics.json

✅ Experiment Suite Complete!
   📁 Results: results/parametric_experiments/run_20251124_003045/
```

### 2. Generar Dashboard HTML

**Comando básico:**

```powershell
poetry run python scripts/generate_dashboard.py --latest
```

**Con opciones:**

```powershell
# Dashboard de un run específico
poetry run python scripts/generate_dashboard.py \
    --run-dir run_20251124_003045

# Output personalizado
poetry run python scripts/generate_dashboard.py \
    --latest \
    --output custom_dashboard.html

# Abrir automáticamente en navegador (Windows)
poetry run python scripts/generate_dashboard.py --latest
start results/parametric_experiments/run_XXXXX/dashboard.html
```

**Opciones disponibles:**

| Opción | Descripción |
|--------|-------------|
| `--latest` | Usar el run más reciente |
| `--run-dir` | Especificar run directory name |
| `--output` | Path personalizado para dashboard |

**Salida esperada:**

```
🎨 Generating dashboard from: results/.../aggregated_metrics.json
   Output: results/.../dashboard.html

✅ Dashboard generated successfully!
   Location: results/parametric_experiments/run_20251124_003045/dashboard.html
   Size: 124.5 KB

🌐 Open in browser: file:///path/to/dashboard.html
```

### 3. Ejecutar Tests

**Tests completos:**

```powershell
poetry run pytest tests/ -v
```

**Tests específicos:**

```powershell
# Test de un módulo específico
poetry run pytest tests/test_ab_runner.py -v

# Test de una función específica
poetry run pytest tests/test_ab_runner.py::test_run_experiment -v

# Tests con markers
poetry run pytest -m "not slow" -v
```

**Con cobertura de código:**

```powershell
# Cobertura básica
poetry run pytest tests/ --cov=src --cov-report=term-missing

# Cobertura con HTML
poetry run pytest tests/ --cov=src --cov-report=html
start htmlcov/index.html

# Con umbral mínimo (falla si < 80%)
poetry run pytest tests/ --cov=src --cov-fail-under=80
```

**Opciones de pytest:**

| Opción | Descripción |
|--------|-------------|
| `-v` | Verbose mode |
| `-s` | Mostrar prints |
| `-x` | Parar en primer fallo |
| `--tb=short` | Traceback corto |
| `--lf` | Ejecutar solo últimos fallidos |
| `--ff` | Ejecutar fallidos primero |
| `-k "pattern"` | Filtrar por nombre de test |

### 4. Linting y Formateo

```powershell
# Black (formateador)
poetry run black src/ tests/

# Flake8 (linter)
poetry run flake8 src/ tests/

# MyPy (type checker)
poetry run mypy src/

# Todo en uno
poetry run black src/ tests/ && \
poetry run flake8 src/ tests/ && \
poetry run mypy src/
```

### 5. Gestión de Dependencias

```powershell
# Ver dependencias instaladas
poetry show

# Agregar dependencia
poetry add requests

# Agregar dependencia de desarrollo
poetry add --group dev pytest-mock

# Actualizar dependencias
poetry update

# Exportar requirements.txt
poetry export -f requirements.txt --output requirements.txt
```

---

## 🧩 Módulos y Componentes

### 1. ABTestRunner (`ab_test_runner.py`)

**Propósito:** Ejecutor principal de experimentos A/B.

**Uso:**

```python
from src.core.ab_test_runner import ABTestRunner

runner = ABTestRunner(
    failure_rate=0.3,
    n_experiments=5,
    timeout=60,
    use_playbook=True
)

results = runner.run_experiment()
```

**Métodos principales:**

| Método | Descripción | Parámetros |
|--------|-------------|------------|
| `run_experiment()` | Ejecuta experimento completo | `None` |
| `_run_single_experiment()` | Ejecuta 1 experimento | `experiment_id: int` |
| `_compare_agents()` | Compara baseline vs playbook | `None` |

**Salida:**

```python
{
    "failure_rate": 0.3,
    "n_experiments": 5,
    "baseline": {
        "success_rate": 0.6,
        "avg_duration": 2.34,
        "inconsistencies": 0.2
    },
    "playbook": {
        "success_rate": 0.8,
        "avg_duration": 2.51,
        "inconsistencies": 0.1
    },
    "raw_results": [...]
}
```

### 2. AggregateMetrics (`aggregate_metrics.py`)

**Propósito:** Agregación y análisis estadístico de resultados.

**Uso:**

```python
from src.core.aggregate_metrics import aggregate_results

aggregated = aggregate_results(
    csv_path="results/run_XXX/raw_results.csv",
    output_path="results/run_XXX/aggregated_metrics.json"
)
```

**Métricas calculadas:**

- **Success Rate**: mean, std, min, max
- **Duration**: mean, std, min, max
- **Inconsistencies**: mean, std, min, max
- **Agent Performance**: baseline vs playbook deltas

### 3. ChaosConfig (`chaos_config.py`)

**Propósito:** Configuración de escenarios de chaos.

**Estructura:**

```python
CHAOS_SCENARIOS = {
    "inventory_timeout": {
        "api": "inventory",
        "failure_type": "timeout",
        "probability": 0.3,
        "delay_ms": 5000
    },
    "payment_http_error": {
        "api": "payment",
        "failure_type": "http_error",
        "probability": 0.2,
        "status_code": 503
    },
    # ... más escenarios
}
```

**Tipos de fallos soportados:**

| Tipo | Descripción | Parámetros |
|------|-------------|------------|
| `timeout` | API no responde | `delay_ms` |
| `http_error` | Error HTTP | `status_code` |
| `data_corruption` | Datos corruptos | `corruption_type` |
| `partial_failure` | Respuesta parcial | `missing_fields` |

### 4. SimulatedAPIs (`simulated_apis.py`)

**Propósito:** APIs simuladas con inyección de fallos.

**APIs disponibles:**

```python
# Inventory API
response = inventory_api.check_inventory(order_id)
# Returns: {"items": [...], "available": true/false}

# Payment API
response = payment_api.process_payment(order_id, amount)
# Returns: {"transaction_id": "...", "status": "success"}

# Shipping API
response = shipping_api.schedule_shipping(order_id, address)
# Returns: {"tracking_id": "...", "eta": "2025-11-25"}
```

**Configuración de fallos:**

```python
from src.apis.simulated_apis import InventoryAPI

api = InventoryAPI(failure_rate=0.3, chaos_enabled=True)
response = api.check_inventory(order_id="ORD123")
```

### 5. OrderOrchestrator (`order_orchestrator.py`)

**Propósito:** Agente orquestador de pedidos.

**Modos:**

- **Baseline**: Sin estrategias de recuperación
- **Playbook**: Con estrategias de recuperación

**Uso:**

```python
from src.agents.order_orchestrator import OrderOrchestrator

# Baseline agent
orchestrator = OrderOrchestrator(use_playbook=False)
result = orchestrator.process_order(order_data)

# Playbook agent
orchestrator = OrderOrchestrator(use_playbook=True)
result = orchestrator.process_order(order_data)
```

**Estrategias de playbook:**

- **Retry con exponential backoff**
- **Circuit breaker**
- **Fallback a valores por defecto**
- **Compensating transactions**

---

## 🔬 Experimentos Paramétricos

### Configuración de Experimentos

**Archivo:** `scripts/run_parametric_experiments.py`

**Parámetros configurables:**

```python
FAILURE_RATES = [0.1, 0.2, 0.3, 0.4, 0.5]  # Lista de failure rates
N_EXPERIMENTS = 5                           # Experimentos por rate
TIMEOUT = 60                                # Timeout en segundos
OUTPUT_DIR = "results/parametric_experiments"
```

### Flujo de Ejecución

```
1. Setup
   ├─> Crear directorio de resultados
   ├─> Inicializar logger
   └─> Cargar configuración

2. Para cada failure rate:
   ├─> Ejecutar N experimentos baseline
   ├─> Ejecutar N experimentos playbook
   └─> Guardar raw_results.csv

3. Agregación
   ├─> Calcular estadísticas por failure rate
   ├─> Calcular deltas (playbook - baseline)
   └─> Guardar aggregated_metrics.json

4. Dashboard
   └─> Generar dashboard.html interactivo
```

### Métricas Capturadas

**Por experimento individual:**

```json
{
  "experiment_id": 1,
  "agent_type": "baseline",
  "failure_rate": 0.3,
  "success": true,
  "duration_s": 2.34,
  "inconsistencies": 0,
  "api_calls": {
    "inventory": {"success": true, "duration": 0.5},
    "payment": {"success": true, "duration": 0.8},
    "shipping": {"success": false, "duration": 1.0}
  }
}
```

**Métricas agregadas:**

```json
{
  "0.3": {
    "failure_rate": 0.3,
    "n_experiments": 5,
    "baseline": {
      "success_rate": {"mean": 0.6, "std": 0.1, "min": 0.4, "max": 0.8},
      "duration_s": {"mean": 2.34, "std": 0.5, "min": 1.8, "max": 3.0},
      "inconsistencies": {"mean": 0.2, "std": 0.1, "min": 0.0, "max": 0.4}
    },
    "playbook": {
      "success_rate": {"mean": 0.8, "std": 0.05, "min": 0.7, "max": 0.9},
      "duration_s": {"mean": 2.51, "std": 0.4, "min": 2.0, "max": 3.1},
      "inconsistencies": {"mean": 0.1, "std": 0.05, "min": 0.0, "max": 0.2}
    }
  }
}
```

---

## 📊 Generación de Reportes

### Dashboard Interactivo

**Archivo:** `scripts/generate_dashboard.py`

**Componentes del dashboard:**

1. **Executive Summary Cards**
   - Max Effectiveness Gain
   - Avg Latency (Baseline)
   - Avg Latency (Playbook)
   - Avg Consistency (Playbook)

2. **Gráficos Interactivos (Plotly)**
   - Agent Effectiveness (bar chart)
   - Latency Overhead % (line chart)
   - Data Consistency % (line chart)
   - Combined Performance Trends (multi-line)

3. **Summary Results Tables**
   - Success Rate Summary (por failure rate)
   - Latency Overhead Rate Summary
   - Consistency Rate Summary

4. **Detailed Results Tables**
   - Métricas detalladas por failure rate
   - Comparación baseline vs playbook
   - Deltas con color coding (verde/rojo/negro)

**Características interactivas:**

- **Zoom/Pan** en gráficos
- **Hover tooltips** con valores exactos
- **Exportar gráficos** (PNG, SVG)
- **Responsive design** (mobile-friendly)

### Comando de Generación

```powershell
# Dashboard del run más reciente
poetry run python scripts/generate_dashboard.py --latest

# Dashboard de run específico
poetry run python scripts/generate_dashboard.py \
    --run-dir run_20251124_003045

# Con output personalizado
poetry run python scripts/generate_dashboard.py \
    --latest \
    --output /path/to/custom_dashboard.html
```

### Estructura HTML Generada

```html
<!DOCTYPE html>
<html>
<head>
    <title>Chaos Playbook Engine - Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>/* Estilos responsivos */</style>
</head>
<body>
    <div class="container">
        <div class="header">...</div>
        <div class="metadata">...</div>
        <div class="content">
            <!-- Executive Summary -->
            <div class="summary-cards">...</div>
            
            <!-- Charts -->
            <div class="charts-grid">...</div>
            
            <!-- Tables -->
            <div class="summary-tables">...</div>
            <div class="detailed-tables">...</div>
        </div>
        <div class="footer">...</div>
    </div>
    <script>/* Plotly charts */</script>
</body>
</html>
```

---

## 🧪 Tests y Cobertura

### Estructura de Tests

```
tests/
├── conftest.py                    # Fixtures compartidos
├── test_ab_runner.py              # Tests de ABTestRunner
├── test_aggregate_metrics.py      # Tests de agregación
├── test_chaos_injection.py        # Tests de chaos injection
├── test_order_orchestrator.py     # Tests de orchestrator
├── test_experiment_judge.py       # Tests de judge
├── test_simulated_apis.py         # Tests de APIs
└── test_playbook_storage.py       # Tests de storage
```

### Fixtures Principales (conftest.py)

```python
@pytest.fixture
def sample_order_data():
    """Datos de orden de prueba"""
    return {
        "order_id": "TEST-001",
        "items": [...],
        "total": 150.00
    }

@pytest.fixture
def mock_apis(monkeypatch):
    """Mock de APIs simuladas"""
    # ... mocking setup

@pytest.fixture
def temp_results_dir(tmp_path):
    """Directorio temporal para resultados"""
    return tmp_path / "test_results"
```

### Ejecutar Tests

**Tests completos:**

```powershell
poetry run pytest tests/ -v
```

**Tests con cobertura:**

```powershell
# Terminal output
poetry run pytest tests/ --cov=src --cov-report=term-missing

# HTML report
poetry run pytest tests/ --cov=src --cov-report=html
start htmlcov/index.html

# XML (para CI/CD)
poetry run pytest tests/ --cov=src --cov-report=xml
```

**Tests específicos:**

```powershell
# Un archivo
poetry run pytest tests/test_ab_runner.py -v

# Una clase
poetry run pytest tests/test_ab_runner.py::TestABTestRunner -v

# Una función
poetry run pytest tests/test_ab_runner.py::test_run_experiment -v

# Por marker
poetry run pytest -m "not slow" -v
```

### Cobertura de Código

**Objetivo:** >80% coverage

**Configuración en pyproject.toml:**

```toml
[tool.pytest.ini_options]
addopts = "--cov=src --cov-report=term-missing --cov-report=html"
testpaths = ["tests"]

[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/__pycache__/*"
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if __name__ == .__main__.:"
]
```

**Ver reporte de cobertura:**

```powershell
# Ejecutar tests con cobertura
poetry run pytest tests/ --cov=src --cov-report=html

# Abrir reporte HTML
start htmlcov/index.html
```

**Métricas de cobertura:**

| Módulo | Statements | Missing | Coverage |
|--------|-----------|---------|----------|
| ab_test_runner.py | 145 | 12 | 91% |
| aggregate_metrics.py | 98 | 5 | 94% |
| chaos_config.py | 42 | 2 | 95% |
| order_orchestrator.py | 203 | 18 | 91% |
| **TOTAL** | **488** | **37** | **92%** |

---

## ⚙️ Configuración Avanzada

### Chaos Playbook JSON

**Archivo:** `playbooks/chaos_playbook.json`

**Estructura:**

```json
{
  "version": "2.0",
  "scenarios": {
    "inventory_timeout": {
      "strategy": "retry_with_backoff",
      "max_retries": 3,
      "backoff_factor": 2,
      "timeout_ms": 5000
    },
    "payment_failure": {
      "strategy": "circuit_breaker",
      "failure_threshold": 3,
      "success_threshold": 2,
      "timeout_ms": 10000
    },
    "shipping_unavailable": {
      "strategy": "fallback",
      "fallback_provider": "backup_shipping",
      "cache_ttl": 300
    }
  },
  "global_config": {
    "max_total_retries": 10,
    "default_timeout_ms": 30000,
    "enable_circuit_breaker": true
  }
}
```

**Estrategias disponibles:**

| Estrategia | Descripción | Parámetros |
|------------|-------------|------------|
| `retry_with_backoff` | Retry con exponential backoff | `max_retries`, `backoff_factor` |
| `circuit_breaker` | Circuit breaker pattern | `failure_threshold`, `success_threshold` |
| `fallback` | Fallback a servicio alternativo | `fallback_provider`, `cache_ttl` |
| `compensating_transaction` | Rollback de transacciones | `compensation_steps` |

### Variables de Entorno

**Archivo:** `.env`

```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Vertex AI
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_MODEL=gemini-1.5-flash-002
VERTEX_AI_TEMPERATURE=0.7
VERTEX_AI_MAX_TOKENS=8192

# Chaos Configuration
DEFAULT_FAILURE_RATE=0.3
CHAOS_SEED=42
ENABLE_CHAOS=true

# Experiment Configuration
MAX_CONCURRENT_EXPERIMENTS=5
EXPERIMENT_TIMEOUT=60
RETRY_MAX_ATTEMPTS=3

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/chaos_engine.log

# Results
RESULTS_BASE_DIR=results
KEEP_RAW_RESULTS=true
```

### Configuración de Logging

**Archivo:** `src/utils/logger.py`

```python
import logging
from pathlib import Path

def setup_logger(
    name: str = "chaos_engine",
    level: int = logging.INFO,
    log_file: str = "logs/chaos_engine.log"
):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    
    # File handler
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
```

---

## 🔧 Troubleshooting

### Problemas Comunes

#### 1. Error: "Module not found"

**Problema:**
```
ModuleNotFoundError: No module named 'src.core'
```

**Solución:**
```powershell
# Asegurar que estás en el directorio correcto
cd chaos-playbook-engine

# Reinstalar dependencias
poetry install

# Activar entorno
poetry shell

# Verificar PYTHONPATH
poetry run python -c "import sys; print(sys.path)"
```

#### 2. Error: "Timeout en experimentos"

**Problema:**
```
TimeoutError: Experiment exceeded 60s timeout
```

**Solución:**
```powershell
# Aumentar timeout
poetry run python scripts/run_parametric_experiments.py \
    --timeout 120

# O modificar configuración por defecto en chaos_config.py
DEFAULT_TIMEOUT = 120
```

#### 3. Error: "Dashboard no genera"

**Problema:**
```
FileNotFoundError: aggregated_metrics.json not found
```

**Solución:**
```powershell
# Verificar que experimento completó correctamente
ls results/parametric_experiments/run_XXXXX/

# Regenerar métricas agregadas
poetry run python -c "
from src.core.aggregate_metrics import aggregate_results
aggregate_results('results/run_XXX/raw_results.csv')
"

# Luego generar dashboard
poetry run python scripts/generate_dashboard.py --latest
```

#### 4. Error: "Tests fallan con fixtures"

**Problema:**
```
fixture 'sample_order_data' not found
```

**Solución:**
```powershell
# Verificar que conftest.py está en tests/
ls tests/conftest.py

# Ejecutar tests con verbose para ver fixtures
poetry run pytest tests/ -v --fixtures
```

#### 5. Error: "Cobertura baja"

**Problema:**
```
FAILED (coverage < 80%)
```

**Solución:**
```powershell
# Ver qué líneas faltan cubrir
poetry run pytest tests/ --cov=src --cov-report=term-missing

# Abrir reporte HTML detallado
poetry run pytest tests/ --cov=src --cov-report=html
start htmlcov/index.html

# Agregar tests para módulos con baja cobertura
```

### Debug Mode

**Habilitar logs detallados:**

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**En comandos:**

```powershell
# Verbose mode
poetry run python scripts/run_parametric_experiments.py --verbose

# Debug pytest
poetry run pytest tests/ -vv -s --log-cli-level=DEBUG
```

### Limpiar Caché y Rebuilds

```powershell
# Limpiar caché de Python
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Limpiar entorno virtual de Poetry
poetry env remove python
poetry install

# Limpiar resultados temporales
rm -rf results/parametric_experiments/run_*
```

---

## 📚 Apéndices

### A. Glosario de Términos

| Término | Definición |
|---------|------------|
| **Chaos Engineering** | Práctica de inyectar fallos controlados para validar resilencia |
| **Playbook** | Conjunto de estrategias de recuperación de errores |
| **Baseline Agent** | Agente sin estrategias de recuperación |
| **Playbook Agent** | Agente con estrategias de recuperación |
| **Failure Rate** | Probabilidad de fallo en APIs (0.0-1.0) |
| **Success Rate** | Porcentaje de experimentos exitosos |
| **Latency Overhead** | Incremento en latencia por estrategias de recuperación |
| **Data Consistency** | Porcentaje de datos consistentes entre APIs |
| **A/B Testing** | Comparación entre dos variantes de agentes |

### B. Referencias Externas

- **Chaos Engineering**: [principlesofchaos.org](https://principlesofchaos.org/)
- **Poetry Documentation**: [python-poetry.org/docs](https://python-poetry.org/docs/)
- **Pytest Documentation**: [docs.pytest.org](https://docs.pytest.org/)
- **Plotly Documentation**: [plotly.com/python](https://plotly.com/python/)
- **Google Vertex AI**: [cloud.google.com/vertex-ai/docs](https://cloud.google.com/vertex-ai/docs)

### C. Comandos Rápidos de Referencia

**Setup y Tests:**

```powershell
# Instalación inicial
poetry install && poetry shell

# Tests rápidos
poetry run pytest tests/ -v

# Tests con cobertura
poetry run pytest tests/ --cov=src --cov-report=html
```

**Experimentos:**

```powershell
# Experimento completo
poetry run python scripts/run_parametric_experiments.py

# Dashboard
poetry run python scripts/generate_dashboard.py --latest
```

**Linting:**

```powershell
# Formatear código
poetry run black src/ tests/

# Linter
poetry run flake8 src/ tests/
```

**Logs y Debug:**

```powershell
# Ver logs
tail -f logs/chaos_engine.log

# Debug mode
export LOG_LEVEL=DEBUG
poetry run python scripts/run_parametric_experiments.py --verbose
```

### D. Estructura de Salida de Resultados

```
results/
└── parametric_experiments/
    └── run_20251124_003045/
        ├── raw_results.csv              # Resultados raw de experimentos
        ├── aggregated_metrics.json      # Métricas agregadas
        ├── dashboard.html               # Dashboard interactivo
        └── experiment.log               # Logs de ejecución
```

**Formato de raw_results.csv:**

```csv
experiment_id,agent_type,failure_rate,success,duration_s,inconsistencies,timestamp
1,baseline,0.3,true,2.34,0,2025-11-24T00:30:45
2,baseline,0.3,false,3.12,1,2025-11-24T00:30:48
3,playbook,0.3,true,2.51,0,2025-11-24T00:30:51
...
```

**Formato de aggregated_metrics.json:**

```json
{
  "0.1": {
    "failure_rate": 0.1,
    "n_experiments": 5,
    "baseline": {
      "success_rate": {"mean": 0.8, "std": 0.05, "min": 0.7, "max": 0.9},
      "duration_s": {"mean": 2.1, "std": 0.3, "min": 1.8, "max": 2.5},
      "inconsistencies": {"mean": 0.1, "std": 0.05, "min": 0.0, "max": 0.2}
    },
    "playbook": {
      "success_rate": {"mean": 0.9, "std": 0.03, "min": 0.85, "max": 0.95},
      "duration_s": {"mean": 2.3, "std": 0.2, "min": 2.0, "max": 2.6},
      "inconsistencies": {"mean": 0.05, "std": 0.03, "min": 0.0, "max": 0.1}
    }
  },
  "0.3": {...},
  "0.5": {...}
}
```

---

## 📞 Soporte y Contacto

**Desarrollador:** Albert  
**Email:** [your-email@example.com]  
**GitHub:** [github.com/your-username/chaos-playbook-engine]  
**Documentación:** [docs.chaos-playbook-engine.com]

---

## 📝 Licencia

Este proyecto es parte del **Stanford Google Cloud AI Capstone** y está disponible bajo licencia MIT.

---

**Última actualización:** 24 Noviembre 2025  
**Versión del manual:** 2.0