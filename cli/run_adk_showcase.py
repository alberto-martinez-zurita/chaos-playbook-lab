"""
CLI Script: ADK Capabilities Showcase
=====================================
Muestra la tabla de evaluación nativa del Google ADK Framework.
Usa un enfoque basado en archivos JSON temporales para máxima compatibilidad.
"""

import sys
import asyncio
import logging
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

# Asegurar que encontramos el código fuente
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

# Importaciones del Framework ADK
from google.adk.evaluation.agent_evaluator import AgentEvaluator
import chaos_engine.agents.order_agent # Importar para asegurar registro

# Configurar logging para que se vea la tabla
logging.basicConfig(level=logging.INFO)

async def main():
    print("\n" + "="*80)
    print("🚀 GOOGLE ADK FRAMEWORK SHOWCASE: PETSTORE EVALUATION")
    print("="*80)
    print("Objetivo: Demostrar la evaluación automática de herramientas (Tool Trajectory).\n")

    # 1. CREAR DATASET TEMPORAL (Formato Legacy Compatible)
    # Usamos este formato porque sabemos que tu versión de ADK lo procesa correctamente
    showcase_data = [
        {
            "query": "Quiero comprar una mascota. Revisa el inventario, busca disponibles, compra la 12345 y marca como vendida.",
            "expected_tool_use": [
                {"tool_name": "get_inventory", "tool_input": {}},
                {"tool_name": "find_pets_by_status", "tool_input": {"status": "available"}},
                {"tool_name": "place_order", "tool_input": {"pet_id": 12345, "quantity": 1}},
                {"tool_name": "update_pet_status", "tool_input": {"pet_id": 12345, "status": "sold", "name": "Fluffy"}}
            ],
            "reference": "{\"selected_pet_id\": 12345, \"completed\": true, \"error\": null}"
        }
    ]

    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp:
        json.dump(showcase_data, tmp)
        tmp_path = tmp.name

    try:
        # 2. MOCK DE RED (Happy Path)
        async def mock_network_response(*args, **kwargs):
            call_str = str(args) + str(kwargs)
            if "inventory" in call_str: return {"status": "success", "code": 200, "data": {"available": 50}}
            if "findByStatus" in call_str: return {"status": "success", "code": 200, "data": [{"id": 12345, "name": "Fluffy", "status": "available"}]}
            if "order" in call_str: return {"status": "success", "code": 200, "data": {"id": "ORD-123", "status": "placed"}}
            if "pet" in call_str: return {"status": "success", "code": 200, "data": {"id": 12345, "status": "sold", "name": "Fluffy"}}
            return {"status": "success", "code": 200, "data": {}}

        # 3. EJECUCIÓN (Interceptando dependencias)
        print(f"⚙️  Dataset temporal creado en: {tmp_path}")
        print("⚙️  Configurando entorno (Mock Mode, 1 Run)...")

        # Parchear Red y NUM_RUNS
        with patch('chaos_engine.agents.order_agent.chaos_proxy.send_request', side_effect=mock_network_response):
            
            # Interceptar llamada interna para forzar 1 sola ejecución
            original_eval = AgentEvaluator.evaluate_eval_set
            
            async def patched_eval(*args, **kwargs):
                kwargs['num_runs'] = 1
                kwargs['print_detailed_results'] = True # Forzar impresión de tabla
                return await original_eval(*args, **kwargs)

            # Aplicar parche al método de clase
            with patch.object(AgentEvaluator, 'evaluate_eval_set', side_effect=patched_eval):
                
                print("\n🏁 Iniciando Agente...\n")
                
                result = await AgentEvaluator.evaluate(
                    agent_module="chaos_engine.agents.order_agent",
                    eval_dataset_file_path_or_dir=tmp_path
                )
                
                print("\n✅ SHOWCASE FINALIZADO.")
                
                if result and hasattr(result, 'summary'):
                    # Si el resultado no se imprimió solo, lo mostramos aquí
                    print("\n--- RESUMEN FINAL ---")
                    # En algunas versiones result es una lista, en otras un objeto
                    if not isinstance(result, list):
                        print(result.summary)

    finally:
        # Limpieza
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    asyncio.run(main())