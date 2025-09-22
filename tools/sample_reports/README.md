# Sample Reports: Inline wrapMethod Coexistence

These JSON files demonstrate the case where a conflict method also has @wrapMethod coexistence. The reporter will always embed an inline list under that conflict showing the wrap occurrences, regardless of whether the global wrap coexistence section is enabled.

## Files

- `sample_report_wrap_inline.json`
  Global option `_options.include_wrap_coexistence = true` (the global wrap coexistence section + inline list).
- `sample_report_wrap_inline_nowrapsection.json`
  Global option `_options.include_wrap_coexistence = false` (no global section, but inline list still shown).

## How to render to HTML (PowerShell)

```powershell
# From repository root
python - <<'PY'
import json, sys, pathlib
from report_builders import build_full_html_gui
root = pathlib.Path('REDscript-Conflict-Reporter/tools/sample_reports')
for name in ['sample_report_wrap_inline.json','sample_report_wrap_inline_nowrapsection.json']:
    data = json.loads((root/name).read_text(encoding='utf-8'))
    html, _ = build_full_html_gui(data, tr=lambda k: k, dark=False, conflicts_only=False, include_reference=True, inline_css=True, lang=None)
    out_path = root / (name.replace('.json','.html'))
    out_path.write_text(html, encoding='utf-8')
    print('Wrote', out_path)
PY
```

Open the generated `.html` files in a browser and locate the `PlayerPuppet.OnUpdate` conflict block. You should see:

1. The replaceMethod occurrences list.
2. A heading: `Other mods @wrapMethod (coexisting)` (or localized string if translations loaded).
3. A `<ul class='wrap-occurrences'>` containing the wrap occurrences.

In the `_nowrapsection` variant, scroll to the end to verify there is no global wrap coexistence section—only the inline block.

## Notes
- These synthetic examples mirror the structure produced by the scanning phase.
- You can localize the heading by providing a translator instead of `lambda k: k`.
