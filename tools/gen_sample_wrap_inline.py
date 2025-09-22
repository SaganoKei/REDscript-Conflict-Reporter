"""Generate sample HTML reports showing inline wrapMethod coexistence list.

This helps verify how the inline wrap list appears when:
 1) Global wrap coexistence section is ENABLED
 2) Global wrap coexistence section is DISABLED (inline list still appears)

Outputs are written under tools/sample_outputs/
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json

import sys
ROOT = Path(__file__).resolve().parents[1]  # REDscript-Conflict-Reporter/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from builders.report_builders import build_full_html_gui


def _synthetic_report() -> dict:
    # Minimal synthetic report structure including wrap coexistence
    return {
        'root': 'X:/game/mods',
        'entries': [
            # replaceMethod occurrences (two mods conflict)
            {
                'annotation': 'replaceMethod', 'class': 'PlayerPuppet', 'method': 'OnUpdate',
                'relpath': 'a.reds', 'line': 10, 'mod': 'ModA', 'func_sig': 'func OnUpdate(delta: Float) -> Void'
            },
            {
                'annotation': 'replaceMethod', 'class': 'PlayerPuppet', 'method': 'OnUpdate',
                'relpath': 'b.reds', 'line': 20, 'mod': 'ModB', 'func_sig': 'func OnUpdate(delta: Float) -> Void'
            },
            # Single replaceMethod (no conflict) to show normal block
            {
                'annotation': 'replaceMethod', 'class': 'HudManager', 'method': 'RefreshUI',
                'relpath': 'c.reds', 'line': 5, 'mod': 'ModC', 'func_sig': 'func RefreshUI() -> Void'
            },
        ],
        'wrap_coexistence': [
            {
                'class': 'PlayerPuppet', 'method': 'OnUpdate',
                'mods': ['ModA', 'ModB'],
                'wrap_count': 2,
                'occurrences': [
                    {'mod': 'ModA', 'relpath': 'a.reds', 'line': 10},
                    {'mod': 'ModB', 'relpath': 'b.reds', 'line': 20},
                ]
            }
        ],
        # This mirrors how conflicts list is pre-grouped in the main app.
        'conflicts': [
            {
                'class': 'PlayerPuppet', 'method': 'OnUpdate', 'mods': ['ModA', 'ModB'], 'count': 2,
                'occurrences': [
                    {'mod': 'ModA', 'relpath': 'a.reds', 'line': 10, 'func_sig': 'func OnUpdate(delta: Float) -> Void'},
                    {'mod': 'ModB', 'relpath': 'b.reds', 'line': 20, 'func_sig': 'func OnUpdate(delta: Float) -> Void'},
                ]
            },
            {
                'class': 'HudManager', 'method': 'RefreshUI', 'mods': ['ModC'], 'count': 1,
                'occurrences': [
                    {'mod': 'ModC', 'relpath': 'c.reds', 'line': 5, 'func_sig': 'func RefreshUI() -> Void'},
                ]
            },
        ],
        '_options': {
            'include_wrap_coexistence': True,
        }
    }


def main():
    report = _synthetic_report()
    out_dir = Path(__file__).parent / 'sample_outputs'
    out_dir.mkdir(parents=True, exist_ok=True)

    # Case 1: wrap coexistence section enabled
    html_enabled, _ = build_full_html_gui(report, tr=lambda k: k, dark=False, conflicts_only=False, include_reference=True, inline_css=True, lang=None)
    (out_dir / 'inline_wrap_enabled.html').write_text(html_enabled, encoding='utf-8')

    # Case 2: wrap coexistence section disabled -> inline list should still appear
    report['_options']['include_wrap_coexistence'] = False
    html_disabled, _ = build_full_html_gui(report, tr=lambda k: k, dark=False, conflicts_only=False, include_reference=True, inline_css=True, lang=None)
    (out_dir / 'inline_wrap_disabled.html').write_text(html_disabled, encoding='utf-8')

    meta = {
        'generated': datetime.utcnow().isoformat() + 'Z',
        'files': ['inline_wrap_enabled.html', 'inline_wrap_disabled.html'],
        'note': 'Both files should show an inline wrap list under PlayerPuppet.OnUpdate.'
    }
    (out_dir / 'meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print("Generated sample HTML:")
    for f in meta['files']:
        print(f" - {f}")


if __name__ == '__main__':
    main()
