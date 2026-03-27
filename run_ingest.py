#!/usr/bin/env python3
"""Wrapper to run scroll ingest with proper module resolution."""
import sys
from pathlib import Path

# Ensure scroll package is importable
sys.path.insert(0, str(Path(__file__).parent))

from scroll.cli import cli
cli()
