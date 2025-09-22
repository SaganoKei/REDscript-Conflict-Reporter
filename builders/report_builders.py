"""Common report builders (localization-aware) shared by GUI and CLI.

Currently exposes build_markdown which reproduces the existing English CLI
output when called with the identity translator (lambda k: k) and also supports
localization when a translation function is supplied.

Design goals:
- Zero GUI dependencies.
- Deterministic ordering (sorted by class, method).
- Feature flag parity via report['_options'] (include_wrap_coexistence boolean).
- Backwards compatibility: When no translator or identity translator is used,
  output matches previous write_markdown implementation byte-for-byte except
  for trailing whitespace normalization (intentional single '\n' handling).

Difference / convergence notes (2025-09):
    - GUI preview originally contained an internal impact heuristic; a simplified
        variant (default_impact_assessment) is exposed here so CLI full HTML can
        display Severity/Impact columns with approximate parity. The GUI may still
        invoke its richer heuristic via impact_fn override.
    - Legend multi-line lines: if not pre-injected by GUI (localized bundle), the
        CLI/full builder injects English defaults for consistent layout.
    - Template/CSS loader: CLI uses a reduced discovery set; future work could
        unify with GUI's broader asset search to eliminate any residual styling
        differences when external template dirs are arranged differently.
    - Anchors: a shared make_conflict_anchor ensures stable IDs across both
        environments (GUI may still override via its own function if needed).
    - Localization: CLI defaults to a minimal English translator; supplying a
        richer translator (loaded from i18n JSON) will yield near-identical output
        to GUI exports except for any preview-only elements intentionally omitted.
"""
from __future__ import annotations
from pathlib import Path
from collections import defaultdict
from typing import Callable, Dict, List, Any
import re
from common.common_impact import (
    compute_impact_unified,
    classify_conflict_symptom,
    symptom_label,
    _IMPACT_DEFAULT_CONFIG as _IMPACT_DEFAULT_CONFIG,
    get_default_impact_config as _get_default_impact_config,
)
from common.common_util import make_conflict_anchor, method_has_wrap  # moved anchor + wrap detection helper
from builders.report_sections import build_wrap_coexistence_index  # new shared helper
from common.common_i18n import localize_impact_placeholders as _ci_localize_impact_placeholders  # centralized impact msg localization
from pathlib import Path as _P
try:  # Prefer shared i18n utilities if present
    from common.common_i18n import make_translator as _ci_make_translator, load_bundles as _ci_load_bundles, Translator as _CITranslator  # type: ignore
except Exception:  # fallback minimal translator (identity)
    _CITranslator = Callable[[str], str]  # type: ignore
    Translator = Callable[[str], str]  # define local alias
    def _ci_make_translator(lang: str | None):  # type: ignore
        return lambda k: k
    def _ci_load_bundles():  # type: ignore
        return {}


