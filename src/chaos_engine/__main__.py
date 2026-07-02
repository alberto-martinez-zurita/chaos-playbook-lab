"""Entry point — use scripts/run_experiment.py for experiment execution."""
from __future__ import annotations

import sys


def main() -> None:
    print("Use scripts/run_experiment.py to run experiments.")
    print("  python scripts/run_experiment.py --config experiments/<name>/experiment.yaml")
    sys.exit(0)


if __name__ == "__main__":
    main()
