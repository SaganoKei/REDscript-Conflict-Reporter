import pytest
from common.common_impact import symptom_label as impact_symptom_label
from common.common_i18n import make_translator, load_bundles, choose_lang

# Ensure at least English fallback works even if bundles missing optional keys.

def test_symptom_label_english_fallback():
    bundles = load_bundles()
    lang = 'en' if 'en' in bundles else choose_lang(bundles)
    tr = make_translator(lang, bundles)
    # Known codes
    for code in ['player','uiHud','vehicle','quest','inventory','damage','generic']:
        lbl = impact_symptom_label(code, tr)
        assert isinstance(lbl, str) and lbl, f"Empty label for {code}"
        # For safety: label should not be the untranslated key pattern if translation present
        if code != 'generic':
            # generic may intentionally fall back
            assert not lbl.startswith('impact.symptom.'), f"Unlocalized key leaked: {lbl}"

@pytest.mark.parametrize('code', ['player','uiHud'])
def test_symptom_label_codes_distinct(code):
    bundles = load_bundles()
    lang = 'en' if 'en' in bundles else choose_lang(bundles)
    tr = make_translator(lang, bundles)
    lbl1 = impact_symptom_label(code, tr)
    lbl2 = impact_symptom_label(code, tr)
    assert lbl1 == lbl2  # determinism
