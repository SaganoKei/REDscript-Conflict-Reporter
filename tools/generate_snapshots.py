"""Utility script to (re)generate synthetic snapshot artifacts for tests.

Usage:
  python -m tools.generate_snapshots

Writes updated HTML & Markdown snapshot fixtures under tests/snapshots/.
This is developer convenience; CI should rely on committed snapshots.
"""
from pathlib import Path
from builders.report_builders import build_full_html_gui, build_markdown

SYNTH_REPORT = {
    'scanned_root': 'X:/game/mods',
    'files_scanned': 5,
    'annotation_counts': {'replaceMethod': 3, 'wrapMethod': 1, 'replaceGlobal': 0},
    'conflicts': [
        {
            'class': 'PlayerPuppet',
            'method': 'OnUpdate',
            'mods': ['ModA', 'ModB'],
            'count': 2,
            'occurrences': [
                {'mod': 'ModA', 'relpath': 'a.reds', 'line': 10, 'func_sig': 'func OnUpdate(delta: Float) -> Void'},
                {'mod': 'ModB', 'relpath': 'b.reds', 'line': 20, 'func_sig': 'func OnUpdate(delta: Float) -> Void'},
            ],
        },
        {
            'class': 'HudManager',
            'method': 'RefreshUI',
            'mods': ['ModC'],
            'count': 1,
            'occurrences': [
                {'mod': 'ModC', 'relpath': 'c.reds', 'line': 5, 'func_sig': 'func RefreshUI() -> Void'},
            ],
        },
    ],
    'wrap_coexistence': [
        {
            'class': 'PlayerPuppet',
            'method': 'OnUpdate',
            'mods': ['ModA', 'ModB'],
            'wrap_count': 2,
            'occurrences': [
                {'mod': 'ModA', 'relpath': 'a.reds', 'line': 10},
                {'mod': 'ModB', 'relpath': 'b.reds', 'line': 20},
            ],
        }
    ],
    'replace_wrap_coexistence': [],
    'entries': [
        {'annotation': 'replaceMethod', 'class': 'PlayerPuppet', 'method': 'OnUpdate', 'mod': 'ModA', 'relpath': 'a.reds', 'line': 10, 'func_sig': 'func OnUpdate(delta: Float) -> Void'},
        {'annotation': 'replaceMethod', 'class': 'PlayerPuppet', 'method': 'OnUpdate', 'mod': 'ModB', 'relpath': 'b.reds', 'line': 20, 'func_sig': 'func OnUpdate(delta: Float) -> Void'},
        {'annotation': 'replaceMethod', 'class': 'HudManager', 'method': 'RefreshUI', 'mod': 'ModC', 'relpath': 'c.reds', 'line': 5, 'func_sig': 'func RefreshUI() -> Void'},
    ],
    '_options': {'include_wrap_coexistence': True},
}

SNAP_DIR = Path(__file__).resolve().parent.parent / 'tests' / 'snapshots'
SNAP_DIR.mkdir(exist_ok=True)


def regen_html():
    html, _used = build_full_html_gui(SYNTH_REPORT, tr=lambda k: k, dark=False, conflicts_only=False, include_reference=True, inline_css=True, lang=None)
    (SNAP_DIR / 'synthetic_report.html').write_text(html, encoding='utf-8')
    print('Updated HTML snapshot.')


def regen_markdown():
    md = build_markdown(SYNTH_REPORT, tr=lambda k: k, conflicts_only=False, include_reference=True)
    (SNAP_DIR / 'synthetic_report.md').write_text(md, encoding='utf-8')
    print('Updated Markdown snapshot.')


def main():
    regen_html()
    regen_markdown()
    print('All snapshots regenerated.')

if __name__ == '__main__':
    main()
