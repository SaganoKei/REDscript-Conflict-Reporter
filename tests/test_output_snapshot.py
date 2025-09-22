import json, hashlib, re
from pathlib import Path
from builders.report_builders import build_markdown, build_full_html_gui

# Minimal synthetic report representing key structures
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

SNAP_DIR = Path(__file__).parent / 'snapshots'
SNAP_DIR.mkdir(exist_ok=True)
MD_SNAPSHOT = SNAP_DIR / 'synthetic_report.md'
HTML_SNAPSHOT = SNAP_DIR / 'synthetic_report.html'

NORMALIZE_REGEXES = [
    (re.compile(r'file:///.+?/(a|b|c)\.reds'), 'file:///ABS_PATH/\\1.reds'),
]

def _normalize(text: str) -> str:
    for pat, repl in NORMALIZE_REGEXES:
        text = pat.sub(repl, text)
    return text.strip() + '\n'

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def test_markdown_snapshot():
    out = build_markdown(SYNTH_REPORT, tr=lambda k: k, conflicts_only=False, include_reference=True)
    out = _normalize(out)
    if not MD_SNAPSHOT.exists():
        MD_SNAPSHOT.write_text(out, encoding='utf-8')
        # First run establishes snapshot  Etreat as pass.
        return
    snap = _normalize(MD_SNAPSHOT.read_text(encoding='utf-8'))
    assert out == snap, f"Markdown snapshot diverged\nNEW:\n{out}\n---\nOLD:\n{snap}"


def test_html_snapshot():
    html, _used = build_full_html_gui(SYNTH_REPORT, tr=lambda k: k, dark=False, conflicts_only=False, include_reference=True, inline_css=True, lang=None)
    html = _normalize(html)
    if not HTML_SNAPSHOT.exists():
        HTML_SNAPSHOT.write_text(html, encoding='utf-8')
        return
    snap = _normalize(HTML_SNAPSHOT.read_text(encoding='utf-8'))
    assert html == snap, 'HTML snapshot diverged (structure or labels changed)'

