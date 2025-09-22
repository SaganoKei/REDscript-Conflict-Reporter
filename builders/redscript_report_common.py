"""
Shared output routines for REDscript conflict reports (HTML/Markdown).

This module is GUI-agnostic and English-only by design. It provides small,
portable writers used by both CLI and GUI, so that saved files are identical
between the two entry points when localization is disabled on the GUI side.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
from typing import Callable, Any
try:
    from common.common_assets import (
        load_template_and_css as _ca_load_template_and_css,
        build_minimal_html as _build_min_html,
        build_minimal_markdown as _build_min_md,
        build_minimal_html_body as _build_min_body,
    )
except Exception:  # pragma: no cover
    _ca_load_template_and_css = None  # type: ignore
    _build_min_md = None  # type: ignore

FALLBACK_HTML_WARN = "Falling back to minimal HTML skeleton (canonical builder unavailable)"

try:  # Prefer canonical GUI-compatible builders; degrade gracefully.
    from builders.report_builders import (
        build_markdown as _build_markdown,
        build_full_html_gui_and_copy as _build_full_html_gui,
    )  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _build_markdown = None  # type: ignore
    _build_full_html_gui = None  # type: ignore

try:  # optional shared i18n
    from common.common_i18n import make_translator as _ci_make_translator, resolve_requested_lang as _resolve_lang
except Exception:
    _ci_make_translator = None  # type: ignore
    _resolve_lang = None  # type: ignore

try:  # logging helper (optional)
    from common.common_util import log_message as _log_message
except Exception:  # pragma: no cover
    _log_message = None  # type: ignore


def write_markdown(report: dict, out_md: Path, conflicts_only: bool = False, include_reference: bool = False, lang: str | None = None) -> None:
    """Write Markdown via shared builder only (translator from common_i18n).

    Simplified: rely exclusively on _build_markdown + common_i18n.make_translator.
    If canonical builder missing, emit minimal English fallback (no ad-hoc JSON loading).
    """
    # Unified language resolution (explicit arg overrides report['_options']).
    if _resolve_lang:
        lang = _resolve_lang(report, lang)
    else:
        if lang is None:
            try:
                lang = (report.get('_options') or {}).get('lang')
            except Exception:
                lang = None
    if _build_markdown is not None:
        tr_fn = None
        if _ci_make_translator:
            try:
                tr_fn = _ci_make_translator(lang)  # type: ignore[arg-type]
            except Exception:
                tr_fn = None
        text = _build_markdown(report, tr_fn, conflicts_only=conflicts_only, include_reference=include_reference)  # type: ignore[misc]
        out_md.write_text(text, encoding='utf-8')
        return
    # Canonical builder unavailable → minimal fixed English summary.
    if _build_min_md:
        out_md.write_text(_build_min_md(report), encoding='utf-8')
        return
    try:
        out_md.write_text('# REDscript Conflict Report\nMinimal builder missing.\n', encoding='utf-8')
    except Exception:
        pass


def write_html(report: dict, out_html: Path, conflicts_only: bool = False, include_reference: bool = False, dark: bool = False, lang: str | None = None, log_fn: Callable[[str], None] | None = None) -> None:
    """Write HTML report: canonical builder or minimal skeleton fallback.

    Reduced to two layers to simplify maintenance:
      1) Canonical GUI-compatible full HTML (shared template/CSS path)
      2) Minimal skeleton (only header + conflicts heading)

    Parameters
    ----------
    report : dict
        Conflict analysis structure.
    out_html : Path
        Destination file path.
    conflicts_only / include_reference / dark / lang : assorted output flags.
    log_fn : callable(str) optional
        If provided, invoked with a WARN message when falling back to the
        minimal skeleton (observability for missing optional deps).
    """
    if _build_full_html_gui is not None:
        try:
            if _resolve_lang:
                lang = _resolve_lang(report, lang)
            else:
                if lang is None:
                    try:
                        lang = (report.get('_options') or {}).get('lang')
                    except Exception:
                        lang = None
            html = _build_full_html_gui(report, out_html, None, dark=dark, conflicts_only=conflicts_only, include_reference=include_reference, lang=lang)  # type: ignore[misc]
            if isinstance(html, tuple):  # backwards compatibility guard
                html = html[0]
            out_html.write_text(html, encoding='utf-8')
            return
        except Exception:
            if log_fn:
                try:
                    if _log_message:
                        _log_message('warn', log_fn, FALLBACK_HTML_WARN)
                    else:
                        log_fn(f"[WARN] {FALLBACK_HTML_WARN}")
                except Exception:
                    pass
    # Use shared template loader skeleton so placeholder semantics consistent
    body_conflicts_html = _build_min_body(report) if '_build_min_body' in globals() and _build_min_body else ''
    skeleton_html = None
    if _ca_load_template_and_css:
        try:
            tpl, _used_tpl, _css_inline, _dir = _ca_load_template_and_css(inline_css=True)
            header = "REDscript Conflict Report"
            theme_class = 'dark' if dark else ''
            body_joined = body_conflicts_html
            skeleton_html = (tpl
                              .replace('{{TITLE}}', header)
                              .replace('{{HEADER_LABEL}}', header)
                              .replace('{{THEME_CLASS}}', theme_class)
                              .replace('{{BODY}}', body_joined))
        except Exception:
            skeleton_html = None
    if skeleton_html is None:
        skeleton_html = _build_min_html("REDscript Conflict Report", "REDscript Conflict Report", body_conflicts_html, dark=dark)
    if log_fn:
        try:
            if _log_message:
                _log_message('warn', log_fn, FALLBACK_HTML_WARN)
            else:
                log_fn(f"[WARN] {FALLBACK_HTML_WARN}")
        except Exception:
            pass
    out_html.write_text(skeleton_html, encoding='utf-8')
