"""
REDscript conflict scanner (CLI core).

This module scans .reds files for annotations like @replaceMethod and @wrapMethod,
builds a structured JSON report, and can write Markdown/HTML summaries. The outputs
are English-only here. The GUI layer can localize its preview and, optionally, the
saved files; when GUI localization is OFF, it reuses the same writers so results match
the CLI.

Key functions:
- scan_file(path): parse a single .reds file and extract annotation → function pairs.
- build_report(root): aggregate entries across the tree and detect conflicts.
- write_markdown/write_html: delegate to shared, GUI-agnostic writers for parity.

Data model (JSON report):
{
    "scanned_root": str,                # absolute path scanned
    "files_scanned": int,               # number of .reds files processed
    "entries": [                        # every annotation matched to a function
        {
            "annotation": "replaceMethod"|"wrapMethod"|"replaceGlobal",
            "class": str,                  # class name or '<global>'
            "method": str,                 # function name
            "func_sig": str,               # function signature (best-effort)
            "file": str,                   # absolute path
            "relpath": str,                # relative path from root (added later)
            "mod": str,                    # top-level folder under root (added later)
            "line": int                    # line number of the annotation
        }, ...
    ],
    "annotation_counts": {"replaceMethod": int, "wrapMethod": int, "replaceGlobal": int},
    "conflicts": [
        {
            "class": str,
            "method": str,
            "count": int,
            "mods": [str],                 # unique mod folders that touch this method
            "occurrences": [entry, ...]    # entries contributing to the conflict
        }, ...
    ]
}
"""

import argparse
import json
import re
import os
from pathlib import Path
from collections import defaultdict, Counter
from builders.redscript_report_common import write_markdown as write_md_common, write_html as write_html_common
try:
    from common.common_impact import compute_impact_unified, get_default_impact_config  # type: ignore
except Exception:  # pragma: no cover - extremely unlikely
    compute_impact_unified = None  # type: ignore
try:
    from common.common_i18n import localize_impact_placeholders as _loc_impact  # type: ignore
except Exception:  # pragma: no cover
    def _loc_impact(text, tr):  # type: ignore
        return text

# ---------------- Impact augmentation utility (defined early so main can call safely) -----------------
def _augment_json_with_impact(report: dict, tr):  # pragma: no cover - runtime exercised
    """Attach impact severity/message(+localized) to conflict arrays.

    Always active (flag removed):
      impact_severity
      impact_message (raw i18n tokens)
      impact_message_localized (translated string; falls back to raw tokens)
    """
    if not compute_impact_unified:
        return
    try:
        _impact_cfg = get_default_impact_config()
    except Exception:
        _impact_cfg = None
    def _apply(group: dict, *, wrap: bool):
        try:
            if not compute_impact_unified:  # double guard for type checkers
                raise RuntimeError('impact unavailable')
            cls = group.get('class', '')
            meth = group.get('method', '')
            mods = group.get('mods') or []
            occs = group.get('occurrences') or group.get('occurrences_replace') or []
            impact = compute_impact_unified(cls, meth, mods, occs, wrap_coexist=wrap, config=_impact_cfg)
            raw_msg = impact.get('message', '')
            group['impact_severity'] = impact.get('severity', '')
            group['impact_message'] = raw_msg
            # Baseline (no wrap bonus) variant
            try:
                base_impact = compute_impact_unified(cls, meth, mods, occs, wrap_coexist=False, config=_impact_cfg)
            except Exception:
                base_impact = {'severity': group['impact_severity'], 'message': raw_msg}
            group['impact_severity_baseline'] = base_impact.get('severity', '')
            group['impact_message_baseline'] = base_impact.get('message', '')
            try:
                group['impact_message_localized'] = _loc_impact(raw_msg, tr)
            except Exception:
                group['impact_message_localized'] = raw_msg
            try:
                group['impact_message_baseline_localized'] = _loc_impact(group['impact_message_baseline'], tr)
            except Exception:
                group['impact_message_baseline_localized'] = group['impact_message_baseline']
        except Exception:
            group.setdefault('impact_severity', '')
            group.setdefault('impact_message', '')
            group.setdefault('impact_message_localized', group.get('impact_message',''))
            group.setdefault('impact_severity_baseline', group.get('impact_severity',''))
            group.setdefault('impact_message_baseline', group.get('impact_message',''))
            group.setdefault('impact_message_baseline_localized', group.get('impact_message_baseline',''))
    for g in report.get('conflicts', []) or []:
        _apply(g, wrap=False)
    for g in report.get('wrap_coexistence', []) or []:
        _apply(g, wrap=True)
    for g in report.get('replace_wrap_coexistence', []) or []:
        _apply(g, wrap=True)

