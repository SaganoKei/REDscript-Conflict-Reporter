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

Cyberpunk 2077 MODの REDscript `@replaceMethod` 競合を検出・分析し、詳細レポートを出力するツールです。

## 概要

REDscript-Conflict-Reporter は、複数のMODが同じメソッドを置換することで発生する競合を自動検出し、影響度評価と共に包括的なレポートを生成します。

**主な機能:**
- 🔍 **競合検出**: `@replaceMethod` による MOの競合を正確に識別
- 📊 **影響度評価**: ヒューリスティック分析による重要度（Critical/High/Medium/Low）の自動判定
- 📝 **多形式出力**: JSON、Markdown、HTML での詳細レポート生成
- 🎨 **リッチGUI**: WebView2対応プレビュー、リアルタイムフィルタ、ダーク/ライトテーマ
- 🌐 **多言語対応**: 日本語・英語対応、`i18n/*.json`ファイル追加による各言語拡張可能
- ⚙️ **高度な設定**: wrapMethod共存検出、出力カスタマイズ

**ツール構成:**
- **CLI**: `redscript_conflicts_report.py` - コマンドライン実行・自動化向け
- **GUI**: `gui_conflict_report.py` - インタラクティブな分析・プレビュー

---

## 🚀 クイックスタート

### GUI版（推奨）
```bash
python gui_conflict_report.py
```

### CLI版
```bash
# 基本実行（競合のみ出力、デフォルト）
python redscript_conflicts_report.py

# 全エントリ出力（競合+参照リスト）
python redscript_conflicts_report.py --mode reference

# HTML出力のみ
python redscript_conflicts_report.py --html --out-html my_report.html
```

---

## 📋 CLI リファレンス

**基本構文:**
```bash
python redscript_conflicts_report.py [オプション]
```

**主要オプション:**

| オプション                             | 説明                                                                                   | デフォルト値                                     |
|----------------------------------------|----------------------------------------------------------------------------------------|--------------------------------------------------|
| `--root <path>`                        | スキャンルート                                                                         | `r6/scripts` 自動検出                            |
| `--mode <conflicts&#124;reference>`   | 出力モード: `conflicts` (競合のみ) または `reference` (参照リスト含む)                 | `conflicts`                                      |
| `--wrap <include&#124;exclude>`       | wrapMethod共存: `include` (含める) または `exclude` (除外)                             | `exclude`                                        |
| `--lang <code>`                        | 言語コード指定 (`en`, `ja` など)                                                       | `en` または最初の利用可能言語                    |
| `--json` `--md` `--html`               | 出力形式選択                                                                           | 全形式                                           |
| `--out-json <file>`                    | JSON出力先                                                                             | `reports/redscript_conflicts.json`              |
| `--out-md <file>`                      | Markdown出力先                                                                         | `reports/redscript_conflicts.md`                |
| `--out-html <file>`                    | HTML出力先                                                                             | `reports/redscript_conflicts.html`              |

**出力例:**
```bash
# カスタム出力パス
python redscript_conflicts_report.py --html --out-html analysis/conflicts_$(date +%Y%m%d).html

# 全エントリ+wrapMethod共存を含める
python redscript_conflicts_report.py --mode reference --wrap include

# 日本語で出力
python redscript_conflicts_report.py --lang ja

# 競合のみ+wrapMethod共存（デフォルト+共存）
python redscript_conflicts_report.py --wrap include
```

**⚠️ 引数の説明:**
- `--mode`: 出力内容を決定。`conflicts` は競合のみ、`reference` は全エントリ+参照リストを出力
- `--wrap`: wrapMethod共存情報の扱い。`include` で含める、`exclude` で除外

### 🔍 競合検出仕様

**検出対象:**
- `@replaceMethod` のみを競合対象として検出
- 同一の `(クラス, メソッド)` ペアを複数MODが置換している場合

**対象外:**
- `@wrapMethod` と `@replaceGlobal` は競合扱いしない（ただし共存情報として記録）

**wrapMethod共存検出:**
- 同一対象への複数 `@wrapMethod`
- `@replaceMethod` と `@wrapMethod` の混在
- `--include-wrap-coexistence` で有効化

---