def _legacy_full_html_cli(report: Dict[str, Any], tr: Callable[[str], str] | None = None, *,
                          dark: bool = False,
                          conflicts_only: bool = False,
                          include_reference: bool = False) -> str:
    """Legacy self-contained (inline CSS) CLI HTML builder.

    Kept for fallback resilience when template/CSS discovery fails. New unified
    build_full_html_cli delegates to build_full_html_gui (inline_css=True).
    """
    _ = tr or (lambda k: k)
    try:
        import html as _html
        def esc(x):
            return _html.escape(str(x))
    except Exception:
        def esc(x):  # type: ignore
            return str(x)

    # CSS identical to legacy writer
    css = (
        "body{font-family:Segoe UI,Arial,sans-serif;margin:0;padding:12px;" +
        ("background:#1e1e1e;color:#e6e6e6;" if dark else "background:#ffffff;color:#000000;") +
        "} h1,h2,h3{margin:10px 0;} h1{font-size:1.6em;} h2{font-size:1.3em;} h3{font-size:1.1em;}" \
        " a{color:" + ("#4aa3ff" if dark else "#004a99") + ";text-decoration:none;} a:hover{text-decoration:underline;}" \
        " .meta{opacity:0.85;} .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:0.9em;" +
        ("background:#3a3d41;color:#fff;" if dark else "background:#e6e6e6;color:#333;") +
        "margin-left:6px;} code,pre{" + ("background:#2d2d30;color:#e6e6e6;" if dark else "background:#f6f6f6;color:#333;") + "padding:2px 4px;border-radius:4px;}" \
        " table{border-collapse:collapse;width:100%;margin:8px 0;} th,td{border:1px solid " + ("#3c3c3c" if dark else "#dcdcdc") + ";padding:6px;text-align:left;} th{background:" + ("#2d2d30;color:#e6e6e6;" if dark else "#f0f0f0;color:#333;") + ";}" \
        " .plink{opacity:0.45;margin-left:6px;font-size:0.85em;} .plink:hover{opacity:0.9;}" \
        " ul{margin-top:4px;} li{line-height:1.25em;margin:2px 0;} .file{font-family:Consolas,monospace;}"
    )

    def _make_method_id(cls: str, meth: str) -> str:
        base = f"{cls}.{meth}".lower()
        base = re.sub(r'[^a-z0-9]+', '-', base).strip('-')
        return f"m-{base}" if base else "m-unknown"

    def _make_occ_id(cls: str, meth: str, idx: int) -> str:
        base = f"{cls}.{meth}".lower()
        base = re.sub(r'[^a-z0-9]+', '-', base).strip('-')
        return f"occ-{base}-{idx}" if base else f"occ-unknown-{idx}"

    disable_file_links = False
    try:
        disable_file_links = bool((report.get('_options') or {}).get('disable_file_links', False))
    except Exception:
        disable_file_links = False
    include_wrap = True
    try:
        include_wrap = bool((report.get('_options') or {}).get('include_wrap_coexistence', True))
    except Exception:
        include_wrap = True

    header = _('report.header') if tr else 'REDscript Conflict Report'
    if header == 'report.header':  # missing key fallback
        header = 'REDscript Conflict Report'
    scanned_label = _('report.scannedRoot') if tr else 'Scanned root:'
    if scanned_label == 'report.scannedRoot':
        scanned_label = 'Scanned root:'
    files_label = _('report.filesScanned') if tr else 'Files scanned:'
    if files_label == 'report.filesScanned':
        files_label = 'Files scanned:'
    conflicts_heading = _('report.conflicts') if tr else 'Conflicts (multiple files @replaceMethod the same method)'
    if tr:
        conflicts_heading = conflicts_heading.split('(')[0].strip()
    no_conflicts = _('report.noConflicts') if tr else 'No conflicts detected.'
    if no_conflicts == 'report.noConflicts':
        no_conflicts = 'No conflicts detected.'
    wrap_heading = _('report.wrapCoexist') if tr else 'wrapMethod Coexistence (@wrapMethod by multiple files)'
    if wrap_heading == 'report.wrapCoexist':
        wrap_heading = 'wrapMethod Coexistence (@wrapMethod by multiple files)'
    rw_heading = _('report.replaceWrapCoexist') if tr else 'Replace + wrapMethod Coexistence (same target)'
    if rw_heading == 'report.replaceWrapCoexist':
        rw_heading = 'Replace + wrapMethod Coexistence (same target)'
    ref_heading = _('report.reference') if tr else 'All @replaceMethod (Reference)'
    if ref_heading == 'report.reference':
        ref_heading = 'All @replaceMethod (Reference)'
    target_label = _('report.targetMethod') if tr else 'Target method'
    if target_label == 'report.targetMethod':
        target_label = 'Target method'

    parts: List[str] = []
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append(f"<style>{css}</style></head><body>")
    parts.append("<a id='top'></a>")
    parts.append(f"<h1>{esc(header)}</h1>")
    parts.append(f"<div class='meta'>{esc(scanned_label)} <code>{esc(report.get('scanned_root',''))}</code> | {esc(files_label)} {int(report.get('files_scanned',0))}</div>")
    ac = report.get('annotation_counts', {}) or {}
    if ac:
        badges = " ".join([f"<span class='badge'>{esc(k)}: {int(v)}</span>" for k, v in sorted(ac.items())])
        parts.append(f"<div class='meta'>Annotation counts: {badges}</div>")

    conflicts = report.get('conflicts', []) or []
    parts.append(f"<h2>{esc(conflicts_heading)}</h2>")
    if not conflicts:
        parts.append(f"<p>{esc(no_conflicts)}</p>")
    else:
        parts.append("<table><thead><tr><th>#</th><th>Class.Method</th><th>MODs</th><th>Count</th></tr></thead><tbody>")
        for idx, c in enumerate(sorted(conflicts, key=lambda x: (x.get('class',''), x.get('method',''))), start=1):
            mods = c.get('mods', []) or []
            mid = _make_method_id(c.get('class',''), c.get('method',''))
            parts.append(f"<tr><td>{idx}</td><td><a href='#{mid}'>{esc(c.get('class',''))}.{esc(c.get('method',''))}</a></td><td>{len(set(mods))}</td><td>{int(c.get('count',0))}</td></tr>")
        parts.append("</tbody></table>")
        for c in sorted(conflicts, key=lambda x: (x.get('class',''), x.get('method',''))):
            cls = esc(c.get('class',''))
            meth = esc(c.get('method',''))
            occs = c.get('occurrences') or []
            sig = ''
            if occs:
                sig = esc(occs[0].get('func_sig') or '')
            mid = _make_method_id(cls, meth)
            parts.append(f"<h3 id='{mid}'>{cls}.{meth} <a class='plink' href='#{mid}'>¶</a></h3>")
            if sig:
                parts.append(f"<div>{esc(target_label)}: <code>{sig}</code></div>")
            parts.append("<ul>")
            for o_idx, occ in enumerate(occs, start=1):
                mod = esc(occ.get('mod', '<unknown>'))
                rel_raw = occ.get('relpath', occ.get('file',''))
                rel = esc(rel_raw)
                line_no = int(occ.get('line', 0))
                oid = _make_occ_id(cls, meth, o_idx)
                if (not disable_file_links) and rel_raw:
                    p = _P(report.get('scanned_root','')) / rel_raw
                    url = _P(p).resolve().as_posix()
                    parts.append(f"<li id='{oid}'>[{mod}] <a class='file' href='file:///{esc(url)}'>{rel}</a>:{line_no}</li>")
                else:
                    parts.append(f"<li id='{oid}'>[{mod}] {rel}:{line_no}</li>")
            parts.append("</ul>")

    wrap_co = report.get('wrap_coexistence', []) or []
    if include_wrap and wrap_co:
        parts.append(f"<h2>{esc(wrap_heading)}</h2>")
        parts.append("<table><thead><tr><th>#</th><th>Class.Method</th><th>MODs</th><th>Wrap Count</th></tr></thead><tbody>")
        for idx, c in enumerate(sorted(wrap_co, key=lambda x: (x.get('class',''), x.get('method',''))), start=1):
            mid = _make_method_id(c.get('class',''), c.get('method',''))
            parts.append(f"<tr><td>{idx}</td><td><a href='#{mid}'>{esc(c.get('class',''))}.{esc(c.get('method',''))}</a></td><td>{len(set(c.get('mods',[])))}</td><td>{int(c.get('wrap_count',0))}</td></tr>")
        parts.append("</tbody></table>")
        for c in sorted(wrap_co, key=lambda x: (x.get('class',''), x.get('method',''))):
            mid = _make_method_id(c.get('class',''), c.get('method',''))
            parts.append(f"<h3 id='{mid}'>{esc(c.get('class',''))}.{esc(c.get('method',''))} <a class='plink' href='#{mid}'>¶</a></h3>")
            parts.append("<ul>")
            for o_idx, occ in enumerate(c.get('occurrences') or [], start=1):
                mod = esc(occ.get('mod', '<unknown>'))
                rel_raw = occ.get('relpath', occ.get('file',''))
                rel = esc(rel_raw)
                line_no = int(occ.get('line', 0))
                oid = _make_occ_id(c.get('class',''), c.get('method',''), o_idx)
                if (not disable_file_links) and rel_raw:
                    p = _P(report.get('scanned_root','')) / rel_raw
                    url = _P(p).resolve().as_posix()
                    parts.append(f"<li id='{oid}'>[{mod}] <a class='file' href='file:///{esc(url)}'>{rel}</a>:{line_no}</li>")
                else:
                    parts.append(f"<li id='{oid}'>[{mod}] {rel}:{line_no}</li>")
            parts.append("</ul>")

    rw_co = report.get('replace_wrap_coexistence', []) or []
    if include_wrap and rw_co:
        parts.append(f"<h2>{esc(rw_heading)}</h2>")
        parts.append("<table><thead><tr><th>#</th><th>Class.Method</th><th>Replace</th><th>Wrap</th></tr></thead><tbody>")
        for idx, c in enumerate(sorted(rw_co, key=lambda x: (x.get('class',''), x.get('method',''))), start=1):
            mid = _make_method_id(c.get('class',''), c.get('method',''))
            parts.append(f"<tr><td>{idx}</td><td><a href='#{mid}'>{esc(c.get('class',''))}.{esc(c.get('method',''))}</a></td><td>{int(c.get('replace_count',0))}</td><td>{int(c.get('wrap_count',0))}</td></tr>")
        parts.append("</tbody></table>")

    if (not conflicts_only) and include_reference:
        repl_entries = [e for e in report.get('entries', []) if e.get('annotation') == 'replaceMethod']
        grouped: Dict[tuple[str,str], List[dict]] = defaultdict(list)
        for e in repl_entries:
            grouped[(e.get('class',''), e.get('method',''))].append(e)
        parts.append(f"<h2>{esc(ref_heading)}</h2>")
        for (cls, meth) in sorted(grouped.keys()):
            mods = sorted({x.get('mod','<unknown>') for x in grouped[(cls, meth)]})
            mod_str = ", ".join(mods)
            mid = _make_method_id(cls, meth)
            parts.append(f"<h3 id='{mid}'>{esc(cls)}.{esc(meth)} — MODs: {esc(mod_str)} <a class='plink' href='#{mid}'>¶</a></h3>")
            parts.append("<ul>")
            for o_idx, e in enumerate(grouped[(cls, meth)], start=1):
                rel_raw = e.get('relpath', e.get('file',''))
                rel = esc(rel_raw)
                mod = esc(e.get('mod', '<unknown>'))
                sig = esc(e.get('func_sig',''))
                line_no = int(e.get('line',0))
                oid = _make_occ_id(cls, meth, o_idx)
                if (not disable_file_links) and rel_raw:
                    p = _P(report.get('scanned_root','')) / rel_raw
                    url = _P(p).resolve().as_posix()
                    parts.append(f"<li id='{oid}'>[{mod}] <a class='file' href='file:///{esc(url)}'>{rel}</a>:{line_no} — <code>{sig}</code></li>")
                else:
                    parts.append(f"<li id='{oid}'>[{mod}] {rel}:{line_no} — <code>{sig}</code></li>")
            parts.append("</ul>")

    parts.append("</body></html>")
    return "\n".join(parts)


