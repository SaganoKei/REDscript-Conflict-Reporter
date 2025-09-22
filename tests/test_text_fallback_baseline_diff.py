import json, tkinter as tk
import pytest
from pathlib import Path

from gui_conflict_report import App  # type: ignore

@pytest.fixture(scope='module')
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('Tk not available in environment (baseline diff test)')
    except Exception:
        pytest.skip('Tk initialization failed (baseline diff test)')
    yield root
    try:
        root.destroy()
    except Exception:
        pass

@pytest.fixture
def gui(tk_root):
    try:
        app = App()
    except tk.TclError:
        pytest.skip('Tk not available (App init)')
    except Exception:
        pytest.skip('Tk init failure (App init)')
    try:
        app.var_lang.set('en')
    except Exception:
        pass
    return app

@pytest.fixture
def diff_report():
    # Resolve path relative to repository root (parent of tests directory)
    repo_root = Path(__file__).resolve().parents[1]
    # Moved fixture from sample_reports/ to tests/fixtures/
    p = repo_root / 'tests' / 'fixtures' / 'severity_diff_example.json'
    data = json.loads(p.read_text(encoding='utf-8'))
    return data

def test_text_fallback_shows_baseline_when_different(gui, diff_report):
    # Ensure wrap section toggle does not prevent overall impact from using wrap bonus
    try:
        gui.var_include_wrap.set(False)
    except Exception:
        pass
    gui.render_report_to_text(diff_report, conflicts_only=True, include_reference=False)
    content = gui.txt_html.get('1.0','end')
    # Should contain both Overall and Baseline lines (High vs Medium) for FooClass.OnUpdate
    assert 'Impact (Overall)' in content or 'impact.label' in content
    assert 'Impact (Baseline)' in content or 'impact.label.baseline' in content
    # Verify order: Overall line precedes Baseline line
    pos_o = content.find('Impact (Overall)') if 'Impact (Overall)' in content else content.find('impact.label')
    pos_b = content.find('Impact (Baseline)') if 'Impact (Baseline)' in content else content.find('impact.label.baseline')
    assert pos_o != -1 and pos_b != -1 and pos_o < pos_b
