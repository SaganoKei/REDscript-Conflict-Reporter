# Sample REDscript Mods for wrapMethod Coexistence Demo

This directory contains minimal .reds files to produce:
- A replaceMethod conflict on `PlayerPuppet.OnUpdate` (ModA + ModB)
- wrapMethod coexistence on the same method (ModC + ModD)
- A separate replaceMethod-only method `HudManager.RefreshUI` (ModE)

## Structure
```
ModA/a.reds          (@replaceMethod PlayerPuppet.OnUpdate)
ModB/b.reds          (@replaceMethod PlayerPuppet.OnUpdate)
ModC/wrap1.reds      (@wrapMethod    PlayerPuppet.OnUpdate)
ModD/wrap2.reds      (@wrapMethod    PlayerPuppet.OnUpdate)
ModE/hud_refresh.reds(@replaceMethod HudManager.RefreshUI)
```

## Usage (PowerShell)
From repository root, run the conflict reporter pointing at `sample_mods`.

```powershell
# JSON 出力例
python -m REDscript-Conflict-Reporter.redscript_conflicts_report --root sample_mods --output sample_mods/report.json --include-wrap-coexistence

# Markdown 出力例
python -m REDscript-Conflict-Reporter.redscript_conflicts_report --root sample_mods --markdown sample_mods/report.md --include-wrap-coexistence

# HTML 出力（GUI ビルダー相当簡易）
python -m REDscript-Conflict-Reporter.redscript_conflicts_report --root sample_mods --html sample_mods/report.html --include-wrap-coexistence
```

Then open the generated report (HTML/MD). You should see under `PlayerPuppet.OnUpdate`:
1. Conflict with two replaceMethod entries (ModA, ModB)
2. Inline wrap list showing ModC / ModD (@wrapMethod)
3. Global wrap coexistence section (because of `--include-wrap-coexistence`)

If you omit `--include-wrap-coexistence`, the global section disappears but the inline list remains.

## Notes
- Files are intentionally minimal; adjust signatures or add more lines as needed.
- The tool treats `@wrapMethod` lines as coexistence augmenting the impact severity and baseline logic.
