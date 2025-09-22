"""Common impact & symptom classification logic.

This module centralizes the previously duplicated logic in report_builders / GUI.
Public API (stable):
  compute_impact_unified(cls, meth, mods, entries, *, config=None, wrap_coexist=False) -> dict
  classify_conflict_symptom(cls_name: str, meth: str='') -> str
  symptom_label(code: str, tr: Translator|None) -> str

All functions are pure (no side effects) and defensive: on error they degrade
gracefully instead of raising.
"""
from __future__ import annotations
from typing import Any
import re, json
from pathlib import Path

# Default impact profile (thresholds + weights)
# Embedded fallback default (used if external file missing or invalid)
_IMPACT_DEFAULT_CONFIG = {
    'thresholds': {
        'critical': 95,
        'high': 70,
        'medium': 45,
    },
    'weights': {
        'per_mod': 10,
        'class_keywords': {
            'vehicle': 15, 'quest': 12, 'player': 12, 'inventory': 10,
            'damage': 10, 'ui': 8, 'hud': 8, 'ink': 6,
        },
        'method_keywords': {
            'update': 12, 'tick': 12, 'initialize': 10, 'init': 10, 'onattach': 8,
            'onunattach': 6, 'refresh': 8, 'calculate': 8, 'resolve': 8,
        },
        'signature': {'per_arg': 3, 'has_return': 6},
        'wrap_coexist_bonus': 12,
    }
}

_IMPACT_EXTERNAL_CACHE: dict | None = None

def _load_external_default() -> dict | None:
    """Attempt to load assets/impact_config.json (once) as the default profile.

    Search order (first hit wins):
      1. Environment variable REDCONFLICT_IMPACT_CONFIG
      2. ./assets/impact_config.json (cwd)
      3. <package_dir>/assets/impact_config.json (module relative)
    Returns parsed dict or None on failure.
    """
    global _IMPACT_EXTERNAL_CACHE
    if _IMPACT_EXTERNAL_CACHE is not None:
        return _IMPACT_EXTERNAL_CACHE
    candidates: list[Path] = []
    try:
        import os
        envp = os.environ.get('REDCONFLICT_IMPACT_CONFIG')
        if envp:
            candidates.append(Path(envp))
    except Exception:
        pass
    try:
        candidates.append(Path.cwd() / 'assets' / 'impact_config.json')
    except Exception:
        pass
    try:
        mod_dir = Path(__file__).parent
        candidates.append(mod_dir / 'assets' / 'impact_config.json')
        candidates.append(mod_dir.parent / 'assets' / 'impact_config.json')
    except Exception:
        pass
    for cand in candidates:
        try:
            if cand.exists() and cand.is_file():
                data = json.loads(cand.read_text(encoding='utf-8'))
                if isinstance(data, dict) and 'thresholds' in data and 'weights' in data:
                    _IMPACT_EXTERNAL_CACHE = data
                    return data
        except Exception:
            continue
    _IMPACT_EXTERNAL_CACHE = None
    return None

def get_default_impact_config() -> dict:
    """Return the active default impact config (external if available)."""
    return _load_external_default() or _IMPACT_DEFAULT_CONFIG

# Symptom keyword mapping
_SYMPTOM_KEYWORDS = [
    ('uiHud', ['ui', 'hud', 'ink']),
    ('player', ['player', 'puppet', 'equipment']),
    ('vehicle', ['vehicle']),
    ('quest', ['quest', 'journal', 'fact']),
    ('inventory', ['inventory']),
    ('damage', ['damage', 'hit']),
]

def classify_conflict_symptom(cls_name: str, meth: str = '') -> str:
    """Return normalized symptom code based on class name keywords.

    Language files are assumed to always exist with required keys.
    """
    s = (cls_name or '').lower()
    for code, kws in _SYMPTOM_KEYWORDS:
        if any(k in s for k in kws):
            return code
    # Return 'other' if no specific symptom matched
    return 'other'

def compute_impact_unified(cls: str, meth: str, mods: list, entries: list, *,
                           config: dict | None = None,
                           wrap_coexist: bool = False) -> dict:
    """Return unified impact dict {'severity':str,'message':str}."""
    try:
        cfg = config or get_default_impact_config()
        weights = (cfg.get('weights') or {})
        thresholds = (cfg.get('thresholds') or {})
        mod_count = len(set(mods or []))
        score = 0
        score += int(weights.get('per_mod', 0)) * mod_count
        cls_l = (cls or '').lower(); meth_l = (meth or '').lower()
        for kw, w in (weights.get('class_keywords') or {}).items():
            if kw in cls_l:
                score += int(w)
        for kw, w in (weights.get('method_keywords') or {}).items():
            if kw in meth_l:
                score += int(w)
        sig_w = (weights.get('signature') or {})
        per_arg = int(sig_w.get('per_arg', 0)); has_ret_w = int(sig_w.get('has_return', 0))
        func_sig = ''
        if entries:
            func_sig = entries[0].get('func_sig') or ''
        args_count = 0; has_return = False
        if func_sig:
            try:
                m = re.search(r'\((.*?)\)', func_sig)
                if m:
                    inner = m.group(1).strip()
                    if inner:
                        args_count = len([a for a in inner.split(',') if a.strip()])
                if '->' in func_sig:
                    ret_part = func_sig.split('->', 1)[1].strip()
                    if ret_part and ret_part.lower() != 'void':
                        has_return = True
            except Exception:
                pass
        score += per_arg * args_count
        if has_return:
            score += has_ret_w
        if wrap_coexist:
            score += int(weights.get('wrap_coexist_bonus', 0))
        sev = 'Low'
        if score >= int(thresholds.get('critical', 80)):
            sev = 'Critical'
        elif score >= int(thresholds.get('high', 60)):
            sev = 'High'
        elif score >= int(thresholds.get('medium', 40)):
            sev = 'Medium'
        code = classify_conflict_symptom(cls, meth)
        base_key = f"impact.symptom.{code}"
        # Emit i18n key token instead of English parenthetical so downstream localization
        # can treat wrap coexistence uniformly without string parsing.
        wrap_note = ' impact.extra.wrapCoexist' if wrap_coexist else ''
        msg = f"{base_key}{wrap_note}"
        return {'severity': sev, 'message': msg}
    except Exception:
        return {'severity': '', 'message': ''}

def symptom_label(code: str, tr) -> str:
    """Return translated symptom label.

    Language files are assumed to always exist with required keys.
    """
    return tr(f'impact.symptom.{code}')

__all__ = [
    'compute_impact_unified', 'classify_conflict_symptom', 'symptom_label',
    '_IMPACT_DEFAULT_CONFIG', 'get_default_impact_config'
]
