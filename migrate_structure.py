import os
import shutil
from pathlib import Path

# Mapa de migración: "Origen" -> "Destino"
# Las rutas destino son relativas a la raíz del proyecto
MOVES = {
    # --- 1. CLI (Scripts de ejecución) ---
    "scripts/run_parametric_experiments.py": "cli/run_simulation.py",
    "scripts/run_agent_comparison.py": "cli/run_comparison.py",
    
    # --- 2. Reporting (Lógica de Dashboard) ---
    "scripts/generate_dashboard.py": "src/chaos_engine/reporting/dashboard.py",
    
    # --- 3. Agents ---
    "agents/petstore_agent.py": "src/chaos_engine/agents/petstore.py",
    "agents/order_agent_llm.py": "src/chaos_engine/agents/legacy_order.py",
    
    # --- 4. Chaos Core ---
    "core/chaos_proxy.py": "src/chaos_engine/chaos/proxy.py",
    "config/chaos_config.py": "src/chaos_engine/chaos/config.py", # La clase ChaosConfig
    "tools/chaos_injection_helper.py": "src/chaos_engine/chaos/injection.py",
    
    # --- 5. Simulation (Fase 5) ---
    "tools/simulated_apis.py": "src/chaos_engine/simulation/apis.py",
    "runners/ab_test_runner.py": "src/chaos_engine/simulation/runner.py",
    "experiments/parametric_ab_test_runner.py": "src/chaos_engine/simulation/parametric.py",
    
    # --- 6. Core Infrastructure ---
    "core/logging_setup.py": "src/chaos_engine/core/logging.py",
    "config/config_loader.py": "src/chaos_engine/core/config.py", # El loader
    "tools/retry_wrapper.py": "src/chaos_engine/core/resilience.py",
    "data/playbook_storage.py": "src/chaos_engine/core/storage.py",
    
    # --- 7. Configuration Files (YAML) ---
    "config/dev_config.yaml": "config/dev.yaml",
    "config/prod_config.yaml": "config/prod.yaml",
    "config/chaos_agent.yaml": "config/presets.yaml",
    
    # --- 8. Assets (JSON Knowledge Base) ---
    "data/http_error_codes.json": "assets/knowledge_base/http_error_codes.json",
    
    # --- 9. Playbooks (Renombrando para claridad) ---
    "data/playbook_petstore_baseline.json": "assets/playbooks/baseline.json",
    "data/playbook_petstore_weak.json": "assets/playbooks/weak.json",
    "data/playbook_petstore_strong.json": "assets/playbooks/strong.json",
    "data/playbook_petstore_training.json": "assets/playbooks/training.json",
    
    # --- 10. Playbooks Legacy (Limpieza) ---
    "data/chaos_playbook.json": "assets/playbooks/legacy/phase5_chaos.json",
    "data/playbook_phase6.json": "assets/playbooks/legacy/phase6_draft.json",
    "data/playbook_phase6_petstore.json": "assets/playbooks/legacy/phase6_petstore_v1.json",
    "data/playbook_phase6_petstore_2.json": "assets/playbooks/legacy/phase6_petstore_v2.json",
}

def migrate():
    root = Path.cwd()
    print(f"🚀 Iniciando REESTRUCTURACIÓN MAESTRA en: {root}")
    
    # A. Crear directorios base
    print("\n[1/3] Creando arquitectura de carpetas...")
    dirs = [
        "cli",
        "config",
        "assets/knowledge_base",
        "assets/playbooks/legacy",
        "src/chaos_engine/agents",
        "src/chaos_engine/chaos",
        "src/chaos_engine/simulation",
        "src/chaos_engine/core",
        "src/chaos_engine/reporting",
        "logs",     # Asegurar que existen
        "results"   # Asegurar que existen
    ]
    
    for d in dirs:
        path = root / d
        path.mkdir(parents=True, exist_ok=True)
        # Crear __init__.py en carpetas de código (src)
        if d.startswith("src"):
            (path / "__init__.py").touch(exist_ok=True)
            
    # Init raíz
    (root / "src/chaos_engine/__init__.py").touch(exist_ok=True)

    # B. Mover archivos
    print("\n[2/3] Migrando archivos...")
    moved = 0
    missing = 0
    
    for old_path_str, new_path_str in MOVES.items():
        old_file = root / old_path_str
        new_file = root / new_path_str
        
        if old_file.exists():
            try:
                shutil.move(str(old_file), str(new_file))
                print(f"  ✅ MOVED: {old_path_str:<40} -> {new_path_str}")
                moved += 1
            except Exception as e:
                print(f"  ❌ ERROR: {old_path_str} -> {e}")
        else:
            # Check si ya se movió (idempotencia)
            if new_file.exists():
                print(f"  ℹ️  SKIP: {new_path_str} ya existe.")
            else:
                print(f"  ⚠️  MISSING: {old_path_str} no encontrado.")
                missing += 1

    # C. Limpieza de carpetas vacías antiguas
    print("\n[3/3] Limpiando directorios vacíos...")
    old_dirs = ["scripts", "agents", "core", "runners", "experiments", "tools", "data"]
    for d in old_dirs:
        path = root / d
        if path.exists() and not any(path.iterdir()):
            path.rmdir()
            print(f"  🗑️  REMOVED EMPTY DIR: {d}")
        elif path.exists():
            print(f"  ⚠️  DIR NOT EMPTY (Revisar manualmente): {d}")

    print(f"\n✨ Migración finalizada. {moved} archivos movidos. {missing} no encontrados.")
    print("📢 SIGUIENTE PASO: Ejecuta 'pip install -e .' para registrar el nuevo paquete.")

if __name__ == "__main__":
    migrate()