## 🎨 GUI機能

**起動:**
```bash
python gui_conflict_report.py
```

**主要機能:**

🖥️ **メイン画面**
- スキャンルート指定（`r6/scripts` 自動検出）
- 出力設定（HTML/Markdown/JSON個別制御）
- リアルタイムプレビュー

⚙️ **出力設定** (メニューバー)
- 各形式の個別ON/OFF切替
- ファイル出力の多言語対応
- 生成後の自動フォルダオープン
- 出力先パスカスタマイズ

🎨 **表示設定**
- ダーク/ライトテーマ切替
- フォントスケール調整（50%-150%）
- 言語切替（日本語/English、追加言語ファイルによる拡張対応）
- 設定の自動保存・復元

🔍 **プレビューフィルタ**
- MOD名フィルタ（カンマ区切り）
- クラス名部分一致
- 重要度別フィルタ（Critical/High/Medium/Low）
- リアルタイム反映（デバウンス処理）

## 📊 影響度評価システム

REDscript-Conflict-Reporter は独自のヒューリスティック分析により、競合の重要度を自動判定します。

### 重要度分類

| レベル           | 説明                                       | 閾値      |
|------------------|--------------------------------------------|-----------|
| **Critical**     | 高確率のコアシステム破損                   | ≥95点     |
| **High**         | 目立つ不具合が起きやすい                   | ≥70点     |
| **Medium**       | 限定的・条件付き問題の可能性               | ≥45点     |
| **Low**          | 軽微または外観レベルのリスク               | <45点     |

### 症状分類

競合の影響領域を以下のカテゴリで自動分類：

| 症状コード       | 影響領域             | 説明                                              |
|------------------|----------------------|---------------------------------------------------|
| `uiHud`          | UI/HUD               | 画面表示・HUD の不整合やちらつき                  |
| `player`         | プレイヤー           | 能力値・装備・プレイヤー挙動の副作用              |
| `vehicle`        | 乗り物               | 乗り物の操作感や振る舞いへの影響                  |
| `quest`          | クエスト             | クエスト進行・フラグ・ジャーナル状態のリスク      |
| `inventory`      | インベントリ         | アイテム一覧・所持管理の不整合                    |
| `damage`         | 戦闘                 | ダメージ計算・戦闘バランスの変動                  |
| `generic`        | 一般                 | その他の一般的な不安定要素                        |

### 評価要素

影響度の算出には以下の要素を考慮：

- **MOD数**: 競合に関与するMOD数（1MODあたり10点）
- **クラス重要度**: システムクラス（PlayerPuppet等）への高重み付け
- **メソッド重要度**: 重要メソッド（OnUpdate等）への高重み付け
- **シグネチャ複雑度**: 引数数・戻り値による複雑度評価
- **wrapMethod共存**: 同一対象への`@wrapMethod`存在による加算

### カスタマイズ

設定ファイル `assets/impact_config.json` で評価基準をカスタマイズ可能：

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

## 💾 システム要件とインストール

### 実行ファイル（.exe）版

**最小要件：**
- **OS**: Windows 10 (バージョン1809以降) / Windows 11
- **アーキテクチャ**: x64 (64bit)
- **メモリ**: 512 MB RAM最小、1 GB推奨
- **ストレージ**: 50 MB以上の空き容量
- **ディスプレイ**: 1024x768解像度以上

**オプション（GUIエクスペリエンス向上）：**
- **WebView2 Runtime**: Microsoft Edge WebView2 Runtime（リッチHTMLプレビュー用）
  - Windows 10/11には通常プリインストール済み
  - ダウンロード: https://developer.microsoft.com/microsoft-edge/webview2/
- **インターネット接続**: WebView2 Runtimeダウンロード用（未インストールの場合）

**注意**: 実行ファイルは自己完結型で、Pythonのインストールは不要です。

### Pythonソース版

- **Python**: 3.8以上
- **OS**: Windows 10/11（WebView2対応）、Linux、macOS
- **必須パッケージ**: 標準ライブラリのみ
- **推奨パッケージ**: `tkwebview2`（WebView2サポート）

### セットアップ

