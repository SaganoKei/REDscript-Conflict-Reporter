"""Compare structural parity between GUI body builder and CLI full HTML output.

Usage (run from repo root):
  python -m tools.compare_gui_cli_html

This script builds a representative sample report (with conflicts, wrap coexistence
and reference entries), then:
  1. Builds GUI-style body via build_html_body_gui (injecting legend lines & impact)
  2. Builds CLI full HTML via build_full_html_gui (with inline CSS) then extracts <body>...</body>
  3. Normalizes whitespace & strips style/script/link tags for structural comparison
  4. Prints a unified diff if differences exist, else prints PARITY OK

Exit code: 0 on match / 1 on difference / 2 on unexpected error.
"""
from __future__ import annotations

import re
import sys
import difflib
from pathlib import Path

try:
    from builders.report_builders import (
        build_html_body_gui,
        build_full_html_gui,
        compute_impact_unified,
        _inject_legend_lines_if_missing as _inject_legend,
        _default_en_translator as _tr_en,
    )  # type: ignore
    from common.common_util import make_conflict_anchor
except Exception as e:  # pragma: no cover
    # Fallback: adjust sys.path so running via `python path/to/script.py` from repo root works
    try:
        _here = Path(__file__).resolve()
        _repo_root = _here.parent.parent  # tools/ -> repo root
        if str(_repo_root) not in sys.path:
            sys.path.insert(0, str(_repo_root))
        from builders.report_builders import (  # type: ignore
            build_html_body_gui,
            build_full_html_gui,
            compute_impact_unified,
            _inject_legend_lines_if_missing as _inject_legend,
            _default_en_translator as _tr_en,
        )
        from common.common_util import make_conflict_anchor
    except Exception as e2:
        print(f"[ERROR] failed to import builders (after path fix): {e2}")
        sys.exit(2)


def _sample_report() -> dict:
    return {
        'scanned_root': 'C:/fake/root',
        'files_scanned': 12,
        'annotation_counts': {'replaceMethod': 4, 'wrapMethod': 3, 'replaceGlobal': 1},
        'conflicts': [
            {
                'class': 'PlayerSystem',
                'method': 'GiveItem',
                'mods': ['ModA', 'ModB', 'ModC'],
                'count': 3,
                'occurrences': [
                    {'mod': 'ModA', 'relpath': 'a/redscript/file1.reds', 'line': 12, 'func_sig': 'public func GiveItem(a: Int32) -> Void'},
                    {'mod': 'ModB', 'relpath': 'b/redscript/file2.reds', 'line': 34, 'func_sig': 'public func GiveItem(a: Int32) -> Void'},
                    {'mod': 'ModC', 'relpath': 'c/redscript/file3.reds', 'line': 56, 'func_sig': 'public func GiveItem(a: Int32) -> Void'},
                ],
            },
            {
                'class': 'VehicleSystem',
                'method': 'SpawnCar',
                'mods': ['ModX', 'ModY'],
                'count': 2,
                'occurrences': [
                    {'mod': 'ModX', 'relpath': 'x/redscript/filex.reds', 'line': 90, 'func_sig': 'public func SpawnCar(model: String) -> Vehicle'},
                    {'mod': 'ModY', 'relpath': 'y/redscript/filey.reds', 'line': 120, 'func_sig': 'public func SpawnCar(model: String) -> Vehicle'},
                ],
            },
        ],
        'wrap_coexistence': [
            {
                'class': 'UIManager',
                'method': 'Refresh',
                'mods': ['ModW', 'ModZ'],
                'wrap_count': 2,
                'occurrences': [
                    {'mod': 'ModW', 'relpath': 'w/redscript/filew.reds', 'line': 77},
                    {'mod': 'ModZ', 'relpath': 'z/redscript/filez.reds', 'line': 88},
                ],
            }
        ],
        'replace_wrap_coexistence': [],
        'entries': [
            {
                'class': 'PlayerSystem',
                'method': 'GiveItem',
                'annotation': 'replaceMethod',
                'mod': 'ModA',
                'relpath': 'a/redscript/file1.reds',
                'line': 12,
                'func_sig': 'public func GiveItem(a: Int32) -> Void',
            },
            {
                'class': 'VehicleSystem',
                'method': 'SpawnCar',
                'annotation': 'replaceMethod',
                'mod': 'ModX',
                'relpath': 'x/redscript/filex.reds',
                'line': 90,
                'func_sig': 'public func SpawnCar(model: String) -> Vehicle',
            },
        ],
        '_options': {'include_wrap_coexistence': True},
    }