def build_full_html_cli(report: Dict[str, Any], tr: Callable[[str], str] | None = None, *,
                        dark: bool = False,
                        conflicts_only: bool = False,
                        include_reference: bool = False) -> str:
    """Unified CLI full HTML builder.

    Uses GUI canonical template pipeline with inline CSS to avoid external file copying requirement.
    """
    # Late import safe: build_full_html_gui appears later in file.
    html, _used = build_full_html_gui(report, tr, dark=dark, conflicts_only=conflicts_only,
                                      include_reference=include_reference, inline_css=True, lang=None)  # type: ignore
    return html


def build_html_body_gui(report: Dict[str, Any], tr: Translator | None, *, conflicts_only: bool, include_reference: bool,
                        include_wrap: bool, disable_file_links: bool, impact_fn=None, anchor_fn=None) -> str:
    """Generate HTML body content compatible with GUI output format.

    Parameters:
      report: Scanner-generated report dictionary
      tr: Translation function (optional)
      conflicts_only/include_reference: Output scope controls
      include_wrap: Include wrap coexistence sections (equivalent to GUI var_include_wrap)
      disable_file_links: Suppress file:// links
      impact_fn: (cls,meth,mods,entries)->{'severity':str,'message':str} GUI-specific heuristic (optional)
      anchor_fn: (idx|None, cls, meth)->id generator (simple implementation if omitted)

    NOTE: Maintains structural compatibility with GUI's existing build_html_body,
    returning only the fragment before external template insertion.
    """
    _ = tr or (lambda k: k)
    scanned_root = report.get('scanned_root','')
    ann = report.get('annotation_counts') or {}

    def _anchor(idx, cls, meth):
        if anchor_fn:
            try:
                return anchor_fn(idx, cls, meth)
            except Exception:
                pass
        base = (cls + '-' + meth).lower().replace(' ', '-')
        base = ''.join(ch for ch in base if ch.isalnum() or ch in ('-','_','.'))
        return f"conf-{idx}-{base}" if idx is not None else f"conf-{base}"

    # file link helper
    from pathlib import Path as _P
    def _mk_file_link(rel: str, line: str | int):
        if not rel:
            return f"{rel}:{line}"
        if disable_file_links:
            return f"{rel}:{line}"
        try:
            p = _P(scanned_root) / rel
            url = p.resolve().as_posix()
            return f"<a class='file' href='file:///{url}'>{rel}</a>:{line}"
        except Exception:
            return f"{rel}:{line}"

    parts: List[str] = []
    # Note: Top-level <h1> is rendered by external template ({{HEADER_LABEL}}) to avoid duplication.
    parts.append(f"<div class='meta'>{_('report.scannedRoot')} <code>{scanned_root}</code> | {_('report.filesScanned')} {report.get('files_scanned',0)}</div>")
    if ann:
        badges = " ".join([f"<span class='badge'>{k}: {v}</span>" for k,v in sorted(ann.items())])
        parts.append(f"<div class='meta'>{badges}</div>")

    # Legend (keys legend.title / legend.body / legend.lines[])
    legend_lines = report.get('_localized_legend_lines')  # optional pre-injected list
    if legend_lines and isinstance(legend_lines, list):
        from html import escape as _esc
        inner = '<br>'.join(_esc(str(x)) for x in legend_lines)
        parts.append(f"<div class='legend'><b>{_('legend.title')}</b><br>{inner}</div>")
    else:
        parts.append(f"<div class='legend'><b>{_('legend.title')}</b> { _('legend.body') }</div>")

    conflicts = report.get('conflicts', []) or []
    total_conf = len(conflicts)
    conf_head = (_('report.conflicts') or 'Conflicts').split('(')[0].strip()
    parts.append(f"<h2>{conf_head} <span class='badge'>{_('summary.total')}: {total_conf}</span></h2>")
    if conflicts:
        sev_hdr = _('filters.severity')
        parts.append(f"<table><thead><tr><th>#</th><th>Class.Method</th><th>Mods</th><th>Count</th><th>{sev_hdr}</th></tr></thead><tbody>")
        for idx, c in enumerate(conflicts, start=1):
            cls = c.get('class',''); meth = c.get('method',''); mods = c.get('mods', []) or []
            entries = c.get('occurrences') or c.get('entries') or []
            # Per-method wrap detection to avoid global wrap inflation
            has_wrap = method_has_wrap(report, cls, meth)
            if impact_fn:
                # ignore provided global wrap inside impact_fn by recomputing here for accuracy
                try:
                    impact = compute_impact_unified(cls, meth, mods, entries, wrap_coexist=has_wrap)
                except Exception:
                    impact = {'severity':'','message':''}
            else:
                impact = {'severity':'','message':''}
            sev = impact.get('severity','')
            sev_key = f"filters.sev.{sev.lower()}" if sev else ''
            sev_label = _(sev_key) if sev_key else ''
            if sev_key and sev_label == sev_key:
                sev_label = sev
            # Hidden wrap tooltip: only when include_wrap option is False globally but this method actually has wrap coexistence
            hidden_wrap_tooltip = ''
            try:
                global_include_wrap = bool((report.get('_options') or {}).get('include_wrap_coexistence', True))
            except Exception:
                global_include_wrap = True
            if has_wrap and not global_include_wrap:
                tip_txt = _('impact.wrapHiddenTooltip')
                if tip_txt == 'impact.wrapHiddenTooltip':  # fallback English if key missing
                    tip_txt = 'wrapMethod coexistence exists (hidden)'
                from html import escape as _esc
                hidden_wrap_tooltip = f" title='{_esc(tip_txt)}'"
            anchor = _anchor(idx, cls, meth)
            parts.append(f"<tr><td>{idx}</td><td><a href='#{anchor}'>{cls}.{meth}</a></td><td>{len(set(mods))}</td><td>{c.get('count',0)}</td><td><span class='badge sev-{sev.lower()}'{hidden_wrap_tooltip}>{sev_label}</span></td></tr>")
        parts.append("</tbody></table>")
        for c in conflicts:
            cls = c.get('class',''); meth = c.get('method','')
            entries = c.get('occurrences') or c.get('entries') or []
            mods = c.get('mods', []) or []
            anchor = _anchor(None, cls, meth)
            parts.append(f"<div class='conflict' id='{anchor}'>")
            parts.append(f"<h3>{cls}.{meth}</h3>")
            if mods:
                parts.append(f"<div><b>Mods:</b> {', '.join(sorted(set(mods)))} </div>")
            if impact_fn:
                has_wrap = method_has_wrap(report, cls, meth)
                try:
                    impact = compute_impact_unified(cls, meth, mods, entries, wrap_coexist=has_wrap)
                except Exception:
                    impact = {'severity':'','message':''}
                # Baseline if wrap present
                if has_wrap:
                    try:
                        baseline = compute_impact_unified(cls, meth, mods, entries, wrap_coexist=False)
                    except Exception:
                        baseline = impact
                else:
                    baseline = impact
                sev2 = impact.get('severity','')
                sev2_key = f"filters.sev.{sev2.lower()}" if sev2 else ''
                sev2_label = _(sev2_key) if sev2_key else sev2
                if sev2_key and sev2_label == sev2_key:
                    sev2_label = sev2
                raw_msg = impact.get('message','') or ''
                disp_msg = _ci_localize_impact_placeholders(raw_msg, _)
                # Hidden wrap tooltip attribute (global include_wrap disabled AND method has wrap)
                try:
                    global_include_wrap = bool((report.get('_options') or {}).get('include_wrap_coexistence', True))
                except Exception:
                    global_include_wrap = True
                hidden_wrap_tooltip = ''
                if has_wrap and not global_include_wrap:
                    tip_txt = _('impact.wrapHiddenTooltip')
                    if tip_txt == 'impact.wrapHiddenTooltip':
                        tip_txt = 'wrapMethod coexistence exists (hidden)'
                    from html import escape as _esc
                    hidden_wrap_tooltip = f" title='{_esc(tip_txt)}'"
                # Main impact line
                parts.append(f"<div class='impact'><b>{_('impact.label')}</b> <span class='badge sev-{sev2.lower()}'{hidden_wrap_tooltip}>{sev2_label}</span> — {disp_msg}</div>")
                # Baseline line (only if different)
                if has_wrap:
                    try:
                        base_sev = baseline.get('severity','')
                        base_msg_raw = baseline.get('message','') or ''
                        base_msg = _ci_localize_impact_placeholders(base_msg_raw, _)
                        # Modified baseline display rule: show only when severity differs (not for message-only differences)
                        if base_sev != sev2:
                            base_key = f"filters.sev.{base_sev.lower()}" if base_sev else ''
                            base_label = _(base_key) if base_key else base_sev
                            if base_key and base_label == base_key:
                                base_label = base_sev
                            # (Optional) add tooltip to baseline too for consistency
                            parts.append(f"<div class='impact baseline'><b>{_('impact.label.baseline')}</b> <span class='badge sev-{base_sev.lower()}'{hidden_wrap_tooltip}>{base_label}</span> — {base_msg}</div>")
                    except Exception:
                        pass
            if entries:
                sig_once = entries[0].get('func_sig') or ''
                if sig_once:
                    parts.append(f"<div><b>{_('report.targetMethod')}:</b> <code>{sig_once}</code></div>")
                parts.append('<ul>')
                for e in entries:
                    rel = e.get('relpath',''); line = e.get('line',''); mod = e.get('mod','')
                    parts.append(f"<li>[{mod}] {_mk_file_link(rel, line)}</li>")
                parts.append('</ul>')
                # Inline wrap occurrences list (other mods performing @wrapMethod on this target)
                try:
                    wrap_groups = report.get('wrap_coexistence') or []
                    # gather wraps for this class.method
                    matched = [g for g in wrap_groups if g.get('class')==cls and g.get('method')==meth]
                    if matched:
                        wraps = matched[0].get('occurrences') or []
                        if wraps:
                            # Fallback heading if translation key unresolved (mirrors markdown builder logic)
                            _heading = _('conflict.wrapInlineHeading')
                            if _heading == 'conflict.wrapInlineHeading':
                                _heading = 'Other mods @wrapMethod (coexisting)'
                            parts.append(f"<div class='wrap-inline'><b>{_heading}</b></div>")
                            parts.append('<ul class=\'wrap-occurrences\'>')
                            for w in wraps:
                                w_rel = w.get('relpath',''); w_line = w.get('line',''); w_mod = w.get('mod','')
                                parts.append(f"<li>[{w_mod}] {_mk_file_link(w_rel, w_line)}</li>")
                            parts.append('</ul>')
                except Exception:
                    pass
            parts.append('</div>')

    if include_wrap:
        _wrap_idx = build_wrap_coexistence_index(report)
        wrap_co = _wrap_idx['wrap']
        if wrap_co:
            parts.append(f"<h2>{_('report.wrapCoexist')}</h2>")
            parts.append("<table><thead><tr><th>#</th><th>Class.Method</th><th>Mods</th><th>Wrap Count</th></tr></thead><tbody>")
            for idx, c in enumerate(wrap_co, start=1):
                parts.append(f"<tr><td>{idx}</td><td>{c.get('class','')}.{c.get('method','')}</td><td>{len(set(c.get('mods') or []))}</td><td>{int(c.get('wrap_count',0))}</td></tr>")
            parts.append("</tbody></table>")
            for c in wrap_co:
                parts.append(f"<h3>{c.get('class','')}.{c.get('method','')}</h3>")
                parts.append('<ul>')
                for occ in c.get('occurrences') or []:
                    parts.append(f"<li>[{occ.get('mod','')}] {_mk_file_link(occ.get('relpath',''), occ.get('line',''))}</li>")
                parts.append('</ul>')
        rw_co = _wrap_idx['replace_wrap']
        if rw_co:
            parts.append(f"<h2>{_('report.replaceWrapCoexist')}</h2>")
            parts.append("<table><thead><tr><th>#</th><th>Class.Method</th><th>Replace</th><th>Wrap</th></tr></thead><tbody>")
            for idx, c in enumerate(rw_co, start=1):
                parts.append(f"<tr><td>{idx}</td><td>{c.get('class','')}.{c.get('method','')}</td><td>{int(c.get('replace_count',0))}</td><td>{int(c.get('wrap_count',0))}</td></tr>")
            parts.append("</tbody></table>")

    if (not conflicts_only) and include_reference:
        parts.append(f"<h2>{_('report.reference')}</h2>")
        repl_entries = [e for e in report.get('entries', []) if e.get('annotation') == 'replaceMethod']
        grouped: Dict[tuple[str,str], List[dict]] = defaultdict(list)
        for e in repl_entries:
            grouped[(e.get('class',''), e.get('method',''))].append(e)
        for (cls, meth) in sorted(grouped.keys()):
            parts.append(f"<div class='conflict'><h3>{cls}.{meth}</h3>")
            sig_once = grouped[(cls, meth)][0].get('func_sig') or ''
            if sig_once:
                parts.append(f"<div><b>{_('report.targetMethod')}:</b> <code>{sig_once}</code></div>")
            parts.append('<ul>')
            for e in grouped[(cls, meth)]:
                parts.append(f"<li>[{e.get('mod','')}] {_mk_file_link(e.get('relpath',''), e.get('line',''))}</li>")
            parts.append('</ul></div>')
    return '\n'.join(parts)

