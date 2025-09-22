"""Small shared utility helpers (error suppression, functional wrappers, etc.).

Currently intentionally tiny to avoid over-abstraction; expand only with clear wins.
"""
from __future__ import annotations
from typing import Type, TypeVar, Callable, Iterable, Any, Optional, Tuple, Union
try:  # optional import (avoid hard failure if module missing in minimal env)
    from common.common_logging import log_line as _log_line
except Exception:  # pragma: no cover
    _log_line = None  # type: ignore

T = TypeVar('T')
E = TypeVar('E', bound=BaseException)


def safe_call(fn: Callable[..., T], *args: Any, default: Optional[T] = None, suppress: Union[Type[E], Tuple[Type[E], ...]] = Exception, on_error: Optional[Callable[[BaseException], None]] = None, **kwargs: Any) -> Optional[T]:
    """Execute fn(*args, **kwargs) swallowing specified exceptions.

    Parameters
    ----------
    fn : callable
        Function to invoke.
    default : value (optional)
        Value returned when an exception is suppressed (default None).
    suppress : Exception type or tuple
        Exceptions to catch (default: Exception, i.e. broad UI-safety usage).
    on_error : callable(exc) (optional)
        If provided, called with the exception object before returning default.

    Returns
    -------
    The function result or the default on error. Never raises for suppressed types.
    """
    try:
        return fn(*args, **kwargs)
    except suppress as exc:  # type: ignore[misc]
        if on_error:
            try:
                on_error(exc)
            except Exception:
                pass
        return default

def ensure_row_visibility(container, build_fn, is_visible_fn=None, relayout_fn=None, log_fn=None):
    """Ensure a lazily-created UI row (frame + children) is visible.

    Parameters
    ----------
    container : widget (e.g., Frame)
        Parent / container whose visibility (winfo_ismapped) we care about.
    build_fn : callable
        Invoked to (re)build missing child widgets if row not visible.
    is_visible_fn : callable -> bool (optional)
        Custom predicate; defaults to container.winfo_ismapped.
    relayout_fn : callable (optional)
        Called after build when available (e.g., to wrap / grid reposition).
    log_fn : callable(str) (optional)
        Logging hook for diagnostics.

    Returns
    -------
    bool : True if row visible (already or after build); False on failure.
    """
    try:
        if container is None:
            return False
        predicate = is_visible_fn or (lambda: bool(container.winfo_ismapped()))
        if predicate():
            return True
        if log_fn:
            try:
                log_message('info', log_fn, 'Row not visible; rebuilding...')  # type: ignore[name-defined]
            except Exception:
                pass
        safe_call(build_fn)
        if relayout_fn:
            safe_call(relayout_fn)
        return bool(predicate())
    except Exception as exc:  # pragma: no cover - defensive
        if log_fn:
            try:
                log_message('warn', log_fn, f"ensure_row_visibility failed: {exc}")  # type: ignore[name-defined]
            except Exception:
                pass
        return False

__all__ = ["safe_call", "ensure_row_visibility"]

def log_message(level: str, sink, msg: str):  # pragma: no cover - thin wrapper
    """Backwards compatibility shim now delegating to common_logging (if available)."""
    try:
        if _log_line:
            # Use provided sink if callable; else fallback internal
            if sink and callable(sink):
                _log_line(level, msg, sink=sink)
            else:
                _log_line(level, msg)
            return
    except Exception:
        pass
    # Fallback to legacy formatting
    try:
        if sink and callable(sink):
            prefix = level.upper().strip()
            sink(f"[{prefix}] {msg}" if prefix else msg)
    except Exception:
        pass

__all__.append("log_message")

# --- Impact / report helpers ---
def method_has_wrap(report: dict, cls: str, method: str) -> bool:
    """Return True if the given class.method appears in wrap or replace+wrap coexistence lists.

    Parameters
    ----------
    report : dict
        Parsed report structure containing optional 'wrap_coexistence' and
        'replace_wrap_coexistence' arrays.
    cls : str
        Class name.
    method : str
        Method name.

    Notes
    -----
    The report builder previously duplicated similar inline scans; centralizing
    reduces risk of divergence between HTML and Markdown renderers.
    """
    try:
        for arr_key in ("wrap_coexistence", "replace_wrap_coexistence"):
            items = report.get(arr_key) or []
            for item in items:
                if item.get("class") == cls and item.get("method") == method:
                    return True
        return False
    except Exception:
        return False

__all__.append("method_has_wrap")

# --- Anchor helper (moved from report_builders for shared stability) ---
def make_conflict_anchor(idx: int | None, cls: str, meth: str) -> str:
    """Return legacy anchor id format used in existing HTML snapshots.

    Format:
      base = (Class + '-' + Method).lower() with spaces removed, invalid chars stripped (only a-z0-9-_.)
      if idx is not None: conf-<idx>-<base>
      else: conf-<base>
    """
    try:
        base = ((cls or '') + '-' + (meth or '')).lower().replace(' ', '-')
        base = ''.join(ch for ch in base if ch.isalnum() or ch in ('-','_','.'))
        return f"conf-{idx}-{base}" if idx is not None else f"conf-{base}"
    except Exception:
        return f"conf-{idx or 0}-unknown"

__all__.append("make_conflict_anchor")
