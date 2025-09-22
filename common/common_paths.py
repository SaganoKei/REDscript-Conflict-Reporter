"""Common path detection utilities for source/frozen environments.

Centralizes PyInstaller-aware path resolution patterns found across:
- gui_conflict_report.py
- common_assets.py
- common_i18n.py
- common_impact.py
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import sys
import os


def get_module_base(file_path: str) -> Path:
    """Get module's base directory (source or frozen)."""
    try:
        return Path(file_path).parent.resolve()
    except Exception:
        return Path.cwd()


def get_frozen_base() -> Optional[Path]:
    """Get PyInstaller frozen base directory if available."""
    try:
        if getattr(sys, 'frozen', False):
            base = getattr(sys, '_MEIPASS', '')
            if base:
                return Path(base)
    except Exception:
        pass
    return None


def get_executable_dir() -> Path:
    """Get directory containing the executable (frozen or script)."""
    try:
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        else:
            return Path(__file__).parent.resolve()
    except Exception:
        return Path.cwd()


def build_candidate_paths(
    base_name: str,
    env_multi: Optional[str] = None,
    env_single: Optional[str] = None,
    relative_subdirs: Optional[List[str]] = None
) -> List[Path]:
    """Build ordered list of candidate paths for resource discovery.

    Parameters:
    - base_name: subdirectory name (e.g., 'assets', 'i18n')
    - env_multi: environment variable for pathsep-separated list
    - env_single: environment variable for single path (legacy)
    - relative_subdirs: additional relative paths to check

    Returns deduplicated ordered list following common pattern:
    1. Environment multi-path variable
    2. Environment single-path variable
    3. CWD/base_name
    4. Module local paths
    5. Frozen base paths
    6. Additional relative paths
    """
    candidates: List[Path] = []

    # Environment overrides
    if env_multi:
        multi = os.environ.get(env_multi)
        if multi:
            for part in multi.split(os.pathsep):
                if part.strip():
                    candidates.append(Path(part.strip()))

    if env_single:
        single = os.environ.get(env_single)
        if single:
            candidates.append(Path(single))

    # Standard locations
    candidates.append(Path.cwd() / base_name)

    # Module relative
    module_base = get_module_base(__file__)
    candidates.append(module_base / base_name)
    candidates.append(module_base.parent / base_name)

    # Frozen location
    frozen_base = get_frozen_base()
    if frozen_base:
        candidates.append(frozen_base / base_name)

    # Additional relative paths
    if relative_subdirs:
        for subdir in relative_subdirs:
            candidates.append(Path.cwd() / subdir)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: List[Path] = []
    for p in candidates:
        try:
            resolved = p.resolve()
        except Exception:
            resolved = p
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            unique.append(resolved)

    return unique


__all__ = [
    'get_module_base', 'get_frozen_base', 'get_executable_dir', 'build_candidate_paths'
]