# ------------------------ GUI canonical full HTML wrapper (for CLI reuse) ------------------------

# Minimal asset discovery duplicated from GUI (kept local to avoid GUI import cycle).
from common.common_assets import (load_template_and_css as _ca_load_template_and_css,
                           ensure_css_copy as _ca_ensure_css_copy,
                           discover_asset_dirs as _ca_discover_asset_dirs,
                           build_minimal_html as _build_min_html)
_FULL_ASSET_LOG_ONCE = False  # retained only for compatibility (log suppression if reused elsewhere)

def _default_en_translator(key: str) -> str:
    mapping = {
        'report.header': 'REDscript Conflicts Report',
        'report.scannedRoot': 'Scanned root:',
        'report.filesScanned': 'Files scanned:',
        'legend.title': 'Legend / Severity',
        'legend.body': 'Critical / High / Medium / Low risk summary',
        'report.conflicts': 'Conflicts',
        'summary.total': 'Total',
        'filters.severity': 'Severity',
        'filters.sev.critical': 'Critical',
        'filters.sev.high': 'High',
        'filters.sev.medium': 'Medium',
        'filters.sev.low': 'Low',
        'report.noConflicts': 'No conflicts detected',
        'impact.label': 'Impact',
        'report.targetMethod': 'Target method',
        'report.wrapCoexist': 'wrapMethod Coexistence (@wrapMethod by multiple files)',
        'report.replaceWrapCoexist': 'Replace + wrapMethod Coexistence (same target)',
        'report.reference': 'Reference (non-conflicting entries)',
    }
    return mapping.get(key, key)

