import pytest

from common.common_impact import compute_impact_unified
from common.common_i18n import load_bundles, choose_lang, make_translator, localize_impact_placeholders

def _sample_entries():
    return [{
        'func_sig': 'public func Foo(arg1: Int32, arg2: Float) -> Bool',
    }]

def test_wrap_token_localization_new_token():
    # Build impact with wrap coexistence True so token is appended
    impact = compute_impact_unified('PlayerStatsSystem', 'Update', ['ModA','ModB'], _sample_entries(), wrap_coexist=True)
    raw_msg = impact['message']
    assert 'impact.symptom.' in raw_msg, 'Symptom key missing'
    assert 'impact.extra.wrapCoexist' in raw_msg, 'Wrap coexistence token missing'

    bundles = load_bundles()
    lang = 'en' if 'en' in bundles else choose_lang(bundles)
    tr = make_translator(lang, bundles)
    localized = localize_impact_placeholders(raw_msg, tr)

    # After localization no raw token for wrap should remain
    assert 'impact.extra.wrapCoexist' not in localized
    # Symptom key should be localized if translation exists
    if 'impact.symptom.player' in raw_msg:
        # If translation exists it should not remain raw
        if tr('impact.symptom.player') != 'impact.symptom.player':
            assert 'impact.symptom.player' not in localized
    # Ensure wrap translation appeared (English or other language)
    wrap_loc = tr('impact.extra.wrapCoexist')
    assert wrap_loc in localized, f'Expected wrap coexistence translation {wrap_loc!r} in localized {localized!r}'


def test_wrap_token_localization_legacy_parenthetical():
    # Test message form containing '(wrap coexistence)'
    legacy_msg = 'impact.symptom.player (wrap coexistence)'
    bundles = load_bundles()
    lang = 'en' if 'en' in bundles else choose_lang(bundles)
    tr = make_translator(lang, bundles)
    localized = localize_impact_placeholders(legacy_msg, tr)
    wrap_loc = tr('impact.extra.wrapCoexist')
    assert wrap_loc in localized
    assert '(wrap coexistence)' not in localized
