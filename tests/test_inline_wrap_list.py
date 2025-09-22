from builders.report_builders import build_full_html_cli, build_markdown

def sample_report(include_wrap_option: bool):
    return {
        'scanned_root': 'R:/root',
        'files_scanned': 3,
        '_options': {
            'include_wrap_coexistence': include_wrap_option,
            'disable_file_links': True,
        },
        'annotation_counts': {'replaceMethod':2,'wrapMethod':2,'replaceGlobal':0},
        'conflicts': [
            {
                'class': 'Foo',
                'method': 'Bar',
                'count': 2,
                'mods': ['ModA','ModB'],
                'occurrences': [
                    {'annotation':'replaceMethod','class':'Foo','method':'Bar','mod':'ModA','relpath':'a.reds','line':10,'func_sig':'func Bar() -> Void'},
                    {'annotation':'replaceMethod','class':'Foo','method':'Bar','mod':'ModB','relpath':'b.reds','line':20,'func_sig':'func Bar() -> Void'},
                ],
            }
        ],
        'wrap_coexistence': [
            {
                'class': 'Foo',
                'method': 'Bar',
                'wrap_count': 2,
                'mods': ['ModA','ModC'],  # note ModC not in replace list
                'occurrences': [
                    {'annotation':'wrapMethod','class':'Foo','method':'Bar','mod':'ModA','relpath':'wa.reds','line':30},
                    {'annotation':'wrapMethod','class':'Foo','method':'Bar','mod':'ModC','relpath':'wc.reds','line':40},
                ],
            }
        ],
        'replace_wrap_coexistence': [],
        'entries': [],
    }


def test_html_inline_wrap_list_present():
    report = sample_report(include_wrap_option=False)
    html = build_full_html_cli(report)
    assert 'wrap-inline' in html, 'Expected inline wrap section'
    assert 'wa.reds' in html and 'wc.reds' in html


def test_markdown_inline_wrap_list_present():
    report = sample_report(include_wrap_option=False)
    md = build_markdown(report)
    assert '@wrapMethod (coexisting)' in md
    assert 'wa.reds:30' in md and 'wc.reds:40' in md