# --- Shared (optional) impact heuristic hook ---
# NOTE: default_impact_assessment wrapper removed; use compute_impact_unified directly.

def _inject_legend_lines_if_missing(report: Dict[str, Any], tr: Translator):
    """Inject localized legend lines if not already present."""
    if report.get('_localized_legend_lines'):
        return

    # 1) Try to access bundle data directly for legend.lines array
    try:
        if _ci_load_bundles:
            bundles = _ci_load_bundles()
            # Determine language from translator context (best effort)
            lang = None
            # Try all available bundle languages to detect which one the translator uses
            for test_lang in bundles.keys():
                test_key = 'legend.title'
                bundle_value = bundles[test_lang].get(test_key)
                if bundle_value and tr(test_key) == bundle_value:
                    lang = test_lang
                    break

            if lang and lang in bundles:
                bundle = bundles[lang]
                legend_lines = bundle.get('legend.lines')
                if isinstance(legend_lines, list) and legend_lines:
                    report['_localized_legend_lines'] = [str(x) for x in legend_lines if x]
                    return
    except Exception:
        pass    # 2) Fallback: numbered individual keys legend.lines.0 .. legend.lines.3
    try:
        lines: list[str] = []
        for i in range(8):  # allow future extension beyond 4
            key = f'legend.lines.{i}'
            translated = tr(key)
            if translated != key:
                lines.append(translated)
            else:
                break
        if lines:
            report['_localized_legend_lines'] = lines
            return
    except Exception:
        pass

    # 3) Legacy: attempt to parse legend.body splitting by period / Japanese punctuation if localized body exists
    try:
        body = tr('legend.body')
        if body and body != 'legend.body':
            import re as _re
            # Split sentences heuristically; keep short fragments filtered
            raw_parts = _re.split(r'[。\.]+\s*', body)
            cand = [p.strip(' ・-') for p in raw_parts if len(p.strip()) > 4][:4]
            if len(cand) >= 2:  # Use only if we got meaningful segmentation
                report['_localized_legend_lines'] = cand[:4]
                return
    except Exception:
        pass

    # 4) Final English fallback
    report['_localized_legend_lines'] = [
        'Critical: very high probability of breaking core systems',
        'High: likely to cause noticeable issues',
        'Medium: situational or limited impact',
        'Low: minor / cosmetic risk'
    ]

