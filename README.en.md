# REDscript Conflict Reporter

Advanced tool for detecting and analyzing REDscript `@replaceMethod` conflicts in Cyberpunk 2077 MODs with comprehensive impact assessment.

## Overview

REDscript-Conflict-Reporter automatically detects conflicts caused by multiple MODs replacing the same methods, providing comprehensive reports with intelligent impact evaluation.

**Key Features:**
- 🔍 **Conflict Detection**: Precisely identifies MOD conflicts via `@replaceMethod` analysis
- 📊 **Impact Assessment**: Heuristic analysis with severity levels (Critical/High/Medium/Low)
- 📝 **Multi-format Output**: Detailed reports in JSON, Markdown, and HTML formats
- 🎨 **Rich GUI**: WebView2-powered preview, real-time filters, dark/light themes
- 🌐 **Internationalization**: Japanese/English support, extensible via `i18n/*.json` files
- ⚙️ **Advanced Settings**: wrapMethod coexistence detection, output customization

**Tool Components:**
- **CLI**: `redscript_conflicts_report.py` - Command-line execution for automation
- **GUI**: `gui_conflict_report.py` - Interactive analysis and preview

---

## 🚀 Quick Start

### GUI Version (Recommended)
```bash
python gui_conflict_report.py
```

### CLI Version
```bash
# Basic execution (conflicts only, default)
python redscript_conflicts_report.py

# All entries output (conflicts + reference list)
python redscript_conflicts_report.py --mode reference

# HTML output only
python redscript_conflicts_report.py --html --out-html my_report.html
```

---

## 📋 CLI Reference

Usage:

```
### 📋 CLI Reference

**Basic Syntax:**
```bash
python redscript_conflicts_report.py [options]
```

**Key Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` `--md` `--html` | Output format selection | All formats |
| `--mode <conflicts\|reference>` | Output mode: `conflicts` (conflicts only) or `reference` (include reference list) | `conflicts` |
| `--wrap <include\|exclude>` | wrapMethod coexistence: `include` or `exclude` | `exclude` |
| `--lang <code>` | Language code (`en`, `ja`, etc.) | `en` or first available |
| `--root <path>` | Scan root path | Auto-detect `r6/scripts` |
| `--out-json <file>` | JSON output path | `reports/redscript_conflicts.json` |
| `--out-md <file>` | Markdown output path | `reports/redscript_conflicts.md` |
| `--out-html <file>` | HTML output path | `reports/redscript_conflicts.html` |

**Argument Options:**
- `--mode`: Determines output content. `conflicts` outputs conflicts only, `reference` outputs all entries plus reference list
- `--wrap`: wrapMethod coexistence handling. `include` to include, `exclude` to exclude

**Examples:**
```bash
# Custom output path
python redscript_conflicts_report.py --html --out-html analysis/conflicts_$(date +%Y%m%d).html

# Include reference list with wrapMethod coexistence
python redscript_conflicts_report.py --mode reference --wrap include

# Output in Japanese
python redscript_conflicts_report.py --lang ja
```

### 🔍 Conflict Detection Rules

**Detection Scope:**
- Only `@replaceMethod` annotations are considered conflicts
- Same `(class, method)` pair replaced by multiple MODs

**Excluded:**
- `@wrapMethod` and `@replaceGlobal` are not treated as conflicts (but recorded as coexistence)

**wrapMethod Coexistence:**
- Multiple `@wrapMethod` on same target
- Mixed `@replaceMethod` and `@wrapMethod` scenarios
- Enabled via `--include-wrap-coexistence`

---

