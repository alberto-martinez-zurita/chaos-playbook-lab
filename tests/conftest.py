# tests/conftest.py

import sys
from pathlib import Path

# Añade src al PYTHONPATH para que pytest encuentre los módulos
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
