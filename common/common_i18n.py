"""Common i18n utilities shared by CLI / GUI / builders.

Phase 1 extraction (safe, backwards compatible):
 - Consolidates translation bundle discovery & translator creation.
 - Existing modules (report_builders, redscript_report_common, gui_conflict_report)
   can continue calling their local helpers; those helpers may delegate here.

Design goals:
 - Zero third‑party deps (pure stdlib).
 - Robust path discovery (handles frozen executables and source tree invocation).
 - Lazy, idempotent bundle loading (cache in module global).
 - Fallback English translator with small stable key set to avoid key leakage.
 - Defensive error handling: never raise in production paths; always return a callable.

Future (Phase 2+):
 - Introduce runtime cache invalidation on file change timestamps if hot‑reloading desired.
 - Provide pluralization helpers if needed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Callable, Optional, Iterable, Tuple
import re as _re
import json
import locale

Translator = Callable[[str], str]

_BUNDLE_CACHE: Dict[str, Dict[str, Any]] | None = None


def _candidate_i18n_dirs(extra: Optional[Iterable[Path]] = None) -> list[Path]:
    """Return ordered list of candidate i18n directories.

    Precedence (earlier entries have priority on duplicate language codes):
      1. REDCONFLICT_I18N_DIRS (os.pathsep-separated list of directories)
      2. REDCONFLICT_I18N (legacy single directory path)
      3. Package local i18n/ (module dir, then parent) and CWD/i18n
      4. Frozen (_MEIPASS) i18n directory (PyInstaller one-dir)
      5. Any explicit 'extra' iterable paths provided by caller (appended last)

    All paths are deduplicated while preserving first occurrence order.
    """
    cand: list[Path] = []
    # Environment overrides
    try:
        import os
        multi = os.environ.get('REDCONFLICT_I18N_DIRS')
        if multi:
            for part in multi.split(os.pathsep):
                if part.strip():
                    cand.append(Path(part.strip()))
        legacy = os.environ.get('REDCONFLICT_I18N')
        if legacy:
            cand.append(Path(legacy))
    except Exception:
        pass
    here = Path(__file__).parent.resolve()
    cand.append(here / 'i18n')
    cand.append(here.parent / 'i18n')
    cand.append(Path.cwd() / 'i18n')
    # PyInstaller one-dir/_MEIPASS like layout (sys._MEIPASS not imported to avoid overhead if absent)
    try:  # pragma: no cover
        import sys
        if getattr(sys, 'frozen', False):
            base = Path(getattr(sys, '_MEIPASS', ''))
            if base:
                cand.append(base / 'i18n')
    except Exception:
        pass
    if extra:
        for p in extra:
            try:
                cand.append(Path(p))
            except Exception:
                pass
    # de-dup while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for p in cand:
        sp = str(p.resolve()) if p else ''
        if sp and sp not in seen:
            seen.add(sp)
            out.append(p)
    return out


def load_bundles(force: bool = False) -> Dict[str, Dict[str, Any]]:
    global _BUNDLE_CACHE
    if _BUNDLE_CACHE is not None and not force:
        return _BUNDLE_CACHE
    bundles: Dict[str, Dict[str, Any]] = {}
    for d in _candidate_i18n_dirs():
        try:
            if not d.exists():
                continue
            for f in d.glob('*.json'):
                try:
                    data = json.loads(f.read_text(encoding='utf-8'))
                    lang = (data.get('$meta') or {}).get('lang') or f.stem
                    bundles[str(lang)] = data
                except Exception:
                    continue
        except Exception:
            continue
    _BUNDLE_CACHE = bundles
    return bundles


def choose_lang(bundles: Dict[str, Dict[str, Any]], requested: Optional[str] = None) -> str:
    if not bundles:
        return 'en'
    if requested and requested in bundles:
        return requested
    # Try system locale variants
    try:
        # locale.getdefaultlocale() deprecated; emulate similar behavior.
        loc_tuple = locale.getlocale()
        loc = None
        if loc_tuple and loc_tuple[0]:
            loc = loc_tuple[0]
            # Windows specific: handle formats like 'Japanese_Japan' -> 'ja'
            if '_' in loc and not '-' in loc:
                # Windows locale format mapping
                windows_locale_map = {
                    'Japanese_Japan': 'ja',
                    'English_United States': 'en',
                    'Chinese_China': 'zh',
                    'Korean_Korea': 'ko',
                    'German_Germany': 'de',
                    'French_France': 'fr',
                    'Spanish_Spain': 'es',
                    'Italian_Italy': 'it',
                    'Portuguese_Brazil': 'pt',
                    'Russian_Russia': 'ru'
                }
                mapped = windows_locale_map.get(loc)
                if mapped:
                    loc = mapped
        if not loc:
            # Fallback: environment LANGUAGE / LC_ALL / LC_MESSAGES / LANG
            import os
            for env_key in ('LC_ALL','LC_MESSAGES','LANGUAGE','LANG'):
                v = os.environ.get(env_key)
                if v:
                    loc = v
                    break
    except Exception:
        loc = None
    if loc:
        loc_norms = {loc.lower(), loc.replace('_', '-').lower()}
        for k in bundles.keys():
            if k.lower() in loc_norms:
                return k
        base = loc.split('_')[0].split('-')[0].lower()
        for k in bundles.keys():
            if k.split('_')[0].split('-')[0].lower() == base:
                return k
    # Prefer English if present
    if 'en' in bundles:
        return 'en'
    return sorted(bundles.keys())[0]


def make_translator(lang: Optional[str], bundles: Dict[str, Dict[str, Any]] | None = None) -> Translator:
    if bundles is None:
        bundles = load_bundles()
    if not lang:
        lang = choose_lang(bundles)
    bundle = bundles.get(lang) or {}

    def _tr(key: str) -> str:
        try:
            return str(bundle.get(key, key))
        except Exception:
            return key
    return _tr


def get_translator(requested: Optional[str] = None) -> Tuple[Translator, str, Dict[str, Dict[str, Any]]]:
    bundles = load_bundles()
    chosen = choose_lang(bundles, requested)
    return make_translator(chosen, bundles), chosen, bundles

def clear_i18n_cache():  # pragma: no cover - used in tests / manual reset
    """Reset internal bundle cache (facilitates deterministic testing)."""
    global _BUNDLE_CACHE
    _BUNDLE_CACHE = None

# --- Small helper to unify repeated pattern of pulling lang from report['_options'] ---
def resolve_requested_lang(report: Dict[str, Any] | None, explicit: Optional[str]) -> Optional[str]:  # pragma: no cover - trivial
    """Return the requested language code, preferring explicit param then report['_options']."""
    if explicit:
        return explicit
    try:
        if report and isinstance(report, dict):
            opts = report.get('_options') or {}
            if isinstance(opts, dict):
                lang = opts.get('lang')
                if isinstance(lang, str) and lang.strip():
                    return lang
    except Exception:
        return explicit
    return explicit


def localize_impact_placeholders(text: str, tr: Translator) -> str:
    """Replace raw impact.symptom.* keys and wrap coexistence marker tokens.

    Supports both legacy inline marker '(wrap coexistence)' and the new
    token form ' impact.extra.wrapCoexist' appended by compute_impact_unified.
    Safe: returns original text on any exception.
    """
    if not text:
        return text
    try:
        def _repl(m: _re.Match[str]) -> str:
            key = m.group(0)
            loc = tr(key)
            return loc if loc and loc != key else key
        new_text = _re.sub(r'impact\.symptom\.[a-zA-Z0-9_]+', _repl, text)
        wrap_loc = tr('impact.extra.wrapCoexist')
        # New token style: space + key appended
        if 'impact.extra.wrapCoexist' in new_text and wrap_loc:
            new_text = new_text.replace('impact.extra.wrapCoexist', wrap_loc)
        # Legacy parenthetical style still supported for older cached outputs
        if wrap_loc and '(wrap coexistence)' in new_text and wrap_loc not in new_text:
            new_text = new_text.replace('(wrap coexistence)', wrap_loc)
        return new_text
    except Exception:
        return text


__all__ = [
    'Translator', 'load_bundles', 'choose_lang', 'make_translator', 'get_translator',
    'localize_impact_placeholders', 'symptom_label', 'clear_i18n_cache'
]

# Backwards compatibility wrapper: delegate to common_impact.symptom_label if present
def symptom_label(code: str, tr: Translator):  # pragma: no cover - thin wrapper
    try:
        from common.common_impact import symptom_label as _ci_symptom_label  # type: ignore
        return _ci_symptom_label(code, tr)
    except Exception:
        # Fallback inline minimal logic (should rarely execute)
        try:
            key = f'impact.symptom.{code}'
            lbl = tr(key)
            return lbl if lbl and lbl != key else code
        except Exception:
            return code
