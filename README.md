# REDscript Conflict Reporter

> 🌐 **Language Selection** | **言語選択**
>
> - [🇺🇸 English](README.en.md)
> - [🇯🇵 日本語](README.ja.md)

---

Advanced tool for detecting and analyzing REDscript `@replaceMethod` conflicts in Cyberpunk 2077 MODs with comprehensive impact assessment.

Cyberpunk 2077 MODの REDscript `@replaceMethod` 競合を検出・分析し、詳細レポートを出力するツールです。

## Quick Start

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
```

## Features

- 🔍 **Conflict Detection**: Precisely identifies MOD conflicts via `@replaceMethod` analysis
- 📊 **Impact Assessment**: Heuristic analysis with severity levels (Critical/High/Medium/Low)
- 📝 **Multi-format Output**: Detailed reports in JSON, Markdown, and HTML formats
- 🎨 **Rich GUI**: WebView2-powered preview, real-time filters, dark/light themes
- 🌐 **Internationalization**: Japanese/English support, extensible via `i18n/*.json` files

## Documentation

For detailed documentation, please select your preferred language:

- **[🇺🇸 English Documentation](README.en.md)** - Complete English guide
- **[🇯🇵 日本語ドキュメント](README.ja.md)** - 完全な日本語ガイド

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

*REDscript-Conflict-Reporter is developed to improve the stability of the Cyberpunk 2077 MOD community.*