1. **リポジトリクローン**
   ```bash
   git clone https://github.com/SaganoKei/REDscript-Conflict-Reporter.git
   cd REDscript-Conflict-Reporter
   ```

2. **依存関係インストール（オプション）**
   ```bash
   # 開発環境
   pip install -r requirements-dev.txt

   # GUI用WebView2サポート（推奨）
   pip install tkwebview2
   ```

3. **動作確認**
   ```bash
   # CLI版テスト
   python redscript_conflicts_report.py --help

   # GUI版起動
   python gui_conflict_report.py
   ```

### 実行形式の作成

**PyInstaller使用（単体exe）:**
```bash
# GUI版（推奨）
python -m PyInstaller REDscriptConflictReporter.spec

# フォルダ版
python -m PyInstaller REDscriptConflictReporter_onedir.spec
```

配布物：`dist/REDscriptConflictReporter.exe`

---

## 🎯 使用方法

### 基本ワークフロー

1. **Cyberpunk 2077 ゲームフォルダ**を開く
2. **GUI起動** または **CLI実行**
3. **スキャンルート**を `r6/scripts` に設定
4. **レポート生成**実行
5. **競合確認**と**影響度評価**

### ディレクトリ構造例

```
Cyberpunk 2077/
├── r6/scripts/          # スキャン対象
│   ├── ModA/
│   ├── ModB/
│   └── ModC/
└── reports/             # 出力先（自動作成）
    ├── redscript_conflicts.html
    ├── redscript_conflicts.md
    └── redscript_conflicts.json
```

### 推奨設定

**GUI初回設定:**
- ✅ **プレビュー（HTML）**: 有効
- ✅ **wrapMethod共存**: 有効
- ✅ **影響度フィルタ**: Critical/High のみ
- ✅ **自動フォルダオープン**: 有効

**CLI自動化:**
```bash
# 週次競合チェック（cron/タスクスケジューラ）
python redscript_conflicts_report.py --conflicts-only --html
```

---

## 📖 出力形式詳細

### HTML レポート
- **リッチプレビュー**: WebView2対応の詳細表示
- **影響度バッジ**: カラー分類・ツールチップ
- **インタラクティブ要素**: 折りたたみ・フィルタ
- **テーマ対応**: ダーク/ライトモード

### Markdown レポート
- **GitHub対応**: Issue・PR・Wiki投稿用
- **プレーンテキスト**: エディタ・IDE表示
- **構造化**: 見出し・リスト・テーブル

### JSON レポート
- **プログラム処理**: API・自動解析用
- **完全情報**: 全競合・統計・メタデータ
- **多言語対応**: ローカライズブロック（オプション）
- **影響度情報**: severity/message/baseline データ

### wrapMethod共存レポート

同一メソッドへの複数アプローチを検出：

- **wrapMethod重複**: 複数MODが同一メソッドをwrap
- **replace-wrap混在**: replaceとwrapの同時存在
- **影響度加算**: 共存による複雑度ボーナス

---

## ⚙️ 設定・カスタマイズ

### 設定ファイル

**場所:**
- デフォルト: `redscript_conflict_gui.json`
- カスタム: メニュー → 出力設定 → 設定ファイル

**主要設定項目:**
```json
{
  "lang": "ja",                    // 言語（ja/en）
  "dark_mode": false,              // ダークモード
  "font_scale": 1.0,               // フォント倍率
  "enable_preview": true,          // HTMLプレビュー
  "include_wrap": true,            // wrapMethod共存
  "localize_output": true,         // 出力多言語化
  "auto_open": true               // 完了後フォルダオープン
}
```

### 影響度設定

**カスタム設定:** `assets/impact_config.json`

**環境変数:** `REDCONFLICT_IMPACT_CONFIG=path/to/config.json`

**設定例:**
```json
{
  "thresholds": {
    "critical": 100,     // より厳しい閾値
    "high": 80,
    "medium": 50
  },
  "weights": {
    "per_mod": 15,       // MOD数重み増加
    "wrap_coexistence": 25   // 共存重み増加
  }
}
```

### 🌐 国際化・言語拡張

**対応言語:**
- 日本語 (`ja.json`)
- 英語 (`en.json`)

