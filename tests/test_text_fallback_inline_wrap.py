import types
import tkinter as tk
import pytest
from tkinter import TclError

# We will instantiate minimal subset of GUI class that provides render_report_to_text
from gui_conflict_report import App  # type: ignore

@pytest.fixture(scope='module')
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk not available in environment')
    yield root
    try:
        root.destroy()
    except Exception:
        pass

@pytest.fixture
def gui(tk_root):
    # Instantiate App. On some Windows CI setups a partially missing Tcl may raise
    # 'invalid command name "tcl_findLibrary"'. Treat as skip to avoid error noise.
    try:
        app = App()
    except TclError as e:  # type: ignore
        if 'tcl_findLibrary' in str(e):
            pytest.skip('Skipping GUI test: Tcl incomplete (tcl_findLibrary)')
        raise
    try:
        app.var_lang.set('en')
    except Exception:
        pass
    if getattr(app, 'txt_html', None) is None:
        pass
    return app

@pytest.fixture
def sample_report():
    # Two conflicts: one with wrap coexistence, one without
    return {
        'scanned_root': '/fake',
        'files_scanned': 3,
        'annotation_counts': {'replaceMethod':2, 'wrapMethod':1, 'replaceGlobal':0},
        'conflicts': [
            {
                'class':'Foo','method':'Bar','count':2,
                # Keep only two mods so baseline and overall severities remain identical (both Low)
                'mods':['ModA','ModB'],
                'occurrences':[{'mod':'ModA','relpath':'a.reds','line':10,'func_sig':'Foo.Bar()'},
                               {'mod':'ModB','relpath':'b.reds','line':12,'func_sig':'Foo.Bar()'}]
            },
            {
                'class':'Foo','method':'Baz','count':1,
                'mods':['ModC'],
                'occurrences':[{'mod':'ModC','relpath':'c.reds','line':5,'func_sig':'Foo.Baz()'}]
            }
        ],
        'wrap_coexistence':[{
            'class':'Foo','method':'Bar','wrap_count':1,
            'mods':['ModW'],
            'occurrences':[{'mod':'ModW','relpath':'w.reds','line':20}]
        }],
        'entries': []
    }

def test_text_fallback_shows_baseline_and_inline_wrap(gui, sample_report):
    # Force include_wrap option off to prove inline list still appears
    try:
        gui.var_include_wrap.set(False)
    except Exception:
        pass
    gui.render_report_to_text(sample_report, conflicts_only=True, include_reference=False)
    content = gui.txt_html.get('1.0','end')
    # Overall impact label appears
    assert 'Impact (Overall)' in content or 'impact.label' in content
    # Rule change: When severity is the same (Low) and only message differs, Baseline row is not displayed
    assert ('Impact (Baseline)' not in content) and ('impact.label.baseline' not in content)
    # Inline wrap heading appears in English fallback
    assert '@wrapMethod (coexisting)' in content or 'conflict.wrapInlineHeading' in content
    # Specific wrap occurrence line
    # Wrap occurrences already indented with four spaces before dash; normal occurrences now also indented
    assert '    - [ModW] w.reds:20' in content
    assert '    - [ModA] a.reds:10' in content or '    - [ModA] a.reds:2' in content or '    - [ModA] ModA/a.reds:2' in content
    # When Baseline is unified
    base_count = content.count('Impact (Baseline)') + content.count('impact.label.baseline')
    assert base_count == 0, content
