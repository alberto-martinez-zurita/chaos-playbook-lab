# SETUP - Chaos Playbook Engine Installation & Configuration

**Version**: 3.0  
**Date**: November 24, 2025  
**Target**: Windows 10/11 + MacOS + Linux  
**Python**: 3.10+ required (3.11+ recommended)

---

## TABLE OF CONTENTS

1. [Quick Start](#quick-start)
2. [System Requirements](#system-requirements)
3. [Installation Methods](#installation-methods)
4. [Verification](#verification)
5. [Running Tests](#running-tests)
6. [Common Issues & Troubleshooting](#common-issues--troubleshooting)
7. [Project Structure](#project-structure)
8. [Running Experiments](#running-experiments)

---

## QUICK START

### For Windows (PowerShell)

```powershell
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 3. Upgrade pip
python -m pip install --upgrade pip

# 4. Install dependencies
pip install -r requirements.txt

# 5. Verify installation
python -c "import google.genai; import pandas; import plotly; print('✅ Setup complete!')"
```

### For MacOS/Linux (Bash/Zsh)

```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Activate virtual environment
source venv/bin/activate

# 3. Upgrade pip
python -m pip install --upgrade pip

# 4. Install dependencies
pip install -r requirements.txt

# 5. Verify installation
python -c "import google.genai; import pandas; import plotly; print('✅ Setup complete!')"
```

---

## SYSTEM REQUIREMENTS

### Minimum Requirements

| Component | Requirement | Recommended |
|-----------|-------------|-------------|
| **OS** | Windows 10, MacOS 10.14+, Linux (Ubuntu 18.04+) | Windows 11, MacOS 12+, Ubuntu 22.04+ |
| **Python** | 3.10+ | 3.11 or 3.12 |
| **RAM** | 4GB | 8GB+ |
| **Disk Space** | 1GB | 2GB+ |
| **Internet** | Required (for pip install) | Required |

### Pre-Installation Checks

**Windows (PowerShell)**:
```powershell
# Check Python version
python --version  # Should be 3.10+

# Check pip version
pip --version

# Check pip location
pip list | head -5
```

**MacOS/Linux (Bash)**:
```bash
# Check Python version
python3 --version  # Should be 3.10+

# Check pip version
pip3 --version

# Check pip location
pip3 list | head -5
```

---

## INSTALLATION METHODS

### Method 1: Pip with Virtual Environment (Recommended)

**Step 1: Create Virtual Environment**

Windows (PowerShell):
```powershell
python -m venv venv
```

MacOS/Linux (Bash):
```bash
python3 -m venv venv
```

**Step 2: Activate Virtual Environment**

Windows (PowerShell):
```powershell
.\venv\Scripts\Activate.ps1
# You should see (venv) in your prompt
```

Windows (Command Prompt - Alternative):
```cmd
.\venv\Scripts\activate.bat
```

MacOS/Linux (Bash):
```bash
source venv/bin/activate
# You should see (venv) in your prompt
```

**Step 3: Upgrade pip (Important)**

```bash
python -m pip install --upgrade pip
```

**Step 4: Install Dependencies**

```bash
pip install -r requirements.txt
```

This will install:
- ✅ google-genai (Google ADK Framework)
- ✅ pandas (Data manipulation)
- ✅ plotly (Visualizations)
- ✅ pytest (Testing framework)
- ✅ mypy (Type checking)
- ✅ All dev dependencies

**Expected output**:
```
Successfully installed google-genai-1.18.0 pandas-2.0.0 plotly-5.18.0 ...
```

### Method 2: Poetry (Alternative - More Professional)

**Step 1: Install Poetry**

Windows (PowerShell):
```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

MacOS/Linux (Bash):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**Step 2: Create pyproject.toml**

```bash
poetry init
```

Follow prompts, then install:
```bash
poetry install
```

**Step 3: Activate Poetry Shell**

```bash
poetry shell
```

---

## VERIFICATION

### Verify Installation

```bash
# Test all core dependencies
python -c "
import google.genai
import pandas as pd
import plotly.graph_objects as go
import pytest
import mypy
print('✅ All core dependencies installed!')
"
```

### Verify Project Structure

```bash
# Check if key directories exist
ls -la  # MacOS/Linux
dir     # Windows PowerShell

# Expected structure:
# chaos-playbook-engine/
# ├── src/chaos_playbook_engine/
# ├── tests/
# ├── scripts/
# ├── data/
# ├── requirements.txt
# └── pyproject.toml
```

### Check Python Version

```bash
python --version  # Should be 3.10.x, 3.11.x, or 3.12.x
```

---

## RUNNING TESTS

### Run All Tests

```bash
pytest tests/ -v
```

### Run with Coverage Report

```bash
pytest tests/ --cov=chaos_playbook_engine --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`

### Run Specific Test Suite

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# End-to-end tests only
pytest tests/e2e/ -v
```

### Run with Verbose Output

```bash
pytest tests/ -v -s
```

The `-s` flag shows print statements during tests.

### Expected Test Results

```
========================= test session starts ==========================
collected 100+ items

tests/unit/test_chaos_config.py::test_chaos_config_initialization PASSED
tests/unit/test_simulated_apis.py::test_inventory_api PASSED
tests/integration/test_ab_runner.py::test_baseline_execution PASSED
...
========================= 100+ passed in X.XXs ==========================
```

---

## COMMON ISSUES & TROUBLESHOOTING

### Issue 1: Python Version Too Old

**Error**: `ERROR: Python 3.9 is not supported`

**Solution**:
```powershell
# Windows: Install Python 3.11+
# 1. Download from https://www.python.org/downloads/
# 2. Run installer, check "Add Python to PATH"
# 3. Verify: python --version

# MacOS: Use Homebrew
brew install python@3.11

# Linux (Ubuntu):
sudo apt-get install python3.11 python3.11-venv
```

### Issue 2: Virtual Environment Not Activating

**Error**: `(venv) not appearing in prompt` or `venv not found`

**Solution**:
```powershell
# Windows: Try alternative activation
.\venv\Scripts\Activate.ps1

# If that fails, check if you're in PowerShell execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then retry:
.\venv\Scripts\Activate.ps1
```

### Issue 3: pip install fails with SSL Error

**Error**: `SSL: CERTIFICATE_VERIFY_FAILED`

**Solution**:
```bash
# Temporarily disable SSL verification (not recommended for production)
pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org

# Better: Install certificates (MacOS)
/Applications/Python\ 3.11/Install\ Certificates.command
```

### Issue 4: Permission Denied on MacOS/Linux

**Error**: `Permission denied: '/usr/local/bin/pytest'`

**Solution**:
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Then reinstall
pip install --upgrade -r requirements.txt
```

### Issue 5: Import Error for google.genai

**Error**: `ModuleNotFoundError: No module named 'google.genai'`

**Solution**:
```bash
# 1. Verify venv is activated
which python  # Should show venv path

# 2. Reinstall google-genai
pip install --upgrade google-genai

# 3. Test import
python -c "import google.genai; print('OK')"
```

### Issue 6: Plotly Visualization Not Working

**Error**: `plotly not installed` or `Cannot render HTML`

**Solution**:
```bash
# Reinstall plotly
pip install --upgrade plotly

# Verify
python -c "import plotly; print(plotly.__version__)"
```

---

## PROJECT STRUCTURE

```
chaos-playbook-engine/
├── src/chaos_playbook_engine/
│   ├── config/
│   │   └── chaos_config.py          # Chaos injection configuration
│   ├── apis/
│   │   └── simulated_apis.py        # Mock API implementations
│   ├── services/
│   │   ├── playbook_storage.py      # RAG playbook persistence
│   │   └── retry_wrapper.py         # Retry logic with backoff
│   ├── runners/
│   │   ├── ab_test_runner.py        # A/B test execution
│   │   └── parametric_ab_test_runner.py  # Parametric testing (Phase 5)
│   ├── evaluation/
│   │   ├── experiment_evaluator.py  # Metrics evaluation
│   │   ├── aggregate_metrics.py     # Statistical aggregation
│   │   └── generate_report.py       # Report generation
│   └── tools/
│       └── chaos_injection_helper.py # Chaos utilities
├── tests/
│   ├── unit/                        # Unit tests (>80% coverage)
│   ├── integration/                 # Integration tests
│   └── e2e/                         # End-to-end tests
├── scripts/
│   ├── run_parametric_ab_test.py    # CLI for parametric testing
│   └── view_playbook.py             # Playbook inspector
├── data/
│   └── chaos_playbook.json          # Learned recovery strategies
├── requirements.txt                 # Pip dependencies
├── pyproject.toml                   # Poetry configuration
└── README.md                        # Project documentation
```

---

## RUNNING EXPERIMENTS

### Run Parametric A/B Test (Phase 5)

```bash
# Basic run with defaults
python scripts/run_parametric_ab_test.py

# With custom failure rates
python scripts/run_parametric_ab_test.py \
  --failure-rates 0.1 0.3 0.5 \
  --experiments-per-rate 10

# With custom seed for reproducibility
python scripts/run_parametric_ab_test.py \
  --seed 42 \
  --failure-rates 0.1 0.3 0.5

# With verbose output
python scripts/run_parametric_ab_test.py --verbose

# Output files generated:
# - raw_results.csv              # Individual experiment data
# - aggregated_metrics.json      # Statistical summaries
# - dashboard.html               # Interactive visualization
```

### Run Unit Tests Only

```bash
pytest tests/unit/ -v --cov=chaos_playbook_engine
```

### Run Integration Tests

```bash
pytest tests/integration/ -v
```

### View Playbook Contents

```bash
python scripts/view_playbook.py
```

---

## ENVIRONMENT VARIABLES

Create a `.env` file in the project root:

```bash
# .env (Optional configuration)
CHAOS_ENABLED=true
CHAOS_FAILURE_RATE=0.3
LOG_LEVEL=INFO
RESULTS_DIR=results/
DATA_DIR=data/
```

Load with:
```python
from dotenv import load_dotenv
import os

load_dotenv()
chaos_enabled = os.getenv("CHAOS_ENABLED", "true").lower() == "true"
```

---

## NEXT STEPS

### After Installation

1. ✅ Run tests: `pytest tests/ -v`
2. ✅ Run experiments: `python scripts/run_parametric_ab_test.py`
3. ✅ View dashboard: Open `results/*/dashboard.html` in browser
4. ✅ Check metrics: `cat results/*/aggregated_metrics.json`

### For Development

1. ✅ Install dev dependencies: `pip install -r requirements.txt`
2. ✅ Run type checker: `mypy src/ --strict`
3. ✅ Format code: `black src/ tests/`
4. ✅ Lint code: `flake8 src/ tests/`

### Documentation

- 📖 Architecture: `docs/Capstone-Architecture-v3.md`
- 📖 Plan: `docs/Capstone-Plan-v3-Final.md`
- 📖 Lessons: `docs/LESSONS_LEARNED.md`
- 📖 ADRs: `docs/Architecture-Decisions-Complete.md`

---

## GETTING HELP

### Verify Installation

```bash
# Check all dependencies
pip list | grep -E "google-genai|pandas|plotly|pytest"

# Check versions
python -c "
import google.genai
import pandas
import plotly
print(f'google-genai: {google.genai.__version__}')
print(f'pandas: {pandas.__version__}')
print(f'plotly: {plotly.__version__}')
"
```

### Report Issues

If you encounter issues, run this diagnostic:

```bash
# Windows (PowerShell)
$diagnostic = @"
Python Version: $(python --version)
Pip Version: $(pip --version)
Installed Packages:
$(pip list)
"@
Write-Host $diagnostic | Out-File -FilePath diagnostic.txt
# Email diagnostic.txt

# MacOS/Linux (Bash)
{
  echo "Python Version: $(python3 --version)"
  echo "Pip Version: $(pip3 --version)"
  echo "Installed Packages:"
  pip3 list
} > diagnostic.txt
# Email diagnostic.txt
```

---

## UNINSTALLATION

### Remove Virtual Environment

**Windows (PowerShell)**:
```powershell
# Deactivate first
deactivate

# Remove venv folder
Remove-Item -Recurse -Force venv
```

**MacOS/Linux (Bash)**:
```bash
# Deactivate first
deactivate

# Remove venv folder
rm -rf venv
```

### Remove Poetry Installation

```bash
# Deactivate poetry shell
exit

# Remove poetry
python -m pip uninstall poetry
```

---

## SUCCESS CHECKLIST

- [ ] Python 3.10+ installed
- [ ] Virtual environment created
- [ ] Virtual environment activated (you see `(venv)` in prompt)
- [ ] pip upgraded
- [ ] requirements.txt installed (`pip install -r requirements.txt`)
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Import verification successful
- [ ] First experiment runs successfully

**When all checked ✅ → You're ready to go!**

---

**Last Updated**: November 24, 2025  
**Maintainer**: Chaos Playbook Engine Team  
**Status**: Production-Ready (Phase 5 Complete)