**新しい言語の追加:**
1. `i18n/` フォルダに新しい言語ファイルを作成（例：`fr.json`, `de.json`, `ko.json`）
2. 既存の `ja.json` または `en.json` をテンプレートとして使用
3. 全ての翻訳キーに対応する値を翻訳
4. アプリケーションが自動的に新しい言語を検出・利用

**言語ファイル例（`fr.json`）:**
```json
{
  "app.title": "REDscript Conflict Reporter",
  "scan.root": "Racine de scan (r6/scripts)",
  "actions.generate": "Générer le rapport",
  "theme.dark": "Sombre",
  "theme.light": "Clair"
}
```

**フォント設定（言語固有）:**
各言語ファイルで推奨フォントを指定可能：
```json
{
  "preferredFonts": ["Noto Sans JP", "Yu Gothic UI", "Meiryo UI"]
}
```

---

## 🔧 トラブルシューティング

### よくある問題

**Q: WebView2でプレビューが表示されない**
```bash
# 対処法：WebView2ランタイムインストール
# または tkwebview2 パッケージ確認
pip install tkwebview2
```

**Q: 日本語フォントが表示されない**
```bash
# 解決策：フォント設定変更
メニュー → 表示設定 → フォント → "Noto Sans JP" 選択
```

**Q: 権限エラーで出力できない**
```bash
# 対処法：出力先変更
メニュー → 出力設定 → 出力先フォルダ変更
```

**Q: CLIで文字化けが発生**
```bash
# Windows PowerShell
chcp 65001  # UTF-8設定

# Command Prompt
python redscript_conflicts_report.py --html  # HTML推奨
```

### パフォーマンス最適化

**大規模MOD環境（100+MOD）:**
- ✅ `--conflicts-only` フラグ使用
- ✅ プレビューフィルタ活用
- ✅ JSON出力のみに限定

**メモリ不足時:**
- ✅ プレビュー無効化
- ✅ フォントスケール縮小
- ✅ 一時ファイル定期削除

### デバッグ・ログ

**詳細ログ出力:**
```bash
# 環境変数設定
set RCR_DEBUG=1
python gui_conflict_report.py
```

**ログファイル場所:**
- Windows: `%TEMP%/redscript_conflict_*.log`
- Linux/macOS: `/tmp/redscript_conflict_*.log`

---

## 🚀 高度な使用例

### CI/CD統合

**GitHub Actions例:**
```yaml
- name: MOD Conflict Check
  run: |
    python redscript_conflicts_report.py --conflicts-only --json
    if [ -s reports/redscript_conflicts.json ]; then
      echo "⚠️ 競合検出！" >> $GITHUB_STEP_SUMMARY
    fi
```

### バッチ処理

**PowerShell自動化:**
```powershell
# 複数プロファイルの一括チェック
$profiles = @("Profile1", "Profile2", "Profile3")
foreach ($profile in $profiles) {
    python redscript_conflicts_report.py --root "Games/$profile/r6/scripts" --out-html "reports/$profile.html"
}
```

### 結果解析

**JSON解析例 (Python):**
```python
import json

with open('reports/redscript_conflicts.json') as f:
    report = json.load(f)

critical_conflicts = [
    c for c in report['conflicts']
    if c['impact_severity'] == 'Critical'
]

print(f"重大競合: {len(critical_conflicts)}件")
```

---

## 📞 サポート・コミュニティ

### バグ報告・機能要求

- **GitHub Issues**: [REDscript-Conflict-Reporter/issues](https://github.com/SaganoKei/REDscript-Conflict-Reporter/issues)
- **テンプレート**: バグ報告・機能要求用テンプレート提供

### 貢献・開発参加

1. **Fork** → **Clone** → **Branch作成**
2. **テスト実行**: `pytest tests/`
3. **Pull Request** 作成

### ライセンス

MIT License - 詳細は `LICENSE` ファイル参照

---

## 📋 更新履歴

最新の変更点は [Releases](https://github.com/SaganoKei/REDscript-Conflict-Reporter/releases) ページで確認してください。

### 主要マイルストーン

- **v0.1.0**: 初期リリース・CLI基本機能・GUI WebView2対応・多言語化・影響度評価システム

---



---

## � インストール・環境構築