## 🎨 GUI Features
```

All arguments are optional. When you run with no arguments, the tool uses these defaults:
- Scan root: attempts to resolve `r6/scripts` relative to the current directory
- Outputs: writes all three formats
  - JSON: `reports/redscript_conflicts.json`
  - Markdown: `reports/redscript_conflicts.md`
  - HTML: `reports/redscript_conflicts.html`
- Mode defaults:
  - `--mode`: `conflicts` (conflicts only, default behavior)
  - `--wrap`: `exclude` (wrapMethod coexistence excluded)

Options:
- `--json` `--md` `--html`: select which outputs to write. If none are specified, all three are written.
- `--mode <conflicts|reference>`: output mode. `conflicts` outputs only conflicting entries (default), `reference` includes the full @replaceMethod reference list.
- `--wrap <include|exclude>`: wrapMethod coexistence handling. `include` adds wrapMethod coexistence list sections (MD/HTML) and corresponding JSON arrays (`wrap_coexistence`, `replace_wrap_coexistence`). Default: `exclude` (arrays/sections omitted). Even when excluded, each conflicted method still shows an inline list of other mods' `@wrapMethod` occurrences directly under the conflict details for quick context.
- `--root <path>`: scan root (default: attempts to resolve `r6/scripts`).
- `--out-json <file>`: JSON report path (default: `reports/redscript_conflicts.json`).
- `--out-md <file>`: Markdown report path (default: `reports/redscript_conflicts.md`).
- `--out-html <file>`: HTML report path (default: `reports/redscript_conflicts.html`).
- `--out-html <file>`: HTML report path (default: `reports/redscript_conflicts.html`).

Notes:
- CLI Markdown/HTML writers are shared with the GUI. When the GUI’s “Localize file outputs” is OFF, GUI-saved Markdown/HTML are byte-identical to CLI outputs.
- JSON is always English-only from the CLI. GUI may add a `localized` block when localization is ON.
- JSON includes `_options.include_wrap_coexistence` (true/false) indicating whether wrapMethod coexistence sections/arrays were enabled for the outputs.

The JSON output includes conflicts, annotation counts, entries (when not trimmed by `--conflicts-only`), and a summary.

### Conflict detection rules

What is reported as a "conflict" in the JSON/MD/HTML outputs is intentionally narrow and deterministic:

- Scope: only `@replaceMethod` is considered for conflicts.
- Key: a conflict is recorded per `(class, method)` pair.
- Condition: when the same `(class, method)` is replaced by more than one file (i.e., multiple mods) under the scan root, it becomes a conflict.
- Metadata: for each conflict we include the unique mod names (top-level folder under `r6/scripts`) and the list of contributing occurrences.

Non-conflict annotations:
- `@wrapMethod` and `@replaceGlobal` are not treated as conflicts in the saved reports. They still contribute to totals and entries but are not listed under `conflicts`.

Coexistence reporting (new):
- We additionally report "coexistence" cases in separate sections, without changing the strict definition of conflicts:
  - Multiple files wrapping the same `(class, method)` via `@wrapMethod`
  - Coexistence of `@replaceMethod` and `@wrapMethod` on the same `(class, method)`
- JSON adds two arrays:
  - `wrap_coexistence`: list of wrapMethod-only coexistence entries (`class`, `method`, `wrap_count`, `mods`, `occurrences`)
  - `replace_wrap_coexistence`: list of replace+wrapMethod coexistence entries (`replace_count`, `wrap_count`, `mods_replace`, `mods_wrap`, `occurrences_replace`, `occurrences_wrap`)
- Markdown/HTML include two new sections:
  - "wrapMethod Coexistence (@wrapMethod by multiple files)"
### 🎨 GUI Features

**Launch:**
```bash
python gui_conflict_report.py
```

**Core Features:**

🖥️ **Main Interface**
- Scan root configuration (`r6/scripts` auto-detection)
- Output settings (HTML/Markdown/JSON individual control)
- Real-time preview

⚙️ **Output Settings** (Menu Bar)
- Individual format toggle (HTML/MD/JSON)
- Multi-language file output
- Auto-open folder after generation
- Custom output path configuration

🎨 **Display Settings**
- Dark/Light theme switching
- Font scale adjustment (50%-150%)
- Language switching (Japanese/English, extensible via additional language files)
- Automatic settings persistence

🔍 **Preview Filters**
- MOD name filtering (comma-separated)
- Class name partial matching
- Severity-based filtering (Critical/High/Medium/Low)
- Real-time updates with debouncing

📊 **Impact Assessment System**
- Heuristic analysis for automatic severity determination
- 4-level evaluation: Critical / High / Medium / Low
- Symptom classification: UI/HUD, Player, Vehicle, Quest, Inventory, Combat, Other
- wrapMethod coexistence bonus scoring

🌐 **Internationalization**
- Japanese/English runtime switching
- Localized file output options
- Native language display ("日本語 (ja)", "English (en)")
- Extensible via `i18n/*.json` language files

🛠️ **Technical Specifications**
- WebView2 support (with fallback)
- Settings file persistence
- Multiple profile support
- Automatic temporary file cleanup

---

## 📊 Impact Assessment System

REDscript-Conflict-Reporter features intelligent heuristic analysis for automatic conflict severity determination.

### Severity Classifications

| Level | Description | Threshold |
|-------|-------------|-----------|
| **Critical** | High probability core system damage | ≥95 points |
| **High** | Noticeable bugs likely | ≥70 points |
| **Medium** | Limited/conditional issues possible | ≥45 points |
| **Low** | Minor or cosmetic-level risks | <45 points |

### Symptom Categories

Conflicts are automatically classified by impact domain:

| Code | Impact Area | Description |
|------|-------------|-------------|
| `uiHud` | UI/HUD | Display inconsistencies, HUD flickering |
| `player` | Player | Stats, equipment, player behavior side effects |
| `vehicle` | Vehicle | Vehicle handling and behavior impacts |
| `quest` | Quest | Quest progression, flags, journal state risks |
| `inventory` | Inventory | Item management, inventory inconsistencies |
| `damage` | Combat | Damage calculation, combat balance variations |
| `generic` | General | Other general instability factors |

### Assessment Factors

Severity calculation considers:

- **MOD Count**: Number of MODs involved in conflict (10 points per MOD)
- **Class Importance**: Higher weight for system classes (PlayerPuppet, etc.)
- **Method Importance**: Higher weight for critical methods (OnUpdate, etc.)
- **Signature Complexity**: Complexity based on argument count and return values
- **wrapMethod Coexistence**: Bonus for `@wrapMethod` presence on same target

### Customization

Assessment criteria can be customized via `assets/impact_config.json`:

```json
{
  "thresholds": {
    "critical": 95,
    "high": 70,
    "medium": 45
  },
  "weights": {
    "per_mod": 10,
    "class_keywords": { "PlayerPuppet": 15 },
    "method_keywords": { "OnUpdate": 10 }
  }
}
```

---

## 💾 Installation & Setup

### Requirements

- **Python**: 3.8 or higher
- **OS**: Windows 10/11 (WebView2 support), Linux, macOS
- **Required Packages**: Standard library only
- **Recommended Packages**: `tkwebview2` (WebView2 support)

### Setup

1. **Clone Repository**
   ```bash
   git clone https://github.com/SaganoKei/REDscript-Conflict-Reporter.git
   cd REDscript-Conflict-Reporter
   ```

2. **Install Dependencies (Optional)**
   ```bash
   # Development environment
   pip install -r requirements-dev.txt

   # WebView2 support for GUI (recommended)
   pip install tkwebview2
   ```

3. **Verify Installation**
   ```bash
   # Test CLI
   python redscript_conflicts_report.py --help

   # Launch GUI
   python gui_conflict_report.py
   ```

### Creating Executable

**Using PyInstaller (standalone exe):**
```bash
# GUI version (recommended)
python -m PyInstaller REDscriptConflictReporter.spec

# Folder distribution
python -m PyInstaller REDscriptConflictReporter_onedir.spec
```

Output: `dist/REDscriptConflictReporter.exe`

---

## 🎯 Usage Guide

### Basic Workflow

1. **Open Cyberpunk 2077 game folder**
2. **Launch GUI** or **run CLI**
3. **Set scan root** to `r6/scripts`
4. **Execute report generation**
5. **Review conflicts** and **impact assessments**

### Directory Structure

```
Cyberpunk 2077/
├── r6/scripts/          # Scan target
│   ├── ModA/
│   ├── ModB/
│   └── ModC/
└── reports/             # Output (auto-created)
    ├── redscript_conflicts.html
    ├── redscript_conflicts.md
    └── redscript_conflicts.json
```

### Recommended Settings

**GUI Initial Configuration:**
- ✅ **HTML Preview**: Enabled
- ✅ **wrapMethod Coexistence**: Enabled
- ✅ **Severity Filters**: Critical/High only
- ✅ **Auto-open Folder**: Enabled

**CLI Automation:**
```bash
# Weekly conflict check (cron/Task Scheduler)
python redscript_conflicts_report.py --conflicts-only --html
```

---

## 📖 Output Format Details

### HTML Report
- **Rich Preview**: WebView2-powered detailed display
- **Severity Badges**: Color-coded classification with tooltips
- **Interactive Elements**: Collapsible sections, filters
- **Theme Support**: Dark/Light mode compatibility

### Markdown Report
- **GitHub Compatible**: For Issues, PRs, Wiki posts
- **Plain Text**: Editor and IDE display
- **Structured**: Headers, lists, tables

### JSON Report
- **Programmatic Processing**: API and automated analysis
- **Complete Information**: All conflicts, statistics, metadata
- **Multi-language Support**: Localized blocks (optional)
- **Impact Data**: severity/message/baseline information

### wrapMethod Coexistence Reports

Detects multiple approaches to the same method:

- **wrapMethod Overlap**: Multiple MODs wrapping same method
- **Replace-Wrap Mixing**: Simultaneous replace and wrap existence
- **Impact Bonus**: Complexity bonus for coexistence

---

## ⚙️ Configuration & Customization

### Settings File

**Location:**
- Default: `redscript_conflict_gui.json`
- Custom: Menu → Output Settings → Settings File

**Key Configuration Items:**
```json
{
  "lang": "en",                    // Language (ja/en)
  "dark_mode": false,              // Dark mode
  "font_scale": 1.0,               // Font scaling
  "enable_preview": true,          // HTML preview
  "include_wrap": true,            // wrapMethod coexistence
  "localize_output": true,         // Output localization
  "auto_open": true               // Auto-open folder
}
```

### Impact Configuration

**Custom Settings:** `assets/impact_config.json`

**Environment Variable:** `REDCONFLICT_IMPACT_CONFIG=path/to/config.json`

**Example Configuration:**
```json
{
  "thresholds": {
    "critical": 100,     // Stricter thresholds
    "high": 80,
    "medium": 50
  },
  "weights": {
    "per_mod": 15,       // Increased MOD count weight
    "wrap_coexistence": 25   // Increased coexistence weight
  }
}
```

### 🌐 Internationalization & Language Extension

**Supported Languages:**
- Japanese (`ja.json`)
- English (`en.json`)

**Adding New Languages:**
1. Create new language file in `i18n/` folder (e.g., `fr.json`, `de.json`, `ko.json`)
2. Use existing `ja.json` or `en.json` as template
3. Translate all translation keys with corresponding values
4. Application automatically detects and utilizes new languages

**Language File Example (`fr.json`):**
```json
{
  "app.title": "REDscript Conflict Reporter",
  "scan.root": "Racine de scan (r6/scripts)",
  "actions.generate": "Générer le rapport",
  "theme.dark": "Sombre",
  "theme.light": "Clair"
}
```

**Font Configuration (Language-specific):**
Each language file can specify recommended fonts:
```json
{
  "preferredFonts": ["Noto Sans", "Segoe UI", "Arial"]
}
```

---

## 🔧 Troubleshooting

### Common Issues

**Q: WebView2 preview not displaying**
```bash
# Solution: Install WebView2 Runtime
# or verify tkwebview2 package
pip install tkwebview2
```

**Q: Japanese fonts not displaying**
```bash
# Solution: Change font settings
Menu → Display Settings → Font → Select "Noto Sans JP"
```

**Q: Permission error on output**
```bash
# Solution: Change output location
Menu → Output Settings → Change output folder
```

**Q: CLI character encoding issues**
```bash
# Windows PowerShell
chcp 65001  # UTF-8 setting

# Command Prompt
python redscript_conflicts_report.py --html  # HTML recommended
```

### Performance Optimization

**Large MOD environments (100+ MODs):**
- ✅ Use `--conflicts-only` flag
- ✅ Utilize preview filters
- ✅ Limit to JSON output only

**Memory limitations:**
- ✅ Disable preview
- ✅ Reduce font scaling
- ✅ Regular temporary file cleanup

### Debug & Logging

**Detailed logging:**
```bash
# Environment variable
set RCR_DEBUG=1
python gui_conflict_report.py
```

**Log file locations:**
- Windows: `%TEMP%/redscript_conflict_*.log`
- Linux/macOS: `/tmp/redscript_conflict_*.log`

---

## 🚀 Advanced Usage Examples

### CI/CD Integration

**GitHub Actions Example:**
```yaml
- name: MOD Conflict Check
  run: |
    python redscript_conflicts_report.py --conflicts-only --json
    if [ -s reports/redscript_conflicts.json ]; then
      echo "⚠️ Conflicts detected!" >> $GITHUB_STEP_SUMMARY
    fi
```

### Batch Processing

**PowerShell Automation:**
```powershell
# Bulk check for multiple profiles
$profiles = @("Profile1", "Profile2", "Profile3")
foreach ($profile in $profiles) {
    python redscript_conflicts_report.py --root "Games/$profile/r6/scripts" --out-html "reports/$profile.html"
}
```

### Result Analysis

**JSON Analysis Example (Python):**
```python
import json

with open('reports/redscript_conflicts.json') as f:
    report = json.load(f)

critical_conflicts = [
    c for c in report['conflicts']
    if c['impact_severity'] == 'Critical'
]

print(f"Critical conflicts: {len(critical_conflicts)}")
```

---

## 📞 Support & Community

### Bug Reports & Feature Requests

- **GitHub Issues**: [REDscript-Conflict-Reporter/issues](https://github.com/SaganoKei/REDscript-Conflict-Reporter/issues)
- **Templates**: Bug report and feature request templates provided

### Contributing & Development

1. **Fork** → **Clone** → **Create Branch**
2. **Run Tests**: `pytest tests/`
3. **Create Pull Request**

### License

MIT License - See `LICENSE` file for details

---

## 📋 Release History

Latest changes available on [Releases](https://github.com/SaganoKei/REDscript-Conflict-Reporter/releases) page.

### Major Milestones

- **v0.1.0**: Initial release with CLI core functionality, GUI WebView2 support, internationalization, and impact assessment system

---

*REDscript-Conflict-Reporter is developed to improve stability for the Cyberpunk 2077 MOD community.*
- The GUI shows a heuristic "Impact" (severity/message) for triage. Conflict detail panels always include an inline list of other mods' wrapMethod occurrences (same as saved outputs) when wraps exist.
- Hidden wrap tooltip: If you disable the outer wrap coexistence sections (`--no-wrap-coexistence` in CLI or toggle OFF in GUI) but a method has wrap coexistence, the HTML still embeds a subtle `title` tooltip on that method's severity badge.

---

## GUI

Launch:

```
python .\gui_conflict_report.py
```

Key features:
- Choose scan root (`r6/scripts`) in the main window; configure output paths/toggles from the menubar
- Mode (exclusive):
  - Conflicts only (ON): only conflicting methods/MODs
  - Include reference (OFF): also include the @replaceMethod reference list
  - Include wrapMethod coexistence (default OFF): affects both Preview (HTML/Text/Markdown) and saved outputs (MD/HTML/JSON). The setting is persisted/restored, and JSON also records `_options.include_wrap_coexistence`. When OFF, `wrap_coexistence` and `replace_wrap_coexistence` are hidden/omitted in both preview and outputs.
- Menubar: “Output settings” — enable HTML/Markdown/JSON individually, localize file outputs (MD/JSON/HTML), auto-open output folder after generation, set output file paths, choose the settings file location, open the output folder
  - You can also open a dedicated “Output settings” window from the menu to edit toggles and output paths in a layout matching the Scan settings section. The settings file path row is placed at the very top of that window.
  - (Update) The legacy status summary bar at the bottom of the Output settings window has been removed. Instead, the primary output toggles (HTML / MD / JSON / Localize / Auto-open) now appear as a horizontal row of checkboxes at the top of the window for immediate visibility.
- Language menu in the menubar (left of “Output settings”), applies at runtime; items show native names
- Dark/Light theme toggle (menubar “Theme” menu, rightmost)
- Logs, toast notifications, optional auto-open of output folder after generation

### Rich Preview & UX
- HTML Preview (tab labeled "HTML" in all languages): rich via WebView2 (tkwebview2) if available; otherwise styled Text fallback
- Impact (Preview-only): heuristic severity and description for triage; JSON/Markdown remain unchanged
- Filters (Preview-only): MOD tokens (comma-separated), class substring, severity (Critical/High/Medium/Low)
- Summary table, legend, font scale slider, spinner, colored logs, toast (HTML headings h1/h2/h3 scale with font size)
- Settings persistence: mode/theme/filters/font scale plus root/output paths and output toggles are saved to a settings file
- Auto-open: optionally open the output folder after files are written
- No copy-to-clipboard button in Preview (removed by request)

### Internationalization (i18n)
- Strings live under `i18n/*.json` (or an `i18n` folder next to the exe); runtime language switching supported
- Selector shows native names (e.g., "English (en)", "日本語 (ja)")
- "Localize file outputs (MD/JSON/HTML)":
  - ON: Markdown/HTML are generated in the selected language; JSON includes a `localized` block
  - OFF: Markdown/HTML are English-only; JSON omits `localized`

### Settings file
- Location is configurable from the menubar: Output settings → “Settings file…”. The entry row for the settings file lives at the very top of the Output settings window.
- Bootstrap pointer (exe-adjacent): `redscript_conflict_gui.json` stores `{ "settings_path": "C:\\path\\to\\your\\settings.json" }` and the app reads this at startup.
- When you change the settings file from the menu, the bootstrap JSON is updated automatically.
- Default: if no bootstrap is present, the app falls back to an exe-adjacent settings file.

### Package to Windows .exe (optional)
1. Requirements: Python 3, tkinter (built-in), optionally `tkhtmlview`
2. Single-file, no console (if you don't bundle i18n, place an `i18n` folder next to the exe)
```
python -m PyInstaller --onefile --noconsole --name REDscriptConflictReporter gui_conflict_report.py
```
3. Distribution: `dist/REDscriptConflictReporter.exe`

Tips:
- When run from the game root, the app auto-detects `r6/scripts` and `reports/`
- Otherwise set scan root in the main window and set output paths via Menubar → Output settings

### Verify CLI/GUI parity (optional)
1) Generate with CLI (defaults to all outputs):
```
python .\redscript_conflicts_report.py
```
2) Generate with GUI with “Localize file outputs” OFF, and enable the same outputs.
3) Compare files under `reports/` (HTML/MD should be identical, JSON structure equivalent).

### HTML rendering notes
- With WebView2, the body HTML is styled and scales with the font-size control (h1/h2/h3 are sized in em).
- In dark mode, background/foreground colors are adjusted where possible.

### Unified Impact Heuristic
The CLI & GUI share a single impact/severity computation now centralized in `common_impact.py` as `compute_impact_unified` (it was previously located in `report_builders.py`).

Key points (current model):
- Single modern profile (legacy/alternate profile removed). Default thresholds: Critical ≥ 95, High ≥ 70, Medium ≥ 45, else Low.
- Weights: per-mod, class keywords, method keywords, signature complexity (arg count + non-void return), wrap coexistence bonus.
- External configuration (override thresholds / weights) via an `impact_config.json` file. Search order (first valid wins):
  1. Environment variable `REDCONFLICT_IMPACT_CONFIG` (absolute or relative path)
  2. `assets/impact_config.json` in the current working directory
  3. `assets/impact_config.json` relative to the module/package location (bundled asset)
  The first successfully parsed file containing `{"thresholds":{...}, "weights":{...}}` is cached and used. If none resolve, the embedded fallback (same values as the distributed file) is used.
- The shipped `assets/impact_config.json` matches the embedded defaults (95 / 70 / 45 thresholds) so editing that file is the primary customization route.
- Severity is surfaced consistently to Markdown, HTML, and now always to JSON. Impact data is always embedded (the previous `--json-impact` flag and `RCR_JSON_IMPACT` env gate have been removed).

JSON impact embedding (always-on):

Each object under `conflicts`, `wrap_coexistence`, and `replace_wrap_coexistence` now contains:

| Field | Description |
|-------|-------------|
| `impact_severity` | Severity bucket (Critical / High / Medium / Low or empty on error) |
| `impact_message` | Raw i18n token string (e.g. `impact.symptom.player impact.extra.wrapCoexist`) |
| `impact_message_localized` | Localized, human-readable message (falls back to raw tokens if a translation is missing) |
| `impact_severity_baseline` | Severity computed without wrap coexistence bonus (for comparison) |
| `impact_message_baseline` | Raw token message without wrap bonus |
| `impact_message_baseline_localized` | Localized baseline message |

Notes:
- `impact_message` stays tokenized, enabling downstream tools to re-localize if desired.
- `impact_message_localized` is produced using the same localization pass applied to HTML/Markdown; if the selected language bundle lacks a key, the token is preserved verbatim.
- The heuristic is identical across all formats (single computation path).

Removed / cleaned up:
- Legacy profile & compatibility logic eliminated (previous 80/60/40 threshold variant removed).
- Redundant in-module copy paths in builders replaced by imports from `common_impact`.

Deprecated:
- `default_impact_assessment` remains as a thin forwarder to `compute_impact_unified` and will be removed in a future release. Use `compute_impact_unified` directly.

### Symptom-based Impact Messages (New)

Instead of a numeric/score-oriented explanatory string, the unified impact now emits a short, localized symptom category label plus an optional note when wrap coexistence is present.

Current symptom codes (and i18n keys under `impact.symptom.<code>`):

| Code | English Label | Purpose |
|------|---------------|---------|
| uiHud | UI / HUD instability | Visual or HUD related side-effects |
| player | Player ability or stats issues | Player stats/abilities/equipment side-effects |
| vehicle | Vehicle handling or behavior | Driving/mount control behaviors |
| quest | Quest or scripted progression risk | Progress / quest state interference |
| inventory | Inventory / item anomalies | Item lists, inventory mutation issues |
| damage | Damage / combat calculation variance | Combat balance / damage formula alterations |
| generic | General instability | Fallback when no keyword matched |

Classification logic lives in `common_impact.classify_conflict_symptom` and is shared by CLI and GUI. The GUI preview renders exactly the same result object produced by `compute_impact_unified`, ensuring parity of both severity and message text.

Wrap coexistence note: when the "Show wrapMethod coexistence list" option/flag is enabled and an overlapping `@wrapMethod` exists for the same target, the message appends the localized `impact.extra.wrapCoexist` string.

Overall vs baseline impact: If a method has wrap coexistence, the report computes two variants – "Impact (Overall)" (with coexistence bonus) and "Impact (Baseline)" (without the wrap bonus). JSON embeds both sets; HTML/Markdown render the second line only when severity or message differs.

Markdown Baseline Note:
The Markdown builder adds a plain text line `Impact (Baseline): <Severity>` immediately after the method signature under the same difference conditions. If values are identical, the baseline line is omitted to keep output compact.

Snapshot Generation Script:
Developer helper script `tools/generate_snapshots.py` can regenerate the synthetic test fixtures under `tests/snapshots/` (HTML & Markdown) reflecting the current rendering logic.

Planned extension: moving symptom keyword to code mapping into a future external profile (so you can tailor domain-specific categories without editing code).