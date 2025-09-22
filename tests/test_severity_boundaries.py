import pytest
from common.common_impact import compute_impact_unified


BOUNDARY_CONFIG = {
    'thresholds': {
        'critical': 95,
        'high': 70,
        'medium': 45,
    },
    'weights': {
        # Keep only per_mod = 1 so score == number of distinct mods
        'per_mod': 1,
        'class_keywords': {},
        'method_keywords': {},
        'signature': {'per_arg': 0, 'has_return': 0},
        'wrap_coexist_bonus': 0,
    }
}


@pytest.mark.parametrize(
    'score,expected', [
        (44, 'Low'),   # Just below Medium threshold (45)
        (45, 'Medium'),
        (69, 'Medium'),  # Just below High threshold (70)
        (70, 'High'),
        (94, 'High'),   # Just below Critical threshold (95)
        (95, 'Critical'),
    ]
)
def test_severity_threshold_boundaries(score, expected):
    mods = [f"m{i}" for i in range(score)]  # unique names => score == len(set(mods))
    impact = compute_impact_unified(
        cls='',
        meth='',
        mods=mods,
        entries=[],
        config=BOUNDARY_CONFIG,
        wrap_coexist=False,
    )
    assert impact['severity'] == expected, (
        f"Score {score} expected {expected} but got {impact['severity']} (config thresholds: {BOUNDARY_CONFIG['thresholds']})"
    )
