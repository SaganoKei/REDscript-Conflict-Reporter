import types
from builders.report_builders import build_full_html_gui
from gui_conflict_report import App

SAMPLE_REPORT = {
    'scanned_root': 'X:/game/mods',
    'files_scanned': 3,
    'annotation_counts': {'replaceMethod': 2, 'wrapMethod': 1, 'replaceGlobal': 0},
    'conflicts': [
        {
            'class': 'Foo', 'method': 'Bar', 'mods': ['A','B'], 'count': 2,
            'occurrences': [
                {'mod':'A','relpath':'a.reds','line':1,'func_sig':'func Bar() -> Void'},
                {'mod':'B','relpath':'b.reds','line':2,'func_sig':'func Bar() -> Void'},
            ]
        }
    ],
    'wrap_coexistence': [
        {'class':'Foo','method':'Bar','mods':['A','B'],'wrap_count':2,'occurrences':[{'mod':'A','relpath':'a.reds','line':1},{'mod':'B','relpath':'b.reds','line':2}]}
    ],
    'replace_wrap_coexistence': [],
    'entries': [
        {'annotation':'replaceMethod','class':'Foo','method':'Bar','mod':'A','relpath':'a.reds','line':1,'func_sig':'func Bar() -> Void'},
        {'annotation':'replaceMethod','class':'Foo','method':'Bar','mod':'B','relpath':'b.reds','line':2,'func_sig':'func Bar() -> Void'},
    ],
    '_options': {'include_wrap_coexistence': True}
}


def test_gui_preview_impact_matches_export(monkeypatch):
    # Build export HTML impact severity for comparison
    # (We only need the computed severity + message for the conflict detail block)
    html, _used = build_full_html_gui(SAMPLE_REPORT, tr=lambda k: k, dark=False, conflicts_only=False, include_reference=True, inline_css=True, lang=None)
    assert 'impact.label' in html  # sanity

    # Instantiate app but avoid full Tk mainloop usage; call impact accessor directly
    app = App()
    # Inject report (attribute is initialized in App __init__, mypy/pylance may treat as Optional)
    app._last_report = SAMPLE_REPORT  # type: ignore[attr-defined]
    app.var_include_wrap.set(True)    # ensure wrap sections enabled

    impact = app._assess_conflict_impact('Foo','Bar',['A','B'], SAMPLE_REPORT['conflicts'][0]['occurrences'])

    # Export builder uses same compute_impact_unified; verify severity token appears consistently
    sev = impact.get('severity')
    assert sev is not None
    # Severity badge class in HTML uses lowercase
    assert f"sev-{sev.lower()}" in html

    # Baseline line (if any) should not contradict preview severity
    # (i.e., preview severity should match exported main severity not baseline)
    if 'impact.label.baseline' in html:
        # extract first occurrence severity class line (main impact)
        import re
        m = re.search(r"<div class='impact'><b>impact.label</b> <span class='badge sev-([a-z]+)'>", html)
        assert m, 'Main impact line not found'
        exported_main = m.group(1)
        assert exported_main == sev.lower(), f"Preview severity {sev.lower()} != exported {exported_main}"

    # Clean up Tk root to avoid resource leaks in repeated test runs
    try:
        app.destroy()
    except Exception:
        pass
