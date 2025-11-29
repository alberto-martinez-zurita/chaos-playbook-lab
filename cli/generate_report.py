"""
CLI entry point for Dashboard Generation.
Wraps the reporting engine logic.
"""
import sys
from pathlib import Path

# Asegurar que encontramos el paquete si se ejecuta como script suelto (fallback)
# Aunque con pip install -e . no haría falta, es una buena red de seguridad.
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from chaos_engine.reporting.dashboard import main

if __name__ == "__main__":
    main()