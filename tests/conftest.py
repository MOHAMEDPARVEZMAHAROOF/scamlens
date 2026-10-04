"""Pytest path setup: make the ScamLens project root importable.

Tests import the `scamlens` package (lexicons, prompts, prescreen, app), so
the project root (parent of the `scamlens/` package dir) must be on sys.path
no matter where pytest is invoked from.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
