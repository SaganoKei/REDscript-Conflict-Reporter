import json, tempfile, sys, subprocess
from pathlib import Path

CLI = Path(__file__).resolve().parent.parent / 'redscript_conflicts_report.py'

BAR_FILE_1 = """
@replaceMethod(Foo)
func Bar(a: Int32) -> Int32 {
}
""".strip()

BAR_FILE_2 = """
@replaceMethod(Foo)
func Bar(a: Int32) -> Int32 {
}
@wrapMethod(Foo)
func Bar(a: Int32) -> Int32 {
}
""".strip()

BAZ_FILE_1 = """
@replaceMethod(Foo)
func Baz() -> Void {
}
""".strip()

BAZ_FILE_2 = """
@replaceMethod(Foo)
func Baz() -> Void {
}
""".strip()

def run_cli(tmp):
    out_json = tmp / 'out.json'
    cmd = [sys.executable, str(CLI), '--root', str(tmp), '--json', '--out-json', str(out_json)]
    subprocess.check_call(cmd)
    return json.loads(out_json.read_text(encoding='utf-8'))

def test_dual_impact_fields_present():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / 'r6' / 'scripts').mkdir(parents=True)
        (tmp / 'r6' / 'scripts' / 'bar1.reds').write_text(BAR_FILE_1, encoding='utf-8')
        (tmp / 'r6' / 'scripts' / 'bar2.reds').write_text(BAR_FILE_2, encoding='utf-8')
        (tmp / 'r6' / 'scripts' / 'baz1.reds').write_text(BAZ_FILE_1, encoding='utf-8')
        (tmp / 'r6' / 'scripts' / 'baz2.reds').write_text(BAZ_FILE_2, encoding='utf-8')
        data = run_cli(tmp)
        confs = data.get('conflicts') or []
        assert confs, 'Expected conflicts present'
        # Find Bar (has wrap coexistence) and Baz (no wrap)
        bar = next(c for c in confs if c['method']=='Bar')
        baz = next(c for c in confs if c['method']=='Baz')
        # Baseline fields exist
        for g in (bar, baz):
            assert 'impact_severity_baseline' in g
            assert 'impact_message_baseline' in g
            assert 'impact_message_baseline_localized' in g
        # For Bar (wrap coexistence) baseline should be <= main severity in ordering
        order = ['Low','Medium','High','Critical']
        main_idx = order.index(bar.get('impact_severity') or 'Low') if bar.get('impact_severity') in order else 0
        base_idx = order.index(bar.get('impact_severity_baseline') or 'Low') if bar.get('impact_severity_baseline') in order else 0
        assert base_idx <= main_idx, 'Baseline severity should not exceed main severity'
        # For Baz (no wrap) baseline and main identical
        assert baz.get('impact_severity') == baz.get('impact_severity_baseline')
        assert baz.get('impact_message') == baz.get('impact_message_baseline')