# --- Shared impact configuration ---

def _get_impact_config_cached():
    """Get cached impact configuration for consistent usage across report builders."""
    if not hasattr(_get_impact_config_cached, '_cached_config'):
        _get_impact_config_cached._cached_config = _get_default_impact_config()
    return _get_impact_config_cached._cached_config

def _make_impact_callback(wrap_coexist: bool = False):
    """Create impact callback function with cached configuration."""
    config = _get_impact_config_cached()
    return lambda cls, meth, mods, entries: compute_impact_unified(
        cls, meth, mods, entries, wrap_coexist=wrap_coexist, config=config
    )

# --- Report builders ---

def _resolve_translator(lang: str | None, tr: Translator | None) -> Translator:
    if tr:
        return tr
    if _ci_make_translator:
        try:
            return _ci_make_translator(lang)  # type: ignore[arg-type]
        except Exception:
            pass
    return _default_en_translator
def iter_conflicts(report: Dict[str, Any], *, sort: bool = False):
    """Yield conflict dicts.

    sort=False preserves original ordering (HTML table/detail parity).
    sort=True provides stable class/method ordering (Markdown legacy format).
    """
    conflicts = (report.get('conflicts') or [])
    if sort:
        return sorted(conflicts, key=lambda x: (x.get('class',''), x.get('method','')))
    return conflicts

# ---------------- Impact profile externalization -----------------

def build_full_html_gui(report: Dict[str, Any], tr: Translator | None = None, *, dark: bool = False,
                        conflicts_only: bool = False, include_reference: bool = False,
                        inline_css: bool = False, lang: str | None = None) -> tuple[str, bool]:
    """Produce full HTML identical in structure to GUI export (template + body).

    Returns (html, used_external_template).
    When inline_css=False and template exists, writes link to external report.css (caller may copy).
    """
    # Translator precedence: explicit tr arg > lang code > default en
    _tr = _resolve_translator(lang, tr)
    # options
    include_wrap = True
    try:
        include_wrap = bool((report.get('_options') or {}).get('include_wrap_coexistence', True))
    except Exception:
        include_wrap = True
    disable_file_links = False
    try:
        disable_file_links = bool((report.get('_options') or {}).get('disable_file_links', False))
    except Exception:
        disable_file_links = False
    # body
    # Legend multi-line ensure
    try:
        _inject_legend_lines_if_missing(report, _tr)
    except Exception:
        pass
    # Impact heuristic (simplified) enable
    wrap_coexist = bool(report.get('wrap_coexistence')) or bool(report.get('replace_wrap_coexistence'))
    # Unified impact configuration
    impact_cb = _make_impact_callback(wrap_coexist=wrap_coexist)
    body_html = build_html_body_gui(report, _tr, conflicts_only=conflicts_only, include_reference=include_reference,
                                    include_wrap=include_wrap, disable_file_links=disable_file_links,
                                    impact_fn=impact_cb, anchor_fn=make_conflict_anchor)
    # Fallback localization pass centralised
    try:
        from common.common_i18n import localize_impact_placeholders as _loc_imp
        body_html = _loc_imp(body_html, _tr)
    except Exception:
        pass
    # wrap
    tpl, used_tpl, _css_inline, _chosen_dir = _ca_load_template_and_css(inline_css=inline_css)
    try:
        header = _tr('report.header')
    except Exception:
        header = 'Report'
    if not isinstance(header, str):
        try:
            header = str(header)
        except Exception:
            header = 'Report'
    theme_class = 'dark' if dark else ''
    try:
        full_html = (tpl
                     .replace('{{TITLE}}', header)
                     .replace('{{HEADER_LABEL}}', header)
                     .replace('{{THEME_CLASS}}', theme_class)
                     .replace('{{BODY}}', body_html))
    except Exception:
        full_html = '<html><body>' + body_html + '</body></html>'
    return full_html, used_tpl

def build_full_html_gui_and_copy(report: Dict[str, Any], out_path: Path, tr: Translator | None = None, *, dark: bool = False,
                                 conflicts_only: bool = False, include_reference: bool = False, lang: str | None = None) -> str:
    tpl, used_tpl, _css_inline, chosen_dir = _ca_load_template_and_css(inline_css=False)
    _tr = _resolve_translator(lang, tr)
    try:
        _inject_legend_lines_if_missing(report, _tr)
    except Exception:
        pass
    wrap_coexist = bool(report.get('wrap_coexistence')) or bool(report.get('replace_wrap_coexistence'))
    impact_cb = _make_impact_callback(wrap_coexist=wrap_coexist)
    body_html = build_html_body_gui(report, _tr, conflicts_only=conflicts_only, include_reference=include_reference,
                                    include_wrap=True, disable_file_links=False,
                                    impact_fn=impact_cb, anchor_fn=make_conflict_anchor)
    try:
        from common.common_i18n import localize_impact_placeholders as _loc_imp
        body_html = _loc_imp(body_html, _tr)
    except Exception:
        pass
    header = _tr('report.header')
    if not isinstance(header, str):
        header = str(header)
    theme_class = 'dark' if dark else ''
    full_html = (tpl
                 .replace('{{TITLE}}', header)
                 .replace('{{HEADER_LABEL}}', header)
                 .replace('{{THEME_CLASS}}', theme_class)
                 .replace('{{BODY}}', body_html))
    if used_tpl and chosen_dir:
        _ca_ensure_css_copy(out_path, chosen_dir)
    return full_html

# ----------------------------------------------------------------------------------
# FUTURE (GUI integration):
# The GUI currently builds a localized body HTML with richer impact heuristics and
# then wraps via its template loader. To converge fully, extract a build_html_body()
# that returns just the <h1>... sections (no <html>/<head>) and allow the GUI to:
#   1) build data model -> body via shared function (with translator)
#   2) inject into its external template (dark/light, inline CSS)
# This file then remains the single source of structural semantics.
# ----------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------
# Compatibility shims (legacy imports)
# Provides compatibility for existing imports to maintain the full HTML output path
# ----------------------------------------------------------------------------------

def build_html(report: Dict[str, Any], tr: Translator | None = None, *, dark: bool = False,
               conflicts_only: bool = False, include_reference: bool = False, lang: str | None = None) -> str:
    """Legacy compatibility: old build_html API.

    Currently calls build_full_html_gui with inline_css=True to return complete HTML.
    Main purpose is to prevent secondary fallback in redscript_report_common.write_html.
    """
    _tr = _resolve_translator(lang, tr)
    try:
        html, _used = build_full_html_gui(report, _tr, dark=dark, conflicts_only=conflicts_only,
                                          include_reference=include_reference, inline_css=True, lang=lang)
        return html
    except Exception:
        # Minimal fallback (minimal HTML)
        return "<html><body><h1>REDscript Conflict Report</h1></body></html>"


