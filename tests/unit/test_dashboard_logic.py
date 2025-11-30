import pytest
from chaos_engine.reporting.dashboard import calculate_summary_stats, extract_chart_data

# Datos simulados de un experimento paramétrico (JSON de entrada)
@pytest.fixture
def mock_metrics_data():
    return {
        "0.1": {
            "failure_rate": 0.1,
            "baseline": {
                "success_rate": {"mean": 0.8},
                "duration_s": {"mean": 2.0},
                "inconsistencies": {"mean": 0.1}
            },
            "playbook": {
                "success_rate": {"mean": 1.0},
                "duration_s": {"mean": 4.0},
                "inconsistencies": {"mean": 0.0}
            }
        },
        "0.2": {
            "failure_rate": 0.2,
            "baseline": {
                "success_rate": {"mean": 0.5}, # Baseline sufre mucho
                "duration_s": {"mean": 2.0},
                "inconsistencies": {"mean": 0.5}
            },
            "playbook": {
                "success_rate": {"mean": 0.95}, # Playbook aguanta
                "duration_s": {"mean": 5.0},
                "inconsistencies": {"mean": 0.05}
            }
        }
    }

def test_calculate_summary_improvement(mock_metrics_data):
    """Verifica que el dashboard calcula correctamente la mejora máxima."""
    stats = calculate_summary_stats(mock_metrics_data)
    
    # En 0.2: Playbook (0.95) - Baseline (0.5) = 0.45 de mejora
    # El dashboard debe reportar +45%
    # 🔥 FIX: Usar pytest.approx para evitar errores de punto flotante (44.9999 != 45.0)
    assert stats['max_improvement'] == pytest.approx(45.0)
    assert stats['improvement_class'] == "positive"

def test_calculate_averages(mock_metrics_data):
    """Verifica los promedios globales mostrados en las tarjetas del dashboard."""
    stats = calculate_summary_stats(mock_metrics_data)
    
    # Duración Baseline: (2.0 + 2.0) / 2 = 2.0s
    assert stats['avg_duration_baseline'] == pytest.approx(2.0)
    
    # Duración Playbook: (4.0 + 5.0) / 2 = 4.5s
    assert stats['avg_duration_playbook'] == pytest.approx(4.5)
    
    # Consistencia Playbook:
    # 0.1 -> inc 0.0 -> cons 1.0
    # 0.2 -> inc 0.05 -> cons 0.95
    # Promedio: (1.0 + 0.95) / 2 = 0.975 -> 97.5%
    assert stats['avg_consistency_playbook'] == pytest.approx(97.5)

def test_extract_chart_data_structure(mock_metrics_data):
    """Verifica que los datos para Plotly se extraen en el orden correcto (ordenado por tasa de fallo)."""
    chart_data = extract_chart_data(mock_metrics_data)
    
    # Debe ordenar las claves numéricamente: 0.1 primero, luego 0.2
    assert chart_data['failure_rates'] == [0.1, 0.2]
    
    # Verificar datos de éxito
    assert chart_data['baseline_success'] == [0.8, 0.5]
    assert chart_data['playbook_success'] == [1.0, 0.95]
    
    # Verificar cálculo de latencia overhead
    # Caso 0.1: (4.0 / 2.0) - 1 = 1.0 -> 100% overhead
    assert chart_data['latency_overhead_pct'][0] == pytest.approx(100.0)