ANNOTATION_RE = re.compile(r"^\s*@(replaceMethod|wrapMethod|replaceGlobal)\s*\(([^)]*)\)\s*$")
# Capture the function name that follows a block of annotations (best-effort).
FUNC_RE = re.compile(r"\bfunc\s+([A-Za-z0-9_]+)\s*\(")
# Simple comment/empty-line filter to reduce false positives.
COMMENT_RE = re.compile(r"^\s*//|^\s*/\*|\*/\s*$")


def scan_file(path: Path):
    """Parse a .reds file and collect annotation/function pairs.

    We allow multiple annotations stacked above a function. When we encounter the
    function signature, we emit one entry per (annotation × class) pending. If an
    unrelated line appears before a function, pending annotations are cleared.
    """
    entries = []
    pending = []  # collect consecutive annotations before a func
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return entries
    for idx, line in enumerate(lines, start=1):
        m = ANNOTATION_RE.match(line)
        if m:
            ann = m.group(1)  # replaceMethod | wrapMethod | replaceGlobal
            classes = [c.strip() for c in m.group(2).split(',')] if m.group(2) else []
            if ann == 'replaceGlobal':
                classes = ['<global>']
            if not classes:
                classes = ['<unknown>']
            pending.append((ann, classes, idx))
            continue
        # skip empty/comments
        if not line.strip() or COMMENT_RE.search(line):
            continue
    # Detect function signature line
        if ' func ' in (' ' + line):
            fm = FUNC_RE.search(line)
            if fm and pending:
                method = fm.group(1)
                func_sig = line.strip()
                for ann, classes, ann_line in pending:
                    for cls in classes:
                        entries.append({
                            'annotation': ann,
                            'class': cls,
                            'method': method,
                            'func_sig': func_sig,
                            'file': str(path),
                            'line': ann_line,
                        })
                pending.clear()
            else:
                pending.clear()
        else:
            # Non-function lines clear pending to avoid associating too far
            if pending:
                # allow attribute lines (e.g. @if(...)) or other annotations; keep pending if line starts with '@'
                if not line.lstrip().startswith('@'):
                    pending.clear()
    return entries


def build_report(root: Path, collect_metrics: bool = False):
    """Scan all .reds files under root and assemble a conflict report.

    Steps:
    1) Discover .reds files.
    2) Parse each file to build 'entries'.
    3) Enrich entries with relpath & mod.
    4) Group & detect conflicts / coexistence variants.

    When collect_metrics=True a (report, metrics) tuple is returned where
    metrics is a dict of millisecond timings for phases:
      discover, parse, enrich, group, total
    Otherwise only the report dict is returned (backwards compatible).
    """
    _pc = None
    if collect_metrics:
        import time as _t
        _pc = _t.perf_counter
        t0_total = _pc()
    # Discover .reds files
    if _pc:
        t0 = _pc()
    reds_files = list(root.rglob('*.reds'))
    if _pc:
        t_discover = (_pc() - t0)
    # Parse annotations from files
    if _pc:
        t0 = _pc()
    entries = []
    for f in reds_files:
        entries.extend(scan_file(f))
    if _pc:
        t_parse = (_pc() - t0)
    # Enrich entries with relative paths and mod names
    if _pc:
        t0 = _pc()
    root = root.resolve()
    for e in entries:
        p = Path(e['file'])
        try:
            rel = p.resolve().relative_to(root)
        except Exception:
            rel = p.name
        if isinstance(rel, Path):
            rel_parts = rel.parts
            rel_str = str(rel)
        else:
            rel_parts = (str(rel),)
            rel_str = str(rel)
        mod = '<root>'
        try:
            parts = list(rel_parts)
            parts_lower = [p.lower() for p in parts]
            if 'r6' in parts_lower:
                i = parts_lower.index('r6')
                if i + 1 < len(parts_lower) and parts_lower[i + 1] == 'scripts' and i + 2 < len(parts):
                    mod = parts[i + 2]
                elif i + 1 < len(parts):
                    mod = parts[i + 1]
            elif 'scripts' in parts_lower:
                j = parts_lower.index('scripts')
                if j + 1 < len(parts):
                    mod = parts[j + 1]
                else:
                    mod = parts[0] if parts else '<root>'
            else:
                mod = parts[0] if parts else '<root>'
        except Exception:
            mod = rel_parts[0] if rel_parts else '<root>'
        e['relpath'] = rel_str
        e['mod'] = mod
    if _pc:
        t_enrich = (_pc() - t0)
    # Group entries and detect conflicts
    if _pc:
        t0 = _pc()
    by_key = defaultdict(list)
    for e in entries:
        key = (e['annotation'], e['class'], e['method'])
        by_key[key].append(e)
    conflicts = []
    wrap_coexistence = []
    replace_wrap_coexistence = []
    by_cm = defaultdict(lambda: {'replace': [], 'wrap': [], 'other': []})
    for (ann, cls, meth), lst in by_key.items():
        if ann == 'replaceMethod':
            by_cm[(cls, meth)]['replace'].extend(lst)
        elif ann == 'wrapMethod':
            by_cm[(cls, meth)]['wrap'].extend(lst)
        else:
            by_cm[(cls, meth)]['other'].extend(lst)
    for (cls, meth), kinds in by_cm.items():
        repl = kinds['replace']
        wrap = kinds['wrap']
        if repl and len({x['file'] for x in repl}) > 1:
            mods = sorted({x.get('mod', '<unknown>') for x in repl})
            conflicts.append({'class': cls, 'method': meth, 'count': len(repl), 'mods': mods, 'occurrences': repl})
        if wrap and len({x['file'] for x in wrap}) > 1:
            mods_w = sorted({x.get('mod', '<unknown>') for x in wrap})
            wrap_coexistence.append({
                'class': cls,
                'method': meth,
                'wrap_count': len(wrap),
                'mods': mods_w,
                'occurrences': wrap,
            })
        if repl and wrap:
            mods_r = sorted({x.get('mod', '<unknown>') for x in repl})
            mods_w = sorted({x.get('mod', '<unknown>') for x in wrap})
            replace_wrap_coexistence.append({
                'class': cls,
                'method': meth,
                'replace_count': len(repl),
                'wrap_count': len(wrap),
                'mods_replace': mods_r,
                'mods_wrap': mods_w,
                'occurrences_replace': repl,
                'occurrences_wrap': wrap,
            })
    ann_counts = Counter(e['annotation'] for e in entries)
    json_report = {
        'scanned_root': str(root.resolve()),
        'files_scanned': len(reds_files),
        'entries': entries,
        'annotation_counts': ann_counts,
        'conflicts': conflicts,
        'wrap_coexistence': wrap_coexistence,
        'replace_wrap_coexistence': replace_wrap_coexistence,
    }
    if collect_metrics and _pc:
        t_total = (_pc() - t0_total)
        metrics = {
            'discover': t_discover * 1000.0,
            'parse': t_parse * 1000.0,
            'enrich': t_enrich * 1000.0,
            'group': (_pc() - t0) * 1000.0,  # grouping and conflict detection duration
            'total': t_total * 1000.0,
            'files': len(reds_files),
            'entries': len(entries),
        }
        return json_report, metrics
    return json_report


