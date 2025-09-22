# REDscript Conflict Reporter

<p align="center">
  <img src="assets/branding/banner_light.svg" alt="REDscript Conflict Reporter - @replaceMethod Conflict & Impact Analyzer banner (Light Primary)" width="100%" />
  <br/>
  <sub><em><a href="assets/branding/banner_dark.svg">Dark variant</a> / Branding assets licensed under MIT (see assets/branding/LICENSE.txt)</em></sub>
</p>

> 🌐 **Language Selection** | **言語選択**
>
> - [🇺🇸 English](README.en.md)
> - [🇯🇵 日本語](README.ja.md)

---

Advanced tool for detecting and analyzing REDscript `@replaceMethod` conflicts in Cyberpunk 2077 MODs with comprehensive impact assessment.

## Overview

REDscript-Conflict-Reporter automatically detects conflicts caused by multiple MODs replacing the same methods, providing comprehensive reports with intelligent impact evaluation.

**Key Features:**
- 🔍 **Conflict Detection**: Precisely identifies MOD conflicts via `@replaceMethod` analysis
- 📊 **Impact Assessment**: Heuristic analysis with severity levels (Critical/High/Medium/Low)
- 📝 **Multi-format Output**: Detailed reports in JSON, Markdown, and HTML formats
- 🎨 **Rich GUI**: WebView2-powered preview, real-time filters, dark/light themes
- 🌐 **Internationalization**: Japanese/English support, extensible via `i18n/*.json` files
- ⚙︁E**Advanced Settings**: wrapMethod coexistence detection, output customization

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

## 💾 System Requirements & Installation

### Executable (.exe) Version

**Minimum Requirements:**
- **OS**: Windows 10 (version 1809 or later) / Windows 11
- **Architecture**: x64 (64-bit)
- **Memory**: 512 MB RAM minimum, 1 GB recommended
- **Storage**: 50 MB free disk space
- **Display**: 1024x768 resolution minimum

**Optional (for enhanced GUI experience):**
- **WebView2 Runtime**: Microsoft Edge WebView2 Runtime for rich HTML preview
  - Usually pre-installed on Windows 10/11
  - Download: https://developer.microsoft.com/microsoft-edge/webview2/
- **Internet Connection**: For downloading WebView2 Runtime (if not present)

**Note**: The executable is self-contained and does not require Python installation.

### Python Source Version

**Requirements:**
- **Python**: 3.8 or later
- **OS**: Windows 10/11, Linux, macOS
- **Dependencies**: Standard library only (no external packages required)
- **Optional**: `tkwebview2` package for enhanced WebView2 support

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

## 📋 CLI Reference

**Basic Syntax:**
```bash
python redscript_conflicts_report.py [options]
```

**Key Options:**

| Option                               | Description                                                                       | Default                                     |
|--------------------------------------|-----------------------------------------------------------------------------------|---------------------------------------------|
| `--root <path>`                      | Scan root path                                                                    | Auto-detect `r6/scripts`                   |
| `--mode <conflicts&#124;reference>` | Output mode: `conflicts` (conflicts only) or `reference` (include reference list) | `conflicts`                                 |
| `--wrap <include&#124;exclude>`     | wrapMethod coexistence: `include` or `exclude`                                   | `exclude`                                   |
| `--lang <code>`                      | Language code (`en`, `ja`, etc.)                                                 | `en` or first available                     |
| `--json` `--md` `--html`             | Output format selection                                                           | All formats                                 |
| `--out-json <file>`                  | JSON output path                                                                  | `reports/redscript_conflicts.json`         |
| `--out-md <file>`                    | Markdown output path                                                              | `reports/redscript_conflicts.md`           |
| `--out-html <file>`                  | HTML output path                                                                  | `reports/redscript_conflicts.html`         |

**Examples:**
```bash
# Custom output path
python redscript_conflicts_report.py --html --out-html analysis/conflicts_$(date +%Y%m%d).html

# Include reference list with wrapMethod coexistence
python redscript_conflicts_report.py --mode reference --wrap include

# Output in Japanese
python redscript_conflicts_report.py --lang ja

# Conflicts only with wrapMethod coexistence (default + coexistence)
python redscript_conflicts_report.py --wrap include
```

**⚠️ Argument Notes:**
- `--mode`: Determines output content. `conflicts` outputs conflicts only, `reference` outputs all entries plus reference list
- `--wrap`: wrapMethod coexistence handling. `include` to include, `exclude` to exclude

### 🔍 Conflict Detection Rules

**Detection Scope:**
- Only `@replaceMethod` annotations are considered conflicts
- Same `(class, method)` pair replaced by multiple MODs

**Excluded:**
- `@wrapMethod` and `@replaceGlobal` are not treated as conflicts (but recorded as coexistence)

**wrapMethod Coexistence:**
- Multiple `@wrapMethod` on same target
- Mixed `@replaceMethod` and `@wrapMethod` scenarios
- Enabled via `--wrap include`

---

## 🎨 GUI Features

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

---

## 📊 Impact Assessment System

REDscript-Conflict-Reporter features intelligent heuristic analysis for automatic conflict severity determination.

### Severity Classifications

| Level              | Description                             | Threshold      |
|--------------------|-----------------------------------------|----------------|
| **Critical**       | High probability core system damage    | ≥95 points     |
| **High**           | Noticeable bugs likely                 | ≥70 points     |
| **Medium**         | Limited/conditional issues possible    | ≥45 points     |
| **Low**            | Minor or cosmetic-level risks          | <45 points     |

### Symptom Categories

Conflicts are automatically classified by impact domain:

| Code           | Impact Area    | Description                                        |
|----------------|----------------|----------------------------------------------------|
| `uiHud`        | UI/HUD         | Display inconsistencies, HUD flickering           |
| `player`       | Player         | Stats, equipment, player behavior side effects    |
| `vehicle`      | Vehicle        | Vehicle handling and behavior impacts             |
| `quest`        | Quest          | Quest progression, flags, journal state risks     |
| `inventory`    | Inventory      | Item management, inventory inconsistencies        |
| `damage`       | Combat         | Damage calculation, combat balance variations     |
| `generic`      | General        | Other general instability factors                 |

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
━E  ├── ModA/
━E  ├── ModB/
━E  └── ModC/
└── reports/             # Output (auto-created)
    ├── redscript_conflicts.html
    ├── redscript_conflicts.md
    └── redscript_conflicts.json
```

### Recommended Settings

**GUI Initial Configuration:**
- ✁E**HTML Preview**: Enabled
- ✁E**wrapMethod Coexistence**: Enabled
- ✁E**Severity Filters**: Critical/High only
- ✁E**Auto-open Folder**: Enabled

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

## ⚙︁EConfiguration & Customization

### Settings File

**Location:**
- Default: `redscript_conflict_gui.json`
- Custom: Menu ↁEOutput Settings ↁESettings File

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
Menu ↁEDisplay Settings ↁEFont ↁESelect "Noto Sans JP"
```

**Q: Permission error on output**
```bash
# Solution: Change output location
Menu ↁEOutput Settings ↁEChange output folder
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
- ✁EUse `--conflicts-only` flag
- ✁EUtilize preview filters
- ✁ELimit to JSON output only

**Memory limitations:**
- ✁EDisable preview
- ✁EReduce font scaling
- ✁ERegular temporary file cleanup

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

1. **Fork** ↁE**Clone** ↁE**Create Branch**
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

*REDscript-Conflict-Reporter is developed to improve stability for the Cyberpunk 2077 MOD community.*

---

Options:
