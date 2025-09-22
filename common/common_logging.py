"""Minimal logging utilities.

Simplified version providing only log_line function for backwards compatibility.
"""
from __future__ import annotations
from typing import Callable, Optional
import sys


def log_line(level: str, msg: str, name: str = 'redconflict', sink: Optional[Callable[[str], None]] = None):
    """Log a single line message."""
    try:
        if sink:
            sink(f"{level.upper()}: {name}: {msg}")
        else:
            sys.stderr.write(f"{level.upper()}: {name}: {msg}\n")
    except Exception:
        pass


__all__ = ['log_line']