def _normalize(html: str) -> list[str]:
    # Extract body content only
    m = re.search(r'<body[^>]*>(.*)</body>', html, re.IGNORECASE | re.DOTALL)
    if m:
        html = m.group(1)
    # Drop style/link/script blocks
    html = re.sub(r'<(style|script)[^>]*>.*?</\1>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<link[^>]+>', '', html, flags=re.IGNORECASE)
    # Remove known non-content wrappers (toolbar, container) for parity focus
    # Remove toolbar block (non-greedy until closing div of toolbar); handle nested simple tags
    html = re.sub(r'<div class="toolbar">.*?</div>\s*', '', html, flags=re.DOTALL|re.IGNORECASE)
    # In case pieces of toolbar (like spacer div or buttons) remained due to earlier splitting, remove standalone occurrences
    html = re.sub(r'<div class="sp"></div>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<button class="btn"[^>]*>.*?</button>', '', html, flags=re.IGNORECASE)
    # Remove outer container wrappers that strictly wrap BODY substitution
    html = re.sub(r'<div class="container">', '', html, flags=re.IGNORECASE)
    # Drop container closing div if it encloses entire content (leave internal structure untouched)
    html = re.sub(r'^\s*</div>\s*', '', html, flags=re.IGNORECASE)  # stray starting closing div
    html = re.sub(r'</div>\s*(</body>|$)', r'\1', html, flags=re.IGNORECASE)
    # Remove any orphan lone </div> left after stripping container open tag at boundaries
    html = re.sub(r'(?:^|\n)</div>\s*$', '', html, flags=re.IGNORECASE)
    # Collapse whitespace between tags
    html = re.sub(r'>\s+<', '><', html)
    # Trim
    html = html.strip()
    # Final pass: if a single trailing </div> remains after all content (likely container), remove it
    html = re.sub(r'(</ul>)\s*</div>\s*$', r'\1', html, flags=re.IGNORECASE)
    # Split deterministic by '><' boundaries for structural diff
    tokens = re.split(r'(?=<)|(?<=>)', html)
    lines = [t for t in (x.strip() for x in tokens) if t]
    return lines


def main() -> int:
    rep = _sample_report()
    # Prepare GUI body (simulate injection steps)
    try:
        _inject_legend(rep, _tr_en)  # ensure legend lines
    except Exception:
        pass
    wrap_flag = True
    impact_cb = lambda cls, meth, mods, entries: compute_impact_unified(cls, meth, mods, entries, wrap_coexist=bool(rep.get('wrap_coexistence')))
    body_gui = build_html_body_gui(rep, _tr_en, conflicts_only=False, include_reference=True,
                                   include_wrap=wrap_flag, disable_file_links=False,
                                   impact_fn=impact_cb, anchor_fn=make_conflict_anchor)
    full_cli, _ = build_full_html_gui(rep, dark=False, conflicts_only=False, include_reference=True, inline_css=True, lang='en')

    norm_gui = _normalize(f"<body>{body_gui}</body>")
    norm_cli = _normalize(full_cli)

    if norm_gui == norm_cli:
        print("[PARITY] GUI body and CLI output structurally match")
        return 0

    # Produce unified diff
    diff = list(difflib.unified_diff(norm_gui, norm_cli, fromfile='GUI_BODY', tofile='CLI_FULL', lineterm=''))
    print(f"[DIFF] Structural differences detected: {len(diff)} diff lines")
    for line in diff[:400]:  # safety cap
        print(line)
    if len(diff) > 400:
        print("[DIFF] Output truncated...")
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
