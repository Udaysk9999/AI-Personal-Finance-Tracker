"""Pytest configuration: add the project root to sys.path so tests can import
app modules (database, finance_ml, etc.) without installing them as a package."""

import sys
from pathlib import Path

# Add the project root (parent of tests/) to the Python path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
