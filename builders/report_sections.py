"""Shared section builders for report rendering (HTML/Markdown).

Currently focuses on wrap coexistence aggregation to eliminate duplicated
loops scattered in report_builders.

Public helpers:
  build_wrap_coexistence_index(report) -> dict with keys:
      'wrap': list[group], 'replace_wrap': list[group], 'has_any': bool
  iter_wrap_groups(report, kind) -> yields normalized groups (sorted)

Design notes:
- Sorting: stable (class, method) ascending to match existing output.
- Input safety: treat missing keys as empty list.
- Pure functions: no mutation of input report.
"""
from __future__ import annotations
from typing import Iterable, Dict, Any, List, Iterator

def _sorted_groups(groups: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        return sorted((groups or []), key=lambda g: (g.get('class',''), g.get('method','')))
    except Exception:
        return list(groups) if groups else []

def build_wrap_coexistence_index(report: Dict[str, Any]) -> Dict[str, Any]:
    try:
        wrap = _sorted_groups(report.get('wrap_coexistence') or [])
        rep_wrap = _sorted_groups(report.get('replace_wrap_coexistence') or [])
        return {
            'wrap': wrap,
            'replace_wrap': rep_wrap,
            'has_any': bool(wrap or rep_wrap),
        }
    except Exception:
        return {'wrap': [], 'replace_wrap': [], 'has_any': False}

def iter_wrap_groups(report: Dict[str, Any], kind: str) -> Iterator[Dict[str, Any]]:
    idx = build_wrap_coexistence_index(report)
    target: List[Dict[str, Any]] = []
    if kind == 'wrap':
        target = idx['wrap']
    elif kind == 'replace_wrap':
        target = idx['replace_wrap']
    for g in target:
        yield g

__all__ = ['build_wrap_coexistence_index', 'iter_wrap_groups']
