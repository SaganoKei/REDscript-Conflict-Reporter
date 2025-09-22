import json, tempfile
from pathlib import Path
import subprocess, sys

CLI = Path(__file__).resolve().parent.parent / 'redscript_conflicts_report.py'

SAMPLE = """// sample
@replaceMethod(Foo)
func Bar() -> Void {
}
@replaceMethod(Foo)
func Bar() -> Void {
}
@wrapMethod(Foo)
func Bar() -> Void {
}
""".strip()

def _run_cli(tmp, extra=None):
    out_json = tmp / 'out.json'
    cmd = [sys.executable, str(CLI), '--root', str(tmp), '--json', '--out-json', str(out_json)]
    if extra:
        cmd.extend(extra)
    subprocess.check_call(cmd)
    return json.loads(out_json.read_text(encoding='utf-8'))

def test_json_always_has_impact_fields_with_localized():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / 'r6' / 'scripts').mkdir(parents=True)
        sample_file = tmp / 'r6' / 'scripts' / 'sample.reds'
        sample_file.write_text(SAMPLE, encoding='utf-8')
        data = _run_cli(tmp)
        assert 'conflicts' in data
        if data['conflicts']:
            c0 = data['conflicts'][0]
            assert 'impact_severity' in c0
            assert 'impact_message' in c0
            assert 'impact_message_localized' in c0
            assert c0['impact_severity'] in {'Critical','High','Medium','Low',''}
            # Localized may equal raw (English), but must be non-null string
            assert isinstance(c0['impact_message_localized'], str) and c0['impact_message_localized']
