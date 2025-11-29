import os
from pathlib import Path

# Mapa de Reemplazos: "Texto Viejo" -> "Texto Nuevo"
REPLACEMENTS = {
    # Agents
    "from agents.petstore_agent": "from chaos_engine.agents.petstore",
    "from agents.order_agent_llm": "from chaos_engine.agents.legacy_order",
    
    # Chaos Core
    "from core.chaos_proxy": "from chaos_engine.chaos.proxy",
    "from config.chaos_config": "from chaos_engine.chaos.config",
    "from tools.chaos_injection_helper": "from chaos_engine.chaos.injection",
    
    # Simulation
    "from tools.simulated_apis": "from chaos_engine.simulation.apis",
    "from runners.ab_test_runner": "from chaos_engine.simulation.runner",
    "from experiments.parametric_ab_test_runner": "from chaos_engine.simulation.parametric",
    
    # Core Infrastructure
    "from core.logging_setup": "from chaos_engine.core.logging",
    "from config.config_loader": "from chaos_engine.core.config",
    "from tools.retry_wrapper": "from chaos_engine.core.resilience",
    "from data.playbook_storage": "from chaos_engine.core.storage",
    
    # Fix imports dentro de los propios módulos movidos
    "from runners.ab_test_runner import ABTestRunner": "from chaos_engine.simulation.runner import ABTestRunner",
    
    # Reporting
    "from scripts.generate_dashboard": "from chaos_engine.reporting.dashboard",
}

def update_files():
    root = Path.cwd()
    extensions = [".py"]
    
    print("🚀 Iniciando actualización de imports...")
    
    # Recorrer src/ y cli/
    target_dirs = [root / "src", root / "cli"]
    
    for target_dir in target_dirs:
        for file_path in target_dir.rglob("*"):
            if file_path.suffix in extensions and file_path.is_file():
                if file_path.name == "update_imports.py" or file_path.name == "migrate_structure.py":
                    continue
                
                try:
                    content = file_path.read_text(encoding="utf-8")
                    original_content = content
                    
                    # Aplicar reemplazos
                    for old, new in REPLACEMENTS.items():
                        content = content.replace(old, new)
                    
                    # Limpiar hacks de sys.path (ya no son necesarios)
                    lines = content.splitlines()
                    clean_lines = []
                    skip_block = False
                    for line in lines:
                        # Eliminar bloques de manipulación de sys.path
                        if "sys.path.insert" in line or "project_root =" in line:
                            continue
                        # Eliminar imports de sys y pathlib si solo se usaban para el path hack
                        if line.strip() == "import sys" and "sys" not in content.replace("import sys", ""):
                            continue 
                            
                        clean_lines.append(line)
                        
                    content = "\n".join(clean_lines)

                    if content != original_content:
                        file_path.write_text(content, encoding="utf-8")
                        print(f"  ✅ Actualizado: {file_path.relative_to(root)}")
                        
                except Exception as e:
                    print(f"  ❌ Error leyendo {file_path}: {e}")

    print("\n✨ Imports actualizados. El código ahora apunta a 'chaos_engine'.")

if __name__ == "__main__":
    update_files()