"""
Verify simulated_apis.py - Show actual implementation
======================================================

Purpose: Display the ACTUAL code of call_simulated_inventory_api
         to see what endpoints are really supported.
"""

import sys
from pathlib import Path
import inspect

# Add src to path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from chaos_playbook_engine.tools.simulated_apis import call_simulated_inventory_api

print("\n" + "="*70)
print("ACTUAL IMPLEMENTATION OF call_simulated_inventory_api")
print("="*70)

try:
    source = inspect.getsource(call_simulated_inventory_api)
    print(source)
except Exception as e:
    print(f"❌ Could not get source: {e}")

print("\n" + "="*70)
print("ANALYSIS")
print("="*70)
print("\nLook for:")
print("  1. if endpoint == 'checkstock':  ← Should be present")
print("  2. elif endpoint == 'reservestock':  ← Should be present")
print("  3. else: raise ValueError(...)  ← Should be at the end")
print("\nIf 'checkstock' is NOT in the if/elif chain, that's the bug.")