def write_markdown(report: dict, out_md: Path, conflicts_only: bool = False, include_reference: bool = False):
    # Delegate to shared, GUI-agnostic writer
    return write_md_common(report, out_md, conflicts_only=conflicts_only, include_reference=include_reference)


def write_html(report: dict, out_html: Path, conflicts_only: bool = False, include_reference: bool = False, dark: bool = False, lang: str | None = None):
    # Delegate to shared, GUI-agnostic writer; propagate language so impact symptom keys localize.
    if lang:
        try:
            opts = report.setdefault('_options', {})
            opts['lang'] = lang
        except Exception:
            pass
    return write_html_common(report, out_html, conflicts_only=conflicts_only, include_reference=include_reference, dark=dark, lang=lang)  # type: ignore[arg-type]


def main():
    # Initial plain English description, replaced after language loading if needed
    ap = argparse.ArgumentParser(description='Scan redscript annotations and report conflicts')
    ap.add_argument('--root', default=str(Path('r6/scripts').resolve()), help='Root directory to scan (default: r6/scripts)')

    # Mode selection: conflicts vs reference
    ap.add_argument('--mode', choices=['conflicts', 'reference'], default='conflicts',
                    help='Output mode: conflicts (conflicts only, default) or reference (include reference list)')

    # wrapMethod coexistence selection
    ap.add_argument('--wrap', choices=['include', 'exclude'], default='exclude',
                    help='wrapMethod coexistence handling: include or exclude (default)')

    # Language selection: single --lang <code> (codes derived from i18n/*.json)
    i18n_dir = Path(__file__).parent / 'i18n'
    available_langs = sorted([p.stem for p in i18n_dir.glob('*.json')])
    ap.add_argument('--lang', choices=available_langs, help='Language code to use (default: en or first available)')

    # Output selection flags: if none specified, all are enabled
    ap.add_argument('--json', action='store_true', help='Write JSON report')
    ap.add_argument('--md', action='store_true', help='Write Markdown report')
    ap.add_argument('--html', action='store_true', help='Write HTML report')
    # Output paths (filenames aligned with GUI defaults)
    ap.add_argument('--out-json', default='reports/redscript_conflicts.json', help='Path to write JSON report')
    ap.add_argument('--out-md', default='reports/redscript_conflicts.md', help='Path to write Markdown report')
    ap.add_argument('--out-html', default='reports/redscript_conflicts.html', help='Path to write HTML report')

    args = ap.parse_args()

    # Language handling placeholder: at present only English writers exist. We keep the flag so
    # scripts or launchers can already pass --en; later additional bundles (e.g. ja) can be wired.
    # If other languages are added, detect additional flags (e.g. --ja) and load translation map
    # to pass into writer functions or adapt write_* helpers.
    # Determine selected language
    if args.lang:
        _lang = args.lang
    else:
        _lang = 'en' if 'en' in available_langs else (available_langs[0] if available_langs else 'en')
    # Expose chosen lang in report via environment (optional future use)

    # Lightweight i18n loader (future-ready). Currently only en.json exists.
    def _load_lang(code: str):
        base = Path(__file__).parent / 'i18n' / f'{code}.json'
        try:
            return json.loads(base.read_text(encoding='utf-8'))
        except Exception:
            return {}
    _BUNDLE = _load_lang(_lang)
    def _(key: str):
        return _BUNDLE.get(key, key)
    # Replace parser description if key present (future other languages) and append language list
    if 'cli.desc' in _BUNDLE:
        base_desc = _(_BUNDLE['cli.desc'])
    else:
        base_desc = ap.description
    try:
        langs_text = ', '.join(available_langs)
        ap.description = f"{base_desc}\nAvailable languages: {langs_text} (use --lang <code>)"
    except Exception:
        pass

    # Determine which outputs to write. If none selected, default to all.
    # Processing order standardized as: HTML -> Markdown -> JSON (readability consistency with GUI).
    sel_any = bool(args.json or args.md or args.html)
    do_html = args.html or (not sel_any)
    do_md = args.md or (not sel_any)
    do_json = args.json or (not sel_any)

    root = Path(args.root)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_html = Path(args.out_html)
    # Ensure parent dirs exist for selected outputs only (HTML, MD, JSON order)
    if do_html:
        out_html.parent.mkdir(parents=True, exist_ok=True)
    if do_md:
        out_md.parent.mkdir(parents=True, exist_ok=True)
    if do_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)

    # collect_metrics stays False for CLI usage (backwards compatible)
    _r = build_report(root, collect_metrics=False)
    # _r is guaranteed dict when collect_metrics False
    report: dict = _r  # type: ignore[assignment]

    # Convert new argument format to legacy boolean flags
    conflicts_only = (args.mode == 'conflicts')
    include_reference = (args.mode == 'reference')
    include_wrap_coexistence = (args.wrap == 'include')

    # Attach output options for downstream writers
    report['_options'] = {
        'include_wrap_coexistence': include_wrap_coexistence,
        'lang': _lang,
    }
    # Optionally strip coexistence arrays from JSON when disabled
    if not include_wrap_coexistence:
        report.pop('wrap_coexistence', None)
        report.pop('replace_wrap_coexistence', None)

    # Determine effective mode based on new argument format
    effective_conflicts_only = conflicts_only
    effective_include_reference = include_reference

    # If conflicts-only mode, trim non-conflict details in JSON for compactness
    if effective_conflicts_only:
        trimmed = {
            'scanned_root': report['scanned_root'],
            'files_scanned': report['files_scanned'],
            'annotation_counts': report['annotation_counts'],
            'conflicts': report['conflicts'],
            'wrap_coexistence': report.get('wrap_coexistence', []),
            'replace_wrap_coexistence': report.get('replace_wrap_coexistence', []),
        }
        # Add impact fields to output
        try:
            _augment_json_with_impact(trimmed, _)
        except Exception:
            pass
        # Write in order: HTML -> MD -> JSON
        if do_html:
            write_html(report, out_html, conflicts_only=True, include_reference=False, dark=False, lang=_lang)
        if do_md:
            # lang parameter propagated via _options for compatibility with legacy signatures
            write_markdown(report, out_md, conflicts_only=True, include_reference=False)
        if do_json:
            trimmed['_options'] = report.get('_options', {})
            out_json.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        # Write in order: HTML -> MD -> JSON (include-reference mode)
        if do_html:
            write_html(report, out_html, conflicts_only=False, include_reference=effective_include_reference, dark=False, lang=_lang)
        if do_md:
            write_markdown(report, out_md, conflicts_only=False, include_reference=effective_include_reference)
        if do_json:
            try:
                _augment_json_with_impact(report, _)
            except Exception:
                pass
            out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    # Print notices in order: HTML -> MD -> JSON
    if do_html:
        print(f"Written: {out_html}")
    if do_md:
        print(f"Written: {out_md}")
    if do_json:
        print(f"Written: {out_json}")


if __name__ == '__main__':
    main()
