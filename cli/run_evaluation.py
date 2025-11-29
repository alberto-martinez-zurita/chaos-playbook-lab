"""
CLI entry point for Agent Evaluation with Observability.
"""
import sys
import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime

# Setup path (si no instalado)
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from chaos_engine.evaluation.runner import EvaluationRunner
from chaos_engine.core.logging import setup_logger

async def main():
    parser = argparse.ArgumentParser(description="Run Chaos Agent Evaluation Suite")
    parser.add_argument("--suite", type=str, default="assets/evaluations/test_suite.json")
    parser.add_argument("--playbook", type=str, default="assets/playbooks/training.json")
    parser.add_argument("--verbose", action="store_true", help="Show logs in console")
    
    args = parser.parse_args()
    
# 1. PREPARAR OBSERVABILIDAD
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ✅ ESTO ES LO CORRECTO: Definir ruta anidada en 'reports'
    output_dir = project_root / "reports" / "evaluations" / f"eval_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # ✅ FIX: Pasar explícitamente log_dir=str(output_dir)
    # Si falta este argumento, se va a /logs por defecto
    logger = setup_logger("evaluation", verbose=args.verbose, log_dir=str(output_dir))
     
    logger.info("="*60)
    logger.info("🕵️‍♂️ AGENT QA EVALUATION STARTED")
    logger.info(f"📁 Report Artifacts: {output_dir}")
    logger.info("="*60)

    # Validar paths
    suite_path = Path(args.suite)
    if not suite_path.exists(): suite_path = project_root / args.suite
    
    playbook_path = args.playbook
    if not Path(playbook_path).exists(): playbook_path = str(project_root / args.playbook)

    # 2. EJECUTAR
    runner = EvaluationRunner(agent_playbook=playbook_path)
    results = await runner.run_suite(str(suite_path))
    
    # 3. GENERAR REPORTE JSON (Artefacto de Calidad)
    report = {
        "timestamp": timestamp,
        "suite": args.suite,
        "playbook": args.playbook,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed)
        },
        "results": [r.to_dict() for r in results]
    }
    
    json_path = output_dir / "evaluation_report.json"
    with open(json_path, 'w') as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"\n📊 REPORT SAVED: {json_path}")
    logger.info(f"✅ PASSED: {report['summary']['passed']}/{report['summary']['total']}")
    
    if report['summary']['failed'] > 0:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())