def build_markdown(report: Dict[str, Any], tr: Translator | None = None, *,
                   conflicts_only: bool = False, include_reference: bool = False, lang: str | None = None) -> str:
    """Legacy compatibility Markdown builder.

    Maintains format close to old CLI implementation while localizing basic labels with translation (tr).
    Adds simple severity display (Severity column) but prioritizes old format compatibility as optional.
    """
    _ = _resolve_translator(lang, tr)
    lines: list[str] = []
    lines.append(f"# { _('report.header') if _('report.header')!='report.header' else 'REDscript Conflict Report'}\n")
    scanned_root = report.get('scanned_root','')
    lines.append(f"- { _('report.scannedRoot') if _('report.scannedRoot')!='report.scannedRoot' else 'Scanned root:' } `{scanned_root}`\n")
    lines.append(f"- { _('report.filesScanned') if _('report.filesScanned')!='report.filesScanned' else 'Files scanned:' } {report.get('files_scanned',0)}\n")
    ac = report.get('annotation_counts', {}) or {}
    lines.append(f"- Annotation counts: replaceMethod={ac.get('replaceMethod',0)}, wrapMethod={ac.get('wrapMethod',0)}, replaceGlobal={ac.get('replaceGlobal',0)}\n")
    conflicts = iter_conflicts(report, sort=True)
    conf_head = (_('report.conflicts') if _('report.conflicts')!='report.conflicts' else 'Conflicts').split('(')[0].strip()
    lines.append(f"\n## {conf_head} (multiple files @replaceMethod the same method)\n")
    if not conflicts:
        no_conf = _('report.noConflicts') if _('report.noConflicts')!='report.noConflicts' else 'No conflicts detected.'
        lines.append(f"{no_conf}\n")
    else:
        from common.common_util import method_has_wrap as _mhwrap  # lazy import (avoids cyclical import at module import time)
        impact_cfg = _get_impact_config_cached()
    for c in conflicts:
            cls = c.get('class',''); meth = c.get('method','')
            mods = c.get('mods', []) or []
            entries = c.get('occurrences') or c.get('entries') or []
            try:
                has_wrap = _mhwrap(report, cls, meth)
            except Exception:
                has_wrap = False
            impact = compute_impact_unified(cls, meth, mods, entries, wrap_coexist=has_wrap, config=impact_cfg)
            sev = impact.get('severity','')
            sev_key = f"filters.sev.{sev.lower()}" if sev else ''
            sev_label = _(sev_key) if (sev_key and _(sev_key)!=sev_key) else sev
            lines.append(f"### {cls}.{meth}  — {c.get('count',0)} occurrences  — Mods: {', '.join(sorted(set(mods)))}  — {sev_label}\n")
            occs = entries
            sig = ''
            if occs:
                sig = occs[0].get('func_sig') or ''
            if sig:
                tgt_lbl = _('report.targetMethod') if _('report.targetMethod')!='report.targetMethod' else 'Target method'
                lines.append(f"{tgt_lbl}: `{sig}`\n")
            # Baseline (no wrap bonus) severity line if different
            if has_wrap:
                baseline = compute_impact_unified(cls, meth, mods, entries, wrap_coexist=False, config=impact_cfg)
                if (baseline.get('severity') != impact.get('severity')) or (baseline.get('message') != impact.get('message')):
                    bsev = baseline.get('severity','')
                    bsev_key = f"filters.sev.{bsev.lower()}" if bsev else ''
                    bsev_label = _(bsev_key) if (bsev_key and _(bsev_key)!=bsev_key) else bsev
                    base_lbl = _('impact.label.baseline') if _('impact.label.baseline')!='impact.label.baseline' else 'Baseline'
                    lines.append(f"{base_lbl}: {bsev_label}\n")
            for occ in occs:
                mod = occ.get('mod', '<unknown>')
                rel = occ.get('relpath', occ.get('file',''))
                lines.append(f"- [{mod}] {rel}:{occ.get('line',0)}\n")
            # Inline wrap occurrences for this class.method
            try:
                wrap_groups = report.get('wrap_coexistence') or []
                matched = [g for g in wrap_groups if g.get('class')==cls and g.get('method')==meth]
                if matched:
                    wraps = matched[0].get('occurrences') or []
                    if wraps:
                        heading = _('conflict.wrapInlineHeading') if _('conflict.wrapInlineHeading')!='conflict.wrapInlineHeading' else '@wrapMethod (coexisting)'
                        lines.append(f"{heading}:\n")
                        for w in wraps:
                            w_mod = w.get('mod','<unknown>')
                            w_rel = w.get('relpath', w.get('file',''))
                            lines.append(f"  - [{w_mod}] {w_rel}:{w.get('line',0)}\n")
            except Exception:
                pass
            lines.append("")
    if include_reference:
        ref_head = _('report.reference') if _('report.reference')!='report.reference' else 'Reference'
        lines.append(f"\n## {ref_head}\n")
        repl_entries = [e for e in report.get('entries', []) if e.get('annotation') == 'replaceMethod']
        grouped: Dict[tuple[str,str], list] = {}
        from collections import defaultdict as _dd
        grouped = _dd(list)
        for e in repl_entries:
            grouped[(e.get('class',''), e.get('method',''))].append(e)
        for (cls, meth) in sorted(grouped.keys()):
            lines.append(f"### {cls}.{meth}\n")
            sig_once = grouped[(cls,meth)][0].get('func_sig') or ''
            if sig_once:
                tgt_lbl = _('report.targetMethod') if _('report.targetMethod')!='report.targetMethod' else 'Target method'
                lines.append(f"{tgt_lbl}: `{sig_once}`\n")
            for e in grouped[(cls,meth)]:
                rel = e.get('relpath', e.get('file',''))
                lines.append(f"- [{e.get('mod','')}] {rel}:{e.get('line',0)}\n")
            lines.append("")
    return '\n'.join(lines)

