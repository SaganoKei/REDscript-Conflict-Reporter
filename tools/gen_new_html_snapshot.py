from pathlib import Path
from builders.report_builders import build_full_html_gui

"""Generate a synthetic HTML snapshot (developer utility).

Moved from repository root to tools/ for consistency with other dev scripts.
Outputs to tests/snapshots/synthetic_report.generated.html relative to project root.
Run with:
    python tools/gen_new_html_snapshot.py
"""

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


def main():
    html, _used = build_full_html_gui(
        SYNTH_REPORT,
        tr=lambda k: k,
        dark=False,
        conflicts_only=False,
        include_reference=True,
        inline_css=True,
        lang=None,
    )
    root = Path(__file__).resolve().parent.parent
    snap_path = root / 'tests' / 'snapshots' / 'synthetic_report.generated.html'
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(html, encoding='utf-8')
    print('Wrote', snap_path)


if __name__ == '__main__':
    main()
