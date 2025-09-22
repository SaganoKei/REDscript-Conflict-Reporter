"""Common asset discovery & template/CSS loader for GUI & CLI.

Assumptions (per refactor request):
 - All expected files/dirs exist (no defensive fallbacks for missing modules).
 - Template file name: report_template.html (matches existing assets/report_template.html)
 - CSS file name: report.css

Responsibilities:
 - discover_asset_dirs(): ordered list of candidate asset directories
 - load_template_and_css(inline_css: bool) -> (template_or_skeleton:str, used_external_template: bool, css_inline: str|None, chosen_dir: Path|None)
 - ensure_css_copy(dest_html: Path): copy report.css next to dest if not already present.

Output Stability:
 - The HTML placeholder tokens expected by existing code are unchanged ({{TITLE}}, {{HEADER_LABEL}}, {{THEME_CLASS}}, {{BODY}})
 - When no external template is found, returns a minimal skeleton with the same tokens to preserve substitution logic.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Optional

_ASSET_DIR_CACHE: List[Path] | None = None


def discover_asset_dirs(force_reload: bool = False) -> List[Path]:
    """Return ordered candidate asset directories (deduplicated).

    Sources (precedence order):
      1. REDCONFLICT_ASSET_DIRS (pathsep-separated list)
      2. REDCONFLICT_ASSETS (legacy single path)
      3. CWD/assets
      4. Package local assets (module dir, parent)
      5. Frozen (_MEIPASS)/assets (if present)
    """
    global _ASSET_DIR_CACHE
    if _ASSET_DIR_CACHE is not None and not force_reload:
        return _ASSET_DIR_CACHE
    import os, sys
    cands: List[Path] = []
    multi = os.environ.get('REDCONFLICT_ASSET_DIRS')
    if multi:
        for part in multi.split(os.pathsep):
            if part.strip():
                cands.append(Path(part.strip()))
    legacy = os.environ.get('REDCONFLICT_ASSETS')
    if legacy:
        cands.append(Path(legacy))
    cands.append(Path.cwd() / 'assets')
    here = Path(__file__).parent.resolve()
    cands.append(here / 'assets')
    cands.append(here.parent / 'assets')
    if getattr(sys, 'frozen', False):  # PyInstaller one-dir
        base = getattr(sys, '_MEIPASS', '')
        if base:
            cands.append(Path(base) / 'assets')
    seen: set[str] = set()
    uniq: List[Path] = []
    for p in cands:
        try:
            r = p.resolve()
        except Exception:
            r = p
        sp = str(r)
        if sp and sp not in seen:
            seen.add(sp)
            uniq.append(r)
    _ASSET_DIR_CACHE = uniq
    return uniq


_SKELETON = (
    "<!DOCTYPE html><html><head><meta charset='utf-8'>"
    "<title>{{TITLE}}</title><style>body{font-family:Segoe UI,Arial,sans-serif;margin:0;padding:16px;background:#ffffff;color:#000000;}"
    "h1,h2,h3{margin:10px 0;} .dark body{background:#1e1e1e;color:#e6e6e6;}"
    ".dark h1,.dark h2,.dark h3{color:#ffffff;}"
    ".dark a{color:#4fc3f7;} .dark a:visited{color:#ba68c8;}"
    ".dark code{background:#333333;color:#f5f5f5;padding:2px 4px;border-radius:3px;}"
    ".dark pre{background:#2d2d2d;color:#f5f5f5;padding:8px;border-radius:4px;}"
    ".dark .badge{border:1px solid #555555;}"
    ".dark table{border-color:#555555;} .dark td,.dark th{border-color:#555555;color:#e6e6e6;}"
    "</style></head><body class='{{THEME_CLASS}}'><h1>{{HEADER_LABEL}}</h1>{{BODY}}</body></html>"
)


def load_template_and_css(inline_css: bool) -> Tuple[str, bool, Optional[str], Optional[Path]]:
    tpl_text: Optional[str] = None
    css_inline: Optional[str] = None
    chosen: Optional[Path] = None
    for d in discover_asset_dirs():
        # Legacy/GUI name is report_template.html; support both (prefer explicit report_template.html)
        tpl = d / 'report_template.html'
        if not tpl.exists():
            tpl = d / 'template.html'
        if tpl.exists():
            tpl_text = tpl.read_text(encoding='utf-8')
            chosen = d
            css = d / 'report.css'
            if css.exists():
                if inline_css:
                    css_inline = f"<style>\n{css.read_text(encoding='utf-8')}\n</style>"
                # else external reference left for caller to copy
            break
    if not tpl_text:
        # Provide skeleton holding the same placeholders so caller replacement path is identical
        return _SKELETON, False, css_inline, chosen
    if css_inline:
        # More flexible CSS link replacement to handle various formats
        import re
        # Pattern to match various forms of the CSS link
        css_link_pattern = r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']report\.css["\'][^>]*/?\s*>'
        if re.search(css_link_pattern, tpl_text):
            tpl_text = re.sub(css_link_pattern, css_inline, tpl_text)
        else:
            # Fallback: try exact match
            tpl_text = tpl_text.replace('<link rel="stylesheet" href="report.css" />', css_inline)
    return tpl_text, True, css_inline, chosen


def ensure_css_copy(dest_html: Path, source_dir: Optional[Path], overwrite: bool = False) -> None:
    if not source_dir:
        return
    css = source_dir / 'report.css'
    if not css.exists():
        return
    target = dest_html.parent / 'report.css'
    if target.exists() and not overwrite:
        return
    try:
        target.write_bytes(css.read_bytes())
    except Exception:
        pass


__all__ = [
    'discover_asset_dirs', 'load_template_and_css', 'ensure_css_copy', 'build_minimal_html', 'build_minimal_markdown', 'build_minimal_html_body'
]


def build_minimal_html(title: str, header: str, body: str, *, dark: bool = False) -> str:
    """Return a minimal, dependency-free HTML document.

    Centralizes previous duplicated skeleton fallbacks found in other modules so a
    future change (e.g., adding meta viewport / CSP) only touches one location.
    """
    theme_cls = 'dark' if dark else ''
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        "</head>"
        f"<body class='{theme_cls}'><h1>{header}</h1>{body}</body></html>"
    )


def build_minimal_markdown(report: dict) -> str:
    """Return a minimal, deterministic Markdown summary without hardcoded text.

    Language files are assumed to always exist.
    """
    try:
        from common.common_i18n import get_translator
        tr, _, _ = get_translator()

        lines: list[str] = []
        lines.append(f'# {tr("report.header")}\n')
        lines.append(f"- {tr('report.scannedRoot')} `{report.get('scanned_root','')}`\n")
        lines.append(f"- {tr('report.filesScanned')} {report.get('files_scanned','')}\n")
        ac = report.get('annotation_counts', {}) or {}
        lines.append(f"- Annotation counts: replaceMethod={ac.get('replaceMethod',0)}, wrapMethod={ac.get('wrapMethod',0)}, replaceGlobal={ac.get('replaceGlobal',0)}\n")
        conflicts = report.get('conflicts', []) or []
        lines.append(f'\n## {tr("report.conflicts")} (multiple files @replaceMethod the same method)\n')
        if not conflicts:
            lines.append(f'{tr("report.noConflicts")}.\n')
        else:
            for c in sorted(conflicts, key=lambda x: (x.get('class',''), x.get('method',''))):
                cls = c.get('class',''); meth = c.get('method',''); count = c.get('count','')
                mods = ', '.join(sorted(set(c.get('mods') or [])))
                lines.append(f"- {cls}.{meth} (count={count}; mods={mods})\n")
        return '\n'.join(lines)
    except Exception:
        return f'# {tr("report.header")}\n{tr("error.generating")}.\n'


def build_minimal_html_body(report: dict) -> str:
    """Return only the <body> inner HTML for minimal fallback pages.

    Used by write_html fallback to avoid duplicating markup.
    Language files are assumed to always exist.
    """
    try:
        from common.common_i18n import get_translator
        tr, _, _ = get_translator()
        import html as _html
        esc = _html.escape  # type: ignore
    except Exception:
        esc = lambda x: str(x)  # type: ignore
        tr = lambda k: k  # type: ignore

    parts: list[str] = []
    parts.append(f"<div>{tr('report.scannedRoot')} <code>{esc(report.get('scanned_root',''))}</code></div>")
    parts.append(f'<h2>{tr("report.conflicts")}</h2>')
    conflicts = report.get('conflicts', []) or []
    if not conflicts:
        parts.append(f'<p>{tr("report.noConflicts")}.</p>')
    return '\n'.join(parts)
