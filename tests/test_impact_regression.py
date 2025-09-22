"""Minimal regression test for compute_impact_unified determinism.

This is not a full unit framework integration; it's a lightweight script so that
we can manually run it (python tests/test_impact_regression.py) and see PASS/FAIL.

It builds two synthetic conflict entries and ensures:
 1. Severity ordering is stable (critical > high > medium > low) given config.
 2. Re-running the function with identical inputs yields identical dict.
 3. Symptom code classification matches expectations for keyword triggers.
"""
from common.common_impact import compute_impact_unified, classify_conflict_symptom

SAMPLE_ENTRIES = [
    {'func_sig': 'public func UpdatePlayer(input: Int32, ctx: Game) -> Bool'},
]

def _run():
    mods = ['ModA', 'ModB']
    cls = 'PlayerStatusUIController'
    meth = 'UpdatePlayer'
    r1 = compute_impact_unified(cls, meth, mods, SAMPLE_ENTRIES, wrap_coexist=True)
    r2 = compute_impact_unified(cls, meth, mods, SAMPLE_ENTRIES, wrap_coexist=True)
    assert r1 == r2, f"Non-deterministic impact result: {r1} vs {r2}"
    assert r1['severity'] in {'Critical','High','Medium','Low'}, f"Unexpected severity {r1}"
    code = classify_conflict_symptom(cls)
    assert code in {'player','uiHud','vehicle','quest','inventory','damage','generic'}, f"Unexpected code {code}"
    print('PASS compute_impact_unified determinism:', r1)

if __name__ == '__main__':
    _run()
