import re
from builders.report_builders import build_full_html_cli


def _make_sample_report(include_wrap_option: bool):
    # Minimal synthetic report containing one conflict with wrap coexistence entries
    return {
        'scanned_root': 'C:/dummy',
        'files_scanned': 2,
        '_options': {
            'include_wrap_coexistence': include_wrap_option,
            'disable_file_links': True,
        },
        'conflicts': [
            {
                'class': 'Foo',
                'method': 'Bar',
                'count': 2,
                'mods': ['ModA', 'ModB'],
                'occurrences': [
                    {'mod': 'ModA', 'relpath': 'a.reds', 'line': 10, 'func_sig': 'public func Bar() -> Void'},
                    {'mod': 'ModB', 'relpath': 'b.reds', 'line': 20, 'func_sig': 'public func Bar() -> Void'},
                ],
            }
        ],
        # To trigger per-method wrap detection we need wrap_coexistence entry referencing same class/method
        'wrap_coexistence': [
            {
                'class': 'Foo',
                'method': 'Bar',
                'wrap_count': 2,
                'mods': ['ModA', 'ModB'],
                'occurrences': [
                    {'mod': 'ModA', 'relpath': 'a.reds', 'line': 10},
                    {'mod': 'ModB', 'relpath': 'b.reds', 'line': 20},
                ],
            }
        ],
        'replace_wrap_coexistence': [],
    }


def test_tooltip_present_when_wrap_hidden():
    report = _make_sample_report(include_wrap_option=False)
    html = build_full_html_cli(report, tr=None, dark=False, conflicts_only=False, include_reference=False)
    # Severity badge for Foo.Bar should contain title attribute with either localized or fallback text
    # Accept both English default or localized key resolution result
    assert "sev-" in html  # sanity
    # Extract the conflict detail line
    # Accept either 'Impact' or 'Impact (Overall)' label variants
    pattern = r"<div class='impact'><b>Impact(?: \(Overall\))?</b> <span class='badge sev-[a-z]+[^>]*title='([^']+)'"
    m = re.search(pattern, html)
    assert m, f"Expected severity badge with title attribute, got snippet: {html[:400]}"
    assert 'wrapMethod coexistence' in m.group(1)


def test_tooltip_absent_when_wrap_shown():
    report = _make_sample_report(include_wrap_option=True)
    html = build_full_html_cli(report, tr=None, dark=False, conflicts_only=False, include_reference=False)
    # Should NOT contain hidden tooltip because wrap section is shown
    assert "sev-" in html
    assert "impact.wrapHiddenTooltip" not in html  # raw key must not leak
    # Ensure no title="...coexistence exists (hidden)" on the main impact badge when wrap visible
    assert "coexistence exists (hidden)" not in html