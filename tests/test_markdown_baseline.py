from builders.report_builders import build_markdown

SYNTH_WITH_WRAP = {
    'scanned_root': 'X:/game/mods',
    'files_scanned': 2,
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

SYNTH_NO_WRAP = {
    'scanned_root': 'X:/game/mods',
    'files_scanned': 1,
    'annotation_counts': {'replaceMethod': 1, 'wrapMethod': 0, 'replaceGlobal': 0},
    'conflicts': [
        {
            'class': 'Baz', 'method': 'Qux', 'mods': ['A'], 'count': 1,
            'occurrences': [
                {'mod':'A','relpath':'a.reds','line':3,'func_sig':'func Qux() -> Void'},
            ]
        }
    ],
    'wrap_coexistence': [],
    'replace_wrap_coexistence': [],
    'entries': [
        {'annotation':'replaceMethod','class':'Baz','method':'Qux','mod':'A','relpath':'a.reds','line':3,'func_sig':'func Qux() -> Void'},
    ],
    '_options': {'include_wrap_coexistence': True}
}


def test_markdown_with_wrap_has_baseline_line():
    md = build_markdown(SYNTH_WITH_WRAP, tr=lambda k: k, include_reference=False)
    assert 'Baseline:' in md, md

def test_markdown_without_wrap_no_baseline_line():
    md = build_markdown(SYNTH_NO_WRAP, tr=lambda k: k, include_reference=False)
    assert 'Baseline:' not in md, md
