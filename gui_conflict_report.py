"""
GUI wrapper for the REDscript conflict scanner.

Key features:
- Runs the core scanner (redscript_conflicts_report.py) from a simple Tkinter app.
- Live Preview with WebView2 (if available) and Text fallback (no external deps).
- Impact heuristic (Preview-only): estimates severity based on mod count & keywords.
- Theme toggle (Light/Dark) with basic ttk style adjustments.

- Internationalization (i18n): all UI and preview strings externalized to i18n/*.json,
    runtime language switching, native-name language selector.
- Optional: Localize file outputs (MD/JSON). Markdown is generated in-GUI when enabled;
    JSON gains a "localized" block with labels in the selected language.

This file strives to be self-explanatory with docstrings and inline comments so that
third parties can easily audit/extend the code.
"""

import sys
import math
import json
import locale
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont
from typing import Optional, Dict, Any, List, TYPE_CHECKING, Protocol, runtime_checkable, Callable, Tuple
import re
import tempfile
import os
import uuid
import atexit
import webbrowser
import time
from datetime import datetime, timedelta, timezone
import shutil
from common.common_util import safe_call, ensure_row_visibility, log_message  # lightweight helpers (broad UI safety)
from common.common_assets import (
    discover_asset_dirs as discover_asset_dirs,
    load_template_and_css as _ca_load_template_and_css,
    ensure_css_copy as _ca_ensure_css_copy,
)

# --- Layout padding constants (shared) ---------------------------------------
# Use uppercase so static analyzers treat them as constants.
PAD_MAIN: dict[str, int] = {'padx': 8, 'pady': 6}      # General section padding
PAD_TIGHT: dict[str, int] = {'padx': 4, 'pady': 2}     # Compact rows / button clusters

# --- Path constants (restored) -------------------------------------------------
THIS_DIR = Path(__file__).parent.resolve()
# When running from source, the project root is the parent of this GUI file.
SRC_DIR = THIS_DIR

# In a frozen (PyInstaller) build we still want SRC_DIR style paths to resolve to the
# extracted temporary folder so our relative asset discovery keeps working. We attempt
# to remap if frozen; fall back silently otherwise.
try:  # pragma: no cover - defensive
    if getattr(sys, 'frozen', False):  # type: ignore[attr-defined]
        # sys._MEIPASS points to the extraction dir for one-file bundles
        _meipass = Path(getattr(sys, '_MEIPASS', THIS_DIR))  # type: ignore[attr-defined]
        if _meipass.exists():
            SRC_DIR = _meipass  # type: ignore
except Exception:  # pragma: no cover
    pass
_WEBVIEW2_IMPORT_ERR: Optional[Tuple[Exception, Optional[Exception]]] = None
_WEBVIEW2_IMPORT_SRC: Optional[str] = None

@runtime_checkable
class WebView2Like(Protocol):  # minimal interface we rely on
    def pack(self, *args, **kwargs): ...
    def bind(self, sequence: str, func: Callable[..., Any]): ...
    def initialize(self) -> Any: ...
    def load_url(self, url: str): ...
    def destroy(self) -> Any: ...

try:  # pragma: no cover - primary import
    from tkwebview2.tkwebview2 import WebView2 as _WV2Type  # type: ignore
    HAS_WEBVIEW2 = True
    _WEBVIEW2_IMPORT_SRC = 'tkwebview2.tkwebview2'
except Exception as _e1:  # pragma: no cover
    try:
        import tkwebview2 as _wv2  # type: ignore
        _WV2Type = getattr(_wv2, 'WebView2', None)  # type: ignore
        HAS_WEBVIEW2 = _WV2Type is not None
        _WEBVIEW2_IMPORT_SRC = 'tkwebview2'
        if not HAS_WEBVIEW2:
            _WEBVIEW2_IMPORT_ERR = (_e1, None)
    except Exception as _e2:
        HAS_WEBVIEW2 = False
        _WEBVIEW2_IMPORT_ERR = (_e1, _e2)
        class _WV2Type:  # fallback no-op stub
            def __init__(self, *_, **__): pass
            def pack(self, *_, **__): pass
            def bind(self, *_, **__): pass
            def initialize(self): return None
            def load_url(self, *_, **__): pass
            def destroy(self): pass
        _WEBVIEW2_IMPORT_SRC = None
try:  # pragma: no cover
    import redscript_conflicts_report as core  # type: ignore
except Exception:  # pragma: no cover
    core = None  # type: ignore
WebView2 = _WV2Type  # type: ignore  # unify name used elsewhere

_ASSET_DIR_CACHE: Optional[List[Path]] = None  # retained name for any external references

_ASSET_LOG_ONCE = False

def _load_template_and_css(inline_css: bool) -> tuple[str, bool]:
    """Wrapper around common_assets.load_template_and_css preserving (html, used_external_template)."""
    tpl, used, _css_inline, _dir = _ca_load_template_and_css(inline_css=inline_css)
    return tpl, used

from common.common_i18n import load_bundles as _ci_load_bundles, choose_lang as _ci_choose_lang  # type: ignore



# --- Theme helpers (must be defined before main/apply_theme) ---
def _setup_style_dark(style: ttk.Style):
    # Minimal dark theme setup for ttk widgets
    try:
        style.theme_use('clam')
    except Exception:
        pass
    colors = {
        'bg': '#1e1e1e',
        'fg': '#e6e6e6',
        'accent': '#3a3d41',
        'select': '#094771',
        'selectfg': '#ffffff',
        'border': '#3c3c3c'
    }
    style.configure('.', background=colors['bg'], foreground=colors['fg'])
    style.configure('TFrame', background=colors['bg'])
    style.configure('TLabel', background=colors['bg'], foreground=colors['fg'])
    style.configure('TCheckbutton', background=colors['bg'], foreground=colors['fg'])
    style.configure('Switch.TCheckbutton', background=colors['bg'], foreground=colors['fg'])
    # Unified checkmark styling: consistent white check and selection background for light/dark
    try:
        style.map('TCheckbutton',
                  background=[('active', '#2a2d2f'), ('selected', '#2a2d2f')],
                  foreground=[('selected', colors['fg'])],
                  indicatorcolor=[('selected', '#0a64c2'), ('!selected', colors['bg'])])
        style.map('Switch.TCheckbutton',
                  background=[('active', '#2a2d2f'), ('selected', '#2a2d2f')],
                  foreground=[('selected', colors['fg'])],
                  indicatorcolor=[('selected', '#0a64c2'), ('!selected', colors['bg'])])
    except Exception:
        pass
    style.configure('TButton', background=colors['accent'], foreground=colors['fg'])
    style.configure('TEntry', fieldbackground='#2d2d30', foreground=colors['fg'])
    style.configure('TLabelframe', background=colors['bg'], foreground=colors['fg'])
    style.configure('TLabelframe.Label', background=colors['bg'], foreground=colors['fg'])
    # Notebook & Tabs (improve dark-mode tab legibility)
    style.configure('TNotebook', background=colors['bg'], bordercolor=colors['border'])
    style.configure('TNotebook.Tab', background='#2a2a2a', foreground=colors['fg'], bordercolor=colors['border'])
    style.map('TNotebook.Tab',
              background=[('selected', colors['select']), ('active', '#3a3d41')],
              foreground=[('selected', colors['selectfg']), ('active', colors['selectfg'])])


def _setup_style_light(style: ttk.Style):
    try:
        style.theme_use('default')
    except Exception:
        pass
    style.configure('.', background='#f0f0f0', foreground='#000000')
    style.configure('TFrame', background='#f0f0f0')
    style.configure('TLabel', background='#f0f0f0', foreground='#000000')
    style.configure('TCheckbutton', background='#f0f0f0', foreground='#000000')
    style.configure('Switch.TCheckbutton', background='#f0f0f0', foreground='#000000')
    try:
        style.map('TCheckbutton',
                  background=[('active', '#e0e0e0'), ('selected', '#e0e0e0')],
                  foreground=[('selected', '#000000')])
        style.map('Switch.TCheckbutton',
                  background=[('active', '#e0e0e0'), ('selected', '#e0e0e0')],
                  foreground=[('selected', '#000000')])
    except Exception:
        pass
    style.configure('TButton', background='#e6e6e6', foreground='#000000')
    style.configure('TEntry', fieldbackground='#ffffff', foreground='#000000')
    style.configure('TLabelframe', background='#f0f0f0', foreground='#000000')
    style.configure('TLabelframe.Label', background='#f0f0f0', foreground='#000000')
    # Notebook & Tabs (keep high contrast in light mode)
    style.configure('TNotebook', background='#f0f0f0', bordercolor='#cccccc')
    style.configure('TNotebook.Tab', background='#e6e6e6', foreground='#000000', bordercolor='#cccccc')
    style.map('TNotebook.Tab',
              background=[('selected', '#ffffff'), ('active', '#ededed')],
              foreground=[('selected', '#000000'), ('active', '#000000')])


def apply_text_widget_theme(widget: tk.Text, dark: bool):
    if dark:
        widget.configure(bg='#1e1e1e', fg='#e6e6e6', insertbackground='#e6e6e6')
    else:
        widget.configure(bg='#ffffff', fg='#000000', insertbackground='#000000')
    # Keep file path (simulated hyperlink) color in sync with HTML link color
    try:
        widget.tag_configure('filelink', foreground=('#4ea3ff' if dark else '#0066cc'))
    except Exception:
        pass


def discover_default_paths():
    """Try to find sensible defaults for root (r6/scripts) and reports folder.

    NOTE: This function no longer creates output directories eagerly. Actual
    directory creation happens in on_run() only when a file output is selected.
    Here we only return candidate path strings.
    """
    cwd = Path.cwd()
    exe_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else SRC_DIR
    candidates_root = [
        cwd / 'r6' / 'scripts',
        exe_dir / '..' / 'r6' / 'scripts',
        SRC_DIR.parent / 'r6' / 'scripts',
    ]
    root = None
    for c in candidates_root:
        if c.exists():
            root = c.resolve()
            break
    if root is None:
        root = (cwd / 'r6' / 'scripts').resolve()

    # Defer creation of reports directory to run-time to avoid empty folders when no outputs are generated.
    candidates_reports = [
        cwd / 'reports',
        SRC_DIR / 'reports',
        exe_dir / 'reports',
    ]
    # Pick the first viable-looking candidate (do not create yet).
    out_dir = None
    for c in candidates_reports:
        if c.exists():
            out_dir = c.resolve()
            break
    if out_dir is None:
        # If none exists, use the first candidate as default string (not created yet).
        out_dir = (cwd / 'reports').resolve()

    out_json = out_dir / 'redscript_conflicts.json'
    out_md = out_dir / 'redscript_conflicts.md'
    return str(root), str(out_json), str(out_md), str(out_dir)


class App(tk.Tk):
    """Tkinter application for scanning and previewing REDscript conflicts.

    Public knobs are stored in tk Variables (StringVar/BooleanVar/DoubleVar) so they can be
    easily traced/observed and bound to UI widgets.
    """
    def __init__(self):
        super().__init__()
        # Application semantic version
        self.APP_VERSION = '0.1.0'
        self._i18n_used_keys = set()  # Track i18n key usage dynamically (only for current session)
        # Load i18n bundles & choose language
        self._bundles = _ci_load_bundles()
        self.var_lang = tk.StringVar(value=_ci_choose_lang(self._bundles))  # Language variable
        self._ = self._make_gettext()  # Gettext function
        self.title(self._('app.title'))  # Set window title
        # Default size: height x1.5 (520 -> 780)
        # Size the initial window to the minimum width (720px)
        self.geometry('720x780')
        self.minsize(720, 720)
        self.style = ttk.Style(self)
        # In-memory caches for localized outputs (reset on language/mode/include-wrap changes)
        self._cache_md = {}
        self._cache_json_loc = {}
        # --- Predeclare dynamic widget attributes (reduce static analyzer false positives) ---
        # Text/preview widgets
        self.txt_html = None  # type: Optional[tk.Text]
        self.html_text_container = None  # type: Optional[ttk.Frame]
        self.sb_html = None  # type: Optional[ttk.Scrollbar]
        self.webview2 = None  # type: Optional[WebView2]  # noqa: N815
        self._webview2_last_error = None  # type: Optional[Exception]
        self.wv_hint = None  # type: Optional[ttk.Frame]  # hint banner placeholder
        # Log / Markdown / JSON text areas
        self.txt_log = None  # type: Optional[tk.Text]
        self.txt_md = None  # type: Optional[tk.Text]
        self.txt_json = None  # type: Optional[tk.Text]
        # Filter related frames/labels (may be None if creation guarded)
        self.lbl_severity = None  # type: Optional[ttk.Label]
        self.ff_sev_checks = None  # type: Optional[ttk.Frame]
        self.lbl_symptoms = None  # type: Optional[ttk.Label]
        self.ff_sym_checks = None  # type: Optional[ttk.Frame]
        # Misc labels/buttons later constructed (predeclare for analyzer)
        self.lbl_theme = None  # type: Optional[ttk.Label]
        self.btn_browse_root = None  # type: Optional[ttk.Button]
        self.lbl_theme_text = None  # type: Optional[ttk.Label]
        self.chk_auto_open = None  # type: Optional[ttk.Checkbutton]
        self.of = None  # type: Optional[ttk.Label]
        self.lbl_output_files = None  # type: Optional[ttk.Label]
        # Output settings window widgets (created lazily)
        self.ent_out_html = None  # type: Optional[ttk.Entry]
        self.ent_out_md = None    # type: Optional[ttk.Entry]
        self.ent_out_json = None  # type: Optional[ttk.Entry]
        self.btn_browse_html = None  # type: Optional[ttk.Button]
        self.btn_browse_md = None    # type: Optional[ttk.Button]
        self.btn_browse_json = None  # type: Optional[ttk.Button]
        self.lbl_outwin_files = None  # type: Optional[ttk.Label]
        self._outwin_toggles = {}  # type: Dict[str, ttk.Checkbutton]
        # Timings dict (always present now)
        self._timings: Dict[str, float] = {}

        # ---------------- Guard / helper methods (defined as closures for locality) ---------
        def _require_report() -> Dict[str, Any]:
            if self._last_report is None:
                raise RuntimeError('Report not generated yet')
            return self._last_report
        self._require_report = _require_report  # type: ignore[attr-defined]

        def _ensure_timings() -> Dict[str, float]:
            return self._timings
        self._ensure_timings = _ensure_timings  # type: ignore[attr-defined]

        def _get_log_widget() -> Optional[tk.Text]:
            return getattr(self, 'txt_log', None)
        self._get_log_widget = _get_log_widget  # type: ignore[attr-defined]

        def _safe_destroy(w: Any):
            try:
                if w and hasattr(w, 'destroy'):
                    w.destroy()
            except Exception:
                pass
        self._safe_destroy = _safe_destroy  # type: ignore[attr-defined]

        def _safe_pack_forget(w: Any):
            try:
                if w and hasattr(w, 'pack_forget'):
                    w.pack_forget()
            except Exception:
                pass
        self._safe_pack_forget = _safe_pack_forget  # type: ignore[attr-defined]
        # Misc tracking
        self._last_filtered_conflicts_count = 0  # initialized for analyzer
        # Browse dialog diagnostics / mode toggle (A+B instrumentation & delayed dispatch)
        self._browse_delay_mode = True  # True=delay a tick before showing dialogs for stability test
        self._browse_delay_skip_next = False  # internal sentinel
        # --- Startup geometry auto-adjust guard ---
        # Prevent the early auto geometry stabilization logic from snapping the window back
        # if the user manually moves it shortly after launch. Once movement is detected we
        # only preserve size (not position) for remaining auto adjustments.
        try:
            import time as _t
            self._startup_geom_deadline = _t.time() + 2.5  # Stop position monitoring ~2.5s after launch
            self._user_moved_window = False
            self._last_win_pos = (self.winfo_x(), self.winfo_y())
            self._fs_after_ids = []  # Track after() ids for font scaling so we can cancel if user moves window

            def _on_configure_evt(evt=None):
                # Check if position changed (ignore pure size adjustments)
                try:
                    cur = (self.winfo_x(), self.winfo_y())
                except Exception:
                    return
                try:
                    if cur != getattr(self, '_last_win_pos', cur):
                        # Treat >1px (effectively any real move) as user movement (filters out internal jitter)
                        if not self._user_moved_window:
                            self._user_moved_window = True
                            # Cancel any pending after() tasks that would restore position (size-only from now on)
                            try:
                                for aid in list(getattr(self, '_fs_after_ids', []) or []):
                                    try:
                                        self.after_cancel(aid)
                                    except Exception:
                                        pass
                                self._fs_after_ids.clear()
                            except Exception:
                                pass
                        self._last_win_pos = cur
                except Exception:
                    pass
                # After deadline stop enforcing position logic (flag itself remains for diagnostics)
                try:
                    if _t.time() > getattr(self, '_startup_geom_deadline', 0):
                        # Unbind configure handler to reduce overhead/noise
                        try:
                            self.unbind('<Configure>', self._startup_configure_bind_id)
                        except Exception:
                            pass
                except Exception:
                    pass

            try:
                self._startup_configure_bind_id = self.bind('<Configure>', _on_configure_evt, add='+')
            except Exception:
                pass
        except Exception:
            pass
        # Ensure initial ttk styles & text widget colors match current dark/light flag
        try:
            self.apply_theme()
        except Exception:
            pass

        if core is None:
            messagebox.showerror(self._('error.import.title'), self._('error.import.body'))

        self.var_root = tk.StringVar()
        self.var_out_json = tk.StringVar()
        self.var_out_md = tk.StringVar()
        # Exclusive mode: True = Conflicts only, False = Include reference
        self.var_mode_conflicts = tk.BooleanVar(value=True)
        self.var_mode_text = tk.StringVar(value=self._('mode.conflicts'))
        # Backwards compatibility flags (not bound to UI)
        self.var_conflicts_only = tk.BooleanVar(value=True)
        self.var_include_reference = tk.BooleanVar(value=False)
        self.var_enable_json = tk.BooleanVar(value=False)
        self.var_enable_md = tk.BooleanVar(value=False)
        # New: enable saving Preview (HTML) as a file
        self.var_enable_preview = tk.BooleanVar(value=False)
    # Include wrapMethod coexistence sections (GUI + file outputs)
        # Default OFF unless the user enables it.
        self.var_include_wrap = tk.BooleanVar(value=False)
        # Dark/Light exclusive toggle
        self.var_dark_mode = tk.BooleanVar(value=False)  # False=Light, True=Dark
        self.var_dark_label = tk.StringVar(value=self._('theme.light'))

        # Preview filters (Preview-only)
        self.var_filter_mods = tk.StringVar(value='')  # comma-separated tokens
        self.var_filter_class = tk.StringVar(value='')  # substring
        self.var_filter_sev_high = tk.BooleanVar(value=True)
        self.var_filter_sev_medium = tk.BooleanVar(value=True)
        self.var_filter_sev_low = tk.BooleanVar(value=True)
        self.var_filter_sev_critical = tk.BooleanVar(value=True)

        # Preview font scaling (default 100% = 1.0x; range 0.5x (50%) - 1.5x (150%))
        self.var_font_scale = tk.DoubleVar(value=1.0)
        # Global font family selection (applies to UI preview + HTML exports)
    # Default UI font preference: try detected preferred family, fallback to Segoe UI.
        try:
            _default_family = self._detect_preferred_font()
        except Exception:
            _default_family = 'Segoe UI'
        self.var_font_family = tk.StringVar(value=_default_family)

        # Post-run option
        self.var_auto_open = tk.BooleanVar(value=False)
        # Localize file outputs (used by menubar; must exist before building menus)
        self.var_localize_output = tk.BooleanVar(value=True)

        # --- Temp session management defaults (can be overridden by settings after load) ---
        self._retain_temp_files = False  # keep session temp directory after exit if True
        self._temp_max_days = 5            # prune sessions older than this (days)
        self._temp_max_total_mb = 300      # prune oldest sessions until total <= limit
        self.session_temp_dir = None
        # Base temp directory used for all sessions
        self._temp_base_dir = Path(tempfile.gettempdir()) / 'RedScriptConflictGUI'
        # On every startup, attempt to remove the entire base directory to guarantee a clean slate
        try:
            self._purge_temp_base_dir()
        except Exception:
            pass
        try:
            self._init_session_temp_dir()
        except Exception:
            pass
        # Loose temp files created outside the session dir (fallbacks) to delete on exit
        self._loose_temp_files = []

        # Settings
        # Default settings path bootstrap: exe-adjacent redscript_conflict_gui.json
        self._exe_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else SRC_DIR
        self._settings_bootstrap = self._exe_dir / 'redscript_conflict_gui.json'
        default_settings = self._settings_bootstrap
        # Read bootstrap for `settings_path` only
        try:
            if self._settings_bootstrap.exists():
                data = json.loads(self._settings_bootstrap.read_text(encoding='utf-8'))
                sp = data.get('settings_path')
                if sp:
                    default_settings = Path(sp)
        except Exception:
            pass
        self._settings_path = default_settings
        self.var_settings_path = tk.StringVar(value=str(self._settings_path))
        # First-run detection (no persisted settings file present yet)
        try:
            self._first_run = not self._settings_path.exists()
        except Exception:
            self._first_run = True
        self._last_report = None
        # Impact configuration - use shared defaults for consistency
        try:  # lazy import so module loads even if common_impact has issues
            from common.common_impact import get_default_impact_config as _gui_gdic  # type: ignore
            self._impact_cfg = _gui_gdic()  # deep copy of defaults
        except Exception:
            # Fallback configuration if common_impact unavailable
            self._impact_cfg = {
                'thresholds': {'critical': 95, 'high': 70, 'medium': 45},
                'weights': {
                    'per_mod': 25,
                    'class_keywords': {},
                    'method_keywords': {},
                    'signature': {'per_arg': 3, 'has_return': 6},
                    'wrap_coexist_bonus': 12,
                }
            }
        # Event listeners storage (placeholder for future extension)
        # self._event_listeners = {}

        root, out_json, out_md, self.reports_dir = discover_default_paths()
        self.var_root.set(root)
        self.var_out_json.set(out_json)
        self.var_out_md.set(out_md)
        # Default HTML out path (alongside JSON/MD in reports_dir)
        try:
            self.var_out_html = tk.StringVar(value=str(Path(self.reports_dir) / 'redscript_conflicts.html'))
        except Exception:
            self.var_out_html = tk.StringVar(value='redscript_conflicts.html')

        # Early log buffer (flush after txt_log widget exists)
        self._early_logs = []  # list of tuples (msg, tag)

        self._build_ui()
        self._wire_events()
        # Store latest HTML body (without head/style) for theme re-render
        self._last_html_body = ''
        # Store latest full HTML (with head/style) for clipboard copy
        self._last_full_html = ''
        # Store latest data for fallback rich Text renderer
        self._last_render_args = None  # tuple: (report_dict, conflicts_only, include_reference)
        # Load settings first so dark-mode and other toggles are applied on first theming
        self._load_settings_silent()
        # Apply theme after settings are loaded to avoid light background flashes
        self.apply_theme()
        self._on_mode_toggle()
        # Register atexit cleanup (after settings load may adjust retain flag)
        try:
            atexit.register(self._cleanup_session_temp_dir_atexit)
        except Exception:
            pass

    def _detect_preferred_font(self) -> str:
        """Detect preferred default UI font.

        Policy (simplified):
        1. If the active language bundle declares preferredFont / preferredFonts, try them in order.
           (Exact case-insensitive match first, then fuzzy prefix match to tolerate style suffixes.)
        2. Otherwise (or if none found/installed) fall back to 'Segoe UI'.

        Returns the detected installed family name or the fallback.
        """
        try:
            fams = set(str(f) for f in tkfont.families())  # may raise if Tk not fully initialized
        except Exception:
            return 'Segoe UI'
        # Build case-insensitive map
        ci_map = {f.lower(): f for f in fams}
        # 1) Language bundle declared fonts
        lang = None
        try:
            lang = self.var_lang.get()
        except Exception:
            pass
        bundle_fonts: list[str] = []
        try:
            bundles = getattr(self, '_bundles', {}) or {}
            b = bundles.get(lang) if lang else None
            if isinstance(b, dict):
                meta = b.get('$meta') or {}
                if isinstance(meta, dict):
                    # Accept preferredFont (str) or preferredFonts (list)
                    pf = meta.get('preferredFont')
                    pfs = meta.get('preferredFonts')
                    if isinstance(pf, str) and pf.strip():
                        bundle_fonts.append(pf.strip())
                    if isinstance(pfs, list):
                        for item in pfs:
                            if isinstance(item, str) and item.strip():
                                bundle_fonts.append(item.strip())
        except Exception:
            pass
        # Deduplicate declared bundle fonts preserving order
        seen = set()
        ordered_bundle_fonts: list[str] = []
        for f in bundle_fonts:
            lf = f.lower()
            if lf not in seen:
                seen.add(lf)
                ordered_bundle_fonts.append(f)

        diag = getattr(self, '_diag_file_log', None)
        if callable(diag):
            try:
                diag(f'FONT DETECT start lang={lang} declared={ordered_bundle_fonts} totalFamilies={len(fams)} policy=declared-or-segoe')
            except Exception:
                pass

        # Helper to log & return
        def _ret(hit_family: str, reason: str):  # type: ignore
            if callable(diag):
                try:
                    diag(f'FONT DETECT select family={hit_family!r} reason={reason}')
                except Exception:
                    pass
            return hit_family

        candidates = ordered_bundle_fonts
        # If none declared, fall back immediately
        if not candidates:
            return _ret('Segoe UI', 'no-declared')

        # Pass 1: exact (case-insensitive)
        for cand in candidates:
            hit = ci_map.get(cand.lower())
            if hit:
                return _ret(hit, 'exact')

        # Pass 2: fuzzy prefix (handle weight/style suffixes)
        lower_fams = [(f.lower(), f) for f in fams]
        for cand in candidates:
            cl = cand.lower()
            fuzzy_hits = [orig for lf, orig in lower_fams if lf == cl or lf.startswith(cl + ' ')]
            if not fuzzy_hits:
                fuzzy_hits = [orig for lf, orig in lower_fams if lf.startswith(cl)]
            if fuzzy_hits:
                fuzzy_hits.sort(key=lambda x: len(x))
                return _ret(fuzzy_hits[0], 'fuzzy')

        # None of the declared fonts installed -> Segoe UI
        return _ret('Segoe UI', 'fallback')

    def _build_ui(self):
        """Builds the main UI: top bar, scan settings, mode/options, tabs, filters, preview.

        This function wires widgets but keeps callbacks in _wire_events for clarity.
        """
        # (Padding constants defined at module scope: PAD_MAIN / PAD_TIGHT)

        frm = ttk.Frame(self)
        frm.pack(fill='both', expand=True)

        # Top bar (we'll place a right-aligned Theme menubutton here)
        self.topbar = ttk.Frame(frm)
        self.topbar.pack(fill='x', padx=8, pady=(8, 0))

        # Menubar (Output settings)
        try:
            self._build_menus()
        except Exception:
            pass

        # Scan settings --------------------------------------------------
        self.lf = ttk.LabelFrame(frm, text=self._('scan.settings'))
        # Use explicit padx/pady (avoid some analyzers mis-reading **dict expansion here)
        self.lf.pack(fill='x', padx=PAD_MAIN['padx'], pady=PAD_MAIN['pady'])
        self.lbl_scan_root = ttk.Label(self.lf, text=self._('scan.root'))
        self.lbl_scan_root.grid(row=0, column=0, sticky='w', padx=8, pady=6)
        self.ent_root = ttk.Entry(self.lf, textvariable=self.var_root)
        self.ent_root.grid(row=0, column=1, sticky='ew', padx=8, pady=6)
        # Column 2 intentionally unused (no browse button)
        self.lf.columnconfigure(1, weight=1)

        # Mode (exclusive toggle) ----------------------------------------
        self.mf = ttk.LabelFrame(frm, text=self._('mode.label'))
        self.mf.pack(fill='x', padx=PAD_MAIN['padx'], pady=PAD_MAIN['pady'])
        self.chk_mode = ttk.Checkbutton(self.mf, textvariable=self.var_mode_text, variable=self.var_mode_conflicts,
                                        style='Switch.TCheckbutton', command=self._on_mode_toggle)
        self.chk_mode.grid(row=0, column=0, sticky='w', padx=(8, 6), pady=6)
        # Include wrapMethod coexistence toggle moved under Mode section
        try:
            self.chk_include_wrap = ttk.Checkbutton(self.mf, text=self._('options.includeWrap'), variable=self.var_include_wrap,
                                                   command=self._on_include_wrap_toggle)
            try:
                self.mf.columnconfigure(0, weight=0)
                self.mf.columnconfigure(1, weight=0)
                self.mf.columnconfigure(2, weight=1)
            except Exception:
                pass
            self.chk_include_wrap.grid(row=0, column=1, sticky='w', padx=(0, 8), pady=6)
        except Exception:
            pass
        # Output toggles reside in the Output Settings window

        # Actions ---------------------------------------------------------
        af = ttk.Frame(frm)
        af.pack(fill='x', padx=PAD_MAIN['padx'], pady=PAD_MAIN['pady'])
        self.btn_run = ttk.Button(af, text=self._('actions.generate'), command=self.on_run)
        self.btn_run.pack(side='left', padx=(6, 6))  # keep first and always visible
        try:
            self.btn_open_browser = ttk.Button(af, text=self._('actions.openBrowser'), command=self.on_open_browser)
        except Exception:
            self.btn_open_browser = None
        self.btn_open_folder = ttk.Button(af, text=self._('actions.openFolder'), command=self.on_open_folder)
        self.progress = ttk.Progressbar(af, mode='indeterminate', length=160)
        self.progress.pack(side='right')
        self.progress.stop()
        self.progress.pack_forget()

        # (Filters will be placed below the Notebook)

        # --- Symptom category filter variables (normalized internal codes + i18n labels) ---
        # Use internal codes so filtering is language-agnostic; map to i18n for UI labels.
        self.var_filter_symptoms = {}
        self.chk_symptoms = {}
        # UI layout tweak: place the "inventory/items" symptom group on the second row initially (one-time forced break)
        try:
            self._sym_force_break_code_initial = 'inventory'
            self._sym_force_break_applied = False
        except Exception:
            pass
        try:
            for code in ['uiHud', 'player', 'vehicle', 'quest', 'inventory', 'damage', 'other']:
                # Default all True
                self.var_filter_symptoms[code] = tk.BooleanVar(value=True)
        except Exception:
            pass

        # Preview options — place ABOVE Notebook so controls remain visible
        self.pf = ttk.LabelFrame(frm, text=self._('preview.options'))
        self.pf.pack(fill='x', padx=PAD_MAIN['padx'], pady=PAD_MAIN['pady'])
        # Status bar at bottom showing engine/theme/lang
        try:
            self.status_bar = ttk.Label(frm, anchor='w')
            self.status_bar.pack(fill='x', side='bottom', padx=6, pady=(0,4))
        except Exception:
            self.status_bar = None
        self._update_status_bar()
        # (No startup popup): Suppress preview state toast on GUI startup per request
        # Widgets: font scale label + slider
        _ppad = {'padx': 8, 'pady': 4}
        self.lbl_font_scale = ttk.Label(self.pf, text=self._('preview.fontScale'))
        self.lbl_font_scale.grid(row=0, column=0, sticky='w', padx=_ppad['padx'], pady=_ppad['pady'])
        # Scale stretches with window width
        # Add decrement button (-), slider, increment button (+) for 10% steps
        def _nudge_font_scale(delta: float):
            """Move scale to the next/previous 10%-step so percentage ones digit becomes 0."""
            try:
                cur = float(self.var_font_scale.get() or 1.0)
            except Exception:
                cur = 1.0
            cur = max(0.5, min(1.5, cur))
            n = cur * 10.0
            if delta > 0:
                new_n = math.floor(n + 1e-6) + 1
            else:
                new_n = math.ceil(n - 1e-6) - 1
            new_val = max(0.5, min(1.5, new_n / 10.0))
            self.var_font_scale.set(round(new_val, 1))
        # +/- buttons use fixed metrics (dynamic sizing disabled)
        # Rough height target matches Windows ttk.Scale trough (~22-26px)
        btn_pad = {'padx': 4, 'pady': 0}
        try:
            if not hasattr(self, 'style'):
                self.style = ttk.Style(self)
            try:
                _btn_font = tkfont.Font(family='Segoe UI', size=8)
            except Exception:
                _btn_font = None
            if _btn_font is not None:
                self.style.configure('FontScale.TButton', padding=(6, 1), font=_btn_font)
            else:
                self.style.configure('FontScale.TButton', padding=(6, 1))
        except Exception:
            pass
        self.btn_font_dec = ttk.Button(self.pf, text='-', width=2, style='FontScale.TButton', command=lambda: _nudge_font_scale(-0.10))
        # Make it slimmer: set ipady=0 and avoid vertical stretch (no sticky NS)
        self.btn_font_dec.grid(row=0, column=1, sticky='w', ipady=0, padx=btn_pad['padx'], pady=btn_pad['pady'])
        self.sld_font_scale = ttk.Scale(self.pf, from_=0.5, to=1.5, orient='horizontal', variable=self.var_font_scale)
        self.sld_font_scale.grid(row=0, column=2, sticky='ew', padx=_ppad['padx'], pady=_ppad['pady'])
        self.btn_font_inc = ttk.Button(self.pf, text='+', width=2, style='FontScale.TButton', command=lambda: _nudge_font_scale(+0.10))
        self.btn_font_inc.grid(row=0, column=3, sticky='e', ipady=0, padx=btn_pad['padx'], pady=btn_pad['pady'])
        def _click_set_scale(event):
            """Move the slider thumb to the click position. If near the thumb (±8px), allow default drag start."""
            try:
                w = max(1, event.widget.winfo_width())
                from_v = float(event.widget.cget('from'))
                to_v = float(event.widget.cget('to'))
                cur = float(self.var_font_scale.get() or from_v)
                frac_cur = (cur - from_v) / (to_v - from_v) if to_v != from_v else 0
                thumb_x = frac_cur * w
                if abs(event.x - thumb_x) <= 8:
                    return
                x = min(max(0, event.x), w)
                frac = x / w
                val = from_v + (to_v - from_v) * frac
                val = max(from_v, min(to_v, round(val * 100) / 100))
                self.var_font_scale.set(val)
                return 'break'
            except Exception:
                return 'break'
        try:
            self.sld_font_scale.bind('<Button-1>', _click_set_scale, add='+')
        except Exception:
            pass
        try:
            self.var_font_px = tk.StringVar()
            self.lbl_font_px = ttk.Label(self.pf, textvariable=self.var_font_px)
            self.lbl_font_px.grid(row=0, column=4, sticky='w', padx=_ppad['padx'], pady=_ppad['pady'])
        except Exception:
            self.var_font_px = tk.StringVar(value='')
            self.lbl_font_px = ttk.Label(self.pf, textvariable=self.var_font_px)
            self.lbl_font_px.grid(row=0, column=4, sticky='w', padx=_ppad['padx'], pady=_ppad['pady'])
        self.pf.columnconfigure(0, weight=0)
        self.pf.columnconfigure(1, weight=0)
        self.pf.columnconfigure(2, weight=1)
        self.pf.columnconfigure(3, weight=0)
        self.pf.columnconfigure(4, weight=0)
        try:
            self._update_font_px_label()
        except Exception:
            pass

        # Notebook with Preview / Markdown / JSON / Log (placed after options; filters go below)
        nb = ttk.Notebook(frm)
        nb.pack(fill='both', expand=True, padx=PAD_MAIN['padx'], pady=PAD_MAIN['pady'])
        self.nb = nb

        # Tabs (in order): Preview, Markdown, JSON, Log
        tab_preview = ttk.Frame(nb)
        tab_md = ttk.Frame(nb)
        tab_json = ttk.Frame(nb)
        tab_log = ttk.Frame(nb)
        # Add localized tab labels (HTML/Markdown/JSON/Log)
        nb.add(tab_preview, text=self._('tabs.html'))
        nb.add(tab_md, text=self._('tabs.markdown'))
        nb.add(tab_json, text=self._('tabs.json'))
        nb.add(tab_log, text=self._('tabs.log'))

        # Preview tab: HTML area only (GUI-only; does not affect output files)
        self.webview2 = None  # active HTML engine widget (WebView2) or None
        self._webview2_last_error = None
        # No hint banner in HTML tab (simplified per request)
        def _show_wv_hint(msg: str):
            # No-op: suppress hint UI entirely (message/Retry/WebView2 info)
            return
        def _hide_wv_hint():
            frame = getattr(self, 'wv_hint', None)
            if frame is not None:
                self._safe_destroy(frame)
                self.wv_hint = None
        # Show Text fallback first and replace with WebView2 automatically if initialization succeeds
        def _ensure_text_fallback():
            if not hasattr(self, 'txt_html') or self.txt_html is None:
                try:
                    # Container + Text widget with vertical Scrollbar
                    self.html_text_container = ttk.Frame(tab_preview)
                    self.html_text_container.pack(fill='both', expand=True, padx=6, pady=6)
                    # Pack scrollbar first to prevent width=0 at high font scales
                    self.txt_html = tk.Text(self.html_text_container, height=12)
                    self.sb_html = ttk.Scrollbar(self.html_text_container, orient='vertical', command=self.txt_html.yview)
                    self.txt_html.configure(yscrollcommand=self.sb_html.set)
                    self.sb_html.pack(side='right', fill='y')
                    self.txt_html.pack(side='left', fill='both', expand=True)
                except Exception:
                    pass

        _ensure_text_fallback()
        # If import failed, log why and show hint immediately
        if not HAS_WEBVIEW2 or WebView2 is None:
            try:
                if _WEBVIEW2_IMPORT_ERR:
                    e1, e2 = _WEBVIEW2_IMPORT_ERR
                    log_message('info', self.log, f"tkwebview2 import failed; using Text fallback. Errors: {_WEBVIEW2_IMPORT_SRC or 'n/a'} -> {type(e1).__name__ if e1 else 'n/a'} / {type(e2).__name__ if e2 else 'n/a'}")
                else:
                    log_message('info', self.log, 'tkwebview2 not available; using Text fallback')
            except Exception:
                pass
            # If translation is missing/incomplete, fall back to an English default message
            try:
                key = 'hint.webview2.unavailable'
                tr = self._(key)
            except Exception:
                tr = None
            if not tr or tr == key or len(str(tr).strip()) < 10:
                tr = 'WebView2 is not available. Falling back to Text preview.'
            _show_wv_hint(tr)

        if HAS_WEBVIEW2 and WebView2 is not None:
            # Prevent duplicate scheduling from both <Map> and timer
            if not hasattr(self, '_webview2_init_scheduled'):
                self._webview2_init_scheduled = False

            def _init_webview2(attempt: int = 1, max_attempts: int = 1):
                try:
                    # Single attempt: if parent is unmapped or extremely small, do not reschedule and exit
                    try:
                        if not tab_preview.winfo_ismapped() or tab_preview.winfo_width() < 50 or tab_preview.winfo_height() < 50:
                            log_message('info', self.log, 'WebView2 init skipped: tab not ready (single-attempt mode)')
                            return
                    except Exception:
                        pass
                    # If initialization already succeeded, don't reinitialize
                    if getattr(self, 'webview2', None) is not None:
                        return
                    log_message('info', self.log, f"WebView2 init attempt {attempt}/{max_attempts}")
                    # If a fixed WebView2 is bundled, set env var to prioritize it
                    try:
                        self._maybe_set_fixed_webview2()
                    except Exception:
                        pass
                    # Pin WebView2 user data folder to a session-specific directory (avoid permission/lock issues)
                    try:
                        base = self.session_temp_dir or (Path(tempfile.gettempdir()) / 'RedScriptConflictGUI')
                        ud = Path(base) / 'wv2_profile'
                        ud.mkdir(parents=True, exist_ok=True)
                        os.environ.setdefault('WEBVIEW2_USER_DATA_FOLDER', str(ud))
                        log_message('info', self.log, f"WEBVIEW2_USER_DATA_FOLDER={ud}")
                    except Exception:
                        pass
                    # Ensure geometry calculations are settled before creating the control
                    try:
                        self.update_idletasks()
                    except Exception:
                        pass
                    # Reserve a small initial size (avoid init failures due to tiny size)
                    wv = WebView2(tab_preview, width=100, height=60)
                    try:
                        wv.pack(fill='both', expand=True)
                    except Exception:
                        pass
                    # Some backends require explicit initialize()
                    try:
                        if hasattr(wv, 'initialize') and callable(getattr(wv, 'initialize')):
                            wv.initialize()
                    except Exception:
                        pass
                    # Context menu on right-click
                    try:
                        wv.bind('<Button-3>', self._on_webview_context_menu)
                    except Exception:
                        pass
                    # Store the control reference
                    self.webview2 = wv
                    _hide_wv_hint()
                    # Hide Text fallback if it exists
                    try:
                        ctn = getattr(self, 'html_text_container', None)
                        if ctn is not None:
                            self._safe_pack_forget(ctn)
                    except Exception:
                        pass
                    # Schedule a safe blank load with a slight delay
                    try:
                        self.after(60, lambda: self._webview2_try_load_blank())
                    except Exception:
                        pass
                    try:
                        # Log tkwebview2 version if available
                        ver = None
                        try:
                            import sys as _sys
                            _mod = _sys.modules.get('tkwebview2')
                            ver = getattr(_mod, '__version__', None)
                        except Exception:
                            ver = None
                        log_message('info', self.log, f"WebView2 control created via {_WEBVIEW2_IMPORT_SRC} (tkwebview2 {ver or 'unknown'})")
                    except Exception:
                        pass
                except Exception as e:
                    # Single-attempt mode: do not retry
                    self.webview2 = None
                    self._webview2_last_error = e
                    log_message('warn', self.log, f"WebView2 init failed: {e.__class__.__name__}: {e}")
                    # Probe runtime presence and include in hint
                    try:
                        info = self._probe_webview2_runtime()
                        if not info.get('found'):
                            log_message('warn', self.log, 'WebView2 Runtime not found in common locations')
                        else:
                            log_message('info', self.log, f"WebView2 Runtime detected: {info.get('path')} (version {info.get('version') or 'unknown'}, arch {info.get('arch') or 'unknown'})")
                    except Exception:
                        pass
                    # If translation is missing/incomplete, fall back to a clear English hint
                    try:
                        key = 'hint.webview2.failed'
                        tr = self._(key)
                    except Exception:
                        tr = None
                    if not tr or tr == key or len(str(tr).strip()) < 10:
                        hint_arch = ''
                        try:
                            import platform
                            app_bits = 'x64' if platform.machine().endswith('64') else 'x86'
                            arch_rt = info.get('arch') if isinstance(info, dict) else None
                            if arch_rt and app_bits != arch_rt:
                                hint_arch = f" Possible architecture mismatch: app={app_bits}, runtime={arch_rt}."
                        except Exception:
                            pass
                        tr = f"WebView2 failed to initialize. Falling back to Text. ({e.__class__.__name__}).{hint_arch}"
                    _show_wv_hint(tr)
            # After the tab is mapped, attempt the first initialization (avoid duplicate starts)
            def _schedule_wv_init(delay: int = 60):
                try:
                    if getattr(self, '_webview2_init_scheduled', False):
                        return
                    self._webview2_init_scheduled = True
                    self.after(delay, _init_webview2)
                except Exception:
                    pass
            try:
                tab_preview.bind('<Map>', lambda *_: _schedule_wv_init(80))
            except Exception:
                pass
            # Also try once at startup
            try:
                _schedule_wv_init(140)
            except Exception:
                pass
            # Save callbacks to allow re-initialization from later diagnostics/hints
            try:
                self._init_webview2_cb = _init_webview2
                self._schedule_wv_init_cb = _schedule_wv_init
            except Exception:
                pass
        else:
            # Without tkwebview2, keep using the Text fallback preview
            pass

        # Log tab content (Scrolled)
        try:
            self.log_text_container = ttk.Frame(tab_log)
            self.log_text_container.pack(fill='both', expand=True, padx=6, pady=6)
            self.txt_log = tk.Text(self.log_text_container, height=12)
            self.sb_log = ttk.Scrollbar(self.log_text_container, orient='vertical', command=self.txt_log.yview)
            self.txt_log.configure(yscrollcommand=self.sb_log.set)
            # Pack Scrollbar before Text
            self.sb_log.pack(side='right', fill='y')
            self.txt_log.pack(side='left', fill='both', expand=True)
        except Exception:
            self.txt_log = tk.Text(tab_log, height=12)
            self.txt_log.pack(fill='both', expand=True, padx=6, pady=6)
        # Flush any early buffered logs now that log widget exists
        try:
            if hasattr(self, '_early_logs') and self._early_logs:
                for _msg, _tag in self._early_logs:
                    try:
                        if _tag:
                            self.txt_log.insert('end', _msg + '\n', _tag)
                        else:
                            self.txt_log.insert('end', _msg + '\n')
                    except Exception:
                        pass
                self._early_logs.clear()
        except Exception:
            pass

        # Markdown preview (Scrolled)
        try:
            self.md_text_container = ttk.Frame(tab_md)
            self.md_text_container.pack(fill='both', expand=True, padx=6, pady=6)
            self.txt_md = tk.Text(self.md_text_container, height=12)
            self.sb_md = ttk.Scrollbar(self.md_text_container, orient='vertical', command=self.txt_md.yview)
            self.txt_md.configure(yscrollcommand=self.sb_md.set)
            self.sb_md.pack(side='right', fill='y')
            self.txt_md.pack(side='left', fill='both', expand=True)
        except Exception:
            self.txt_md = tk.Text(tab_md, height=12)
            self.txt_md.pack(fill='both', expand=True, padx=6, pady=6)

        # JSON preview (Scrolled)
        try:
            self.json_text_container = ttk.Frame(tab_json)
            self.json_text_container.pack(fill='both', expand=True, padx=6, pady=6)
            self.txt_json = tk.Text(self.json_text_container, height=12)
            self.sb_json = ttk.Scrollbar(self.json_text_container, orient='vertical', command=self.txt_json.yview)
            self.txt_json.configure(yscrollcommand=self.sb_json.set)
            self.sb_json.pack(side='right', fill='y')
            self.txt_json.pack(side='left', fill='both', expand=True)
        except Exception:
            self.txt_json = tk.Text(tab_json, height=12)
            self.txt_json.pack(fill='both', expand=True, padx=6, pady=6)
        # Initialize fonts for styled Text rendering (fallback path)
        self._init_fonts()
        # Capture base line heights of text widgets for later scale compensation
        try:
            self._text_widgets = []
            for _w_name in ('txt_html', 'txt_md', 'txt_json', 'txt_log'):
                w = getattr(self, _w_name, None)
                if w is not None:
                    self._text_widgets.append(w)
            self._text_base_heights = {}
            for w in self._text_widgets:
                try:
                    self._text_base_heights[w] = int(w.cget('height') or 12)
                except Exception:
                    self._text_base_heights[w] = 12
        except Exception:
            self._text_widgets = []
            self._text_base_heights = {}

        # Report which preview engine is active (helps user verify WebView2 is used)
        try:
            if self.webview2 is not None:
                log_message('info', self.log, 'Preview engine: WebView2')
            else:
                log_message('info', self.log, 'Preview engine: Text fallback')
        except Exception:
            pass

        # Copy toolbar omitted by design

        # Log color tags (for simple visual categorization)
        try:
            self.txt_log.tag_config('INFO', foreground='#8aa2ff')
            self.txt_log.tag_config('WARN', foreground='#ffb347')
            self.txt_log.tag_config('ERROR', foreground='#ff6f6f')
        except Exception:
            pass

        # Filters UI (Preview only) — place BELOW Notebook content (after its creation)
        pad = PAD_MAIN  # backward compat local name for existing layout code below
        self.ff = ttk.LabelFrame(frm, text=self._('filters.title'))
        try:
            self.ff.pack_forget()
        except Exception:
            pass
        try:
            self.nb.pack_forget()
        except Exception:
            pass
        try:
            self.pf.pack_forget()
        except Exception:
            pass
        self.nb.pack(fill='both', expand=True, padx=PAD_MAIN['padx'], pady=PAD_MAIN['pady'])
        self.ff.pack(fill='x', padx=PAD_MAIN['padx'], pady=PAD_MAIN['pady'])
        self.pf.pack(fill='x', padx=PAD_MAIN['padx'], pady=PAD_MAIN['pady'])
        # Row 0: Mods / Class (entries)
        self.lbl_filters_mods = ttk.Label(self.ff, text=self._('filters.mods'))
        self.lbl_filters_mods.grid(row=0, column=0, sticky='e', padx=(8, 4), pady=6)
        self.ent_filter_mods = ttk.Entry(self.ff, textvariable=self.var_filter_mods)
        self.ent_filter_mods.grid(row=0, column=1, sticky='ew', padx=(0, 8), pady=6)
        self.lbl_filters_class = ttk.Label(self.ff, text=self._('filters.class'))
        self.lbl_filters_class.grid(row=0, column=2, sticky='e', padx=(8, 4), pady=6)
        self.ent_filter_class = ttk.Entry(self.ff, textvariable=self.var_filter_class)
        self.ent_filter_class.grid(row=0, column=3, sticky='ew', padx=(0, 8), pady=6)

        # Row 1: Buttons (All / None)
        btnpad = PAD_TIGHT
        self.ff_btn_row = ttk.Frame(self.ff)
        self.ff_btn_row.grid(row=1, column=0, columnspan=4, sticky='w', padx=btnpad['padx'], pady=btnpad['pady'])
        try:
            self.btn_sym_all = ttk.Button(self.ff_btn_row, text=self._('filters.symptoms.all'), width=6, command=lambda: self._set_all_filters(True))
            self.btn_sym_all.pack(side='left', padx=(0,4))
            self.btn_sym_none = ttk.Button(self.ff_btn_row, text=self._('filters.symptoms.none'), width=8, command=lambda: self._set_all_filters(False))
            self.btn_sym_none.pack(side='left', padx=(0,8))
        except Exception:
            pass

        # Row 2: Severity checkboxes
        _ckpad = PAD_TIGHT
        self.ff_sev_row = ttk.Frame(self.ff)
        self.ff_sev_row.grid(row=2, column=0, columnspan=4, sticky='ew', padx=_ckpad['padx'], pady=_ckpad['pady'])
        try:
            self.ff_sev_row.columnconfigure(0, weight=0)
            self.ff_sev_row.columnconfigure(1, weight=1)
        except Exception:
            pass
        try:
            self.ff.rowconfigure(2, minsize=26)
        except Exception:
            pass
        try:
            self.lbl_severity = ttk.Label(self.ff_sev_row, text=self._('filters.severity'))
            self.lbl_severity.grid(row=0, column=0, sticky='w', padx=(0, 10))
        except Exception:
            self.lbl_severity = None
        try:
            self.ff_sev_checks = ttk.Frame(self.ff_sev_row)
            self.ff_sev_checks.grid(row=0, column=1, sticky='ew')
            self._sev_layout_scheduled = False
            self._sev_layout_last_avail = None
            self.ff_sev_checks.bind('<Configure>', self._on_sev_checks_configure)
        except Exception:
            self.ff_sev_checks = None
        self.chk_sev_c = ttk.Checkbutton(self.ff_sev_checks, text=self._('filters.sev.critical'), variable=self.var_filter_sev_critical)
        self.chk_sev_h = ttk.Checkbutton(self.ff_sev_checks, text=self._('filters.sev.high'), variable=self.var_filter_sev_high)
        self.chk_sev_m = ttk.Checkbutton(self.ff_sev_checks, text=self._('filters.sev.medium'), variable=self.var_filter_sev_medium)
        self.chk_sev_l = ttk.Checkbutton(self.ff_sev_checks, text=self._('filters.sev.low'), variable=self.var_filter_sev_low)
        self._relayout_severity_checks()
        try:
            if hasattr(self, 'ff_sev_row') and self.ff_sev_row is not None:
                self.ff_sev_row.bind('<Map>', lambda *_: self._on_sev_checks_configure())
        except Exception:
            pass
        try:
            self.after(120, lambda: self._on_sev_checks_configure())
        except Exception:
            pass
        for c in range(0, 4):
            self.ff.columnconfigure(c, weight=1 if c in (1, 3) else 0)

        # Row 3: Symptom checkboxes (labels from i18n; values bound to internal codes)
        try:
            self.ff_sym_row = ttk.Frame(self.ff)
            self.ff_sym_row.grid(row=3, column=0, columnspan=4, sticky='ew', padx=4, pady=(0,4))
            self.ff_sym_row.columnconfigure(0, weight=0)
            self.ff_sym_row.columnconfigure(1, weight=1, minsize=320)
            try:
                self.ff.rowconfigure(3, minsize=26)
            except Exception:
                pass
            try:
                sym_label = self._('impact.label')
                self.lbl_symptoms = ttk.Label(self.ff_sym_row, text=sym_label)
                self.lbl_symptoms.grid(row=0, column=0, sticky='w', padx=(0, 10))
            except Exception:
                self.lbl_symptoms = None
            # Right-side frame for symptom checkbuttons (auto-wrap via grid)
            try:
                self.ff_sym_checks = ttk.Frame(self.ff_sym_row)
                self.ff_sym_checks.grid(row=0, column=1, sticky='ew')
                # Due to frequent resizes, schedule via debounce instead of calling directly
                self._sym_layout_scheduled = False
                self._sym_layout_last_avail = None
                self.ff_sym_checks.bind('<Configure>', self._on_sym_checks_configure)
            except Exception:
                self.ff_sym_checks = None
            # Build initial row (uses current language order if provided)
            try:
                self._build_symptom_filter_row()
            except Exception:
                pass
        except Exception:
            pass

    def _wire_events(self):
        """Connect widget callbacks and setup dynamic enable/disable logic for outputs."""
        # Root/settings browse now handled exclusively in the Output Settings window.
        # React to language changes regardless of source (menu radiobutton)
        try:
            self.var_lang.trace_add('write', lambda *_: self.on_change_language())
        except Exception:
            pass

        # Update preview when font scale changes
        try:
            def _on_scale(*_):
                # Apply scaling and re-render while preserving current window geometry
                try:
                    self._apply_font_scale_preserving_size()
                except Exception:
                    # Fallback if anything fails
                    try:
                        self.apply_font_scale()
                    except Exception:
                        pass
                    try:
                        self._rerender_preview()
                    except Exception:
                        pass
                    try:
                        self._update_font_px_label()
                    except Exception:
                        pass
            self.var_font_scale.trace_add('write', lambda *_: _on_scale())
            # Some ttk.Scale implementations don't update variable on drag without command, add one
            if hasattr(self, 'sld_font_scale'):
                self.sld_font_scale.configure(command=lambda *_: _on_scale())
            # Ensure initial application so baseline capture occurs and initial value is reflected
            try:
                self._apply_font_scale_preserving_size()
            except Exception:
                try:
                    self.apply_font_scale()
                except Exception:
                    pass
        except Exception:
            pass

        # Update output field enabled state based on checkboxes
        def toggle_outputs(*_):
            """Enable/disable output path entries if they exist (created in Output Settings window)."""
            # If the Output Settings window is not open, return silently (getattr avoids exceptions).
            ent_html = getattr(self, 'ent_out_html', None)
            ent_md = getattr(self, 'ent_out_md', None)
            ent_json = getattr(self, 'ent_out_json', None)
            if not any([ent_html, ent_md, ent_json]):
                return
            state_html = 'normal' if self.var_enable_preview.get() else 'disabled'
            state_md = 'normal' if self.var_enable_md.get() else 'disabled'
            state_json = 'normal' if self.var_enable_json.get() else 'disabled'
            try:
                if ent_html is not None:
                    ent_html.configure(state=state_html)
                btn_html = getattr(self, 'btn_browse_html', None)
                if btn_html is not None:
                    btn_html.configure(state=state_html)
            except Exception:
                pass
            try:
                if ent_md is not None:
                    ent_md.configure(state=state_md)
                btn_md = getattr(self, 'btn_browse_md', None)
                if btn_md is not None:
                    btn_md.configure(state=state_md)
            except Exception:
                pass
            try:
                if ent_json is not None:
                    ent_json.configure(state=state_json)
                btn_json = getattr(self, 'btn_browse_json', None)
                if btn_json is not None:
                    btn_json.configure(state=state_json)
            except Exception:
                pass
        self.var_enable_preview.trace_add('write', toggle_outputs)
        self.var_enable_md.trace_add('write', toggle_outputs)
        self.var_enable_json.trace_add('write', toggle_outputs)
        # Re-render when wrapMethod coexistence toggle changes (affects preview and outputs)
        try:
            self.var_include_wrap.trace_add('write', lambda *_: self._on_include_wrap_toggle())
        except Exception:
            pass
        toggle_outputs()
        # Save settings on window close
        self.protocol('WM_DELETE_WINDOW', self._on_close)

        # --- Real-time filter updates (debounced) ---
        try:
            # Debounced schedule helper to avoid rendering on every keystroke
            self._filter_after_id = None
            def _schedule_rerender(delay_ms: int = 180):
                try:
                    if self._filter_after_id is not None:
                        self.after_cancel(self._filter_after_id)
                except Exception:
                    pass
                try:
                    self._filter_after_id = self.after(delay_ms, self._rerender_preview)
                except Exception:
                    # fallback immediate
                    self._rerender_preview()

            self._schedule_rerender = _schedule_rerender  # stash for reuse

            # Text filters: on change -> debounced re-render
            self.var_filter_mods.trace_add('write', lambda *_: _schedule_rerender())
            self.var_filter_class.trace_add('write', lambda *_: _schedule_rerender())
            # Severity toggles: immediate (still cheap) or lightly debounced
            self.var_filter_sev_critical.trace_add('write', lambda *_: _schedule_rerender(100))
            self.var_filter_sev_high.trace_add('write', lambda *_: _schedule_rerender(100))
            self.var_filter_sev_medium.trace_add('write', lambda *_: _schedule_rerender(100))
            self.var_filter_sev_low.trace_add('write', lambda *_: _schedule_rerender(100))
        except Exception:
            pass

    def _on_mode_toggle(self):
        # Update mode text and internal flags for downstream logic
        if self.var_mode_conflicts.get():
            self.var_mode_text.set(self._('mode.conflicts'))
            self.var_conflicts_only.set(True)
            self.var_include_reference.set(False)
        else:
            self.var_mode_text.set(self._('mode.reference'))
            self.var_conflicts_only.set(False)
            self.var_include_reference.set(True)

    def on_toggle_dark(self):
        # Update label and re-apply theme
        if self.var_dark_mode.get():
            self.var_dark_label.set(self._('theme.dark'))
        else:
            self.var_dark_label.set(self._('theme.light'))
        self.apply_theme()
        try:
            self._update_status_bar()
        except Exception:
            pass

    def _toggle_dark_clicked(self):
        """Toggle dark mode from the right-aligned theme button and update its label."""
        try:
            self.var_dark_mode.set(not bool(self.var_dark_mode.get()))
            # on_toggle_dark will update label and theme
            self.on_toggle_dark()
        except Exception:
            pass

    def apply_theme(self):
        dark = self.var_dark_mode.get()
        if dark:
            _setup_style_dark(self.style)
        else:
            _setup_style_light(self.style)
        # Keep the label in sync too
        self.var_dark_label.set(self._('theme.dark') if dark else self._('theme.light'))
        # Apply to text widget explicitly
        try:
            txt_log = getattr(self, 'txt_log', None)
            txt_md = getattr(self, 'txt_md', None)
            txt_json = getattr(self, 'txt_json', None)
            txt_html = getattr(self, 'txt_html', None)
            if txt_log is not None:
                apply_text_widget_theme(txt_log, dark)
            if txt_md is not None:
                apply_text_widget_theme(txt_md, dark)
            if txt_json is not None:
                apply_text_widget_theme(txt_json, dark)
            if txt_html is not None:
                apply_text_widget_theme(txt_html, dark)
        except Exception:
            pass
        # Re-render HTML with theme-aware styles if we have prior content
        if getattr(self, '_last_html_body', ''):
            try:
                self.set_preview_html_from_body(self._last_html_body)
            except Exception:
                pass
        # Re-render styled Text fallback if applicable
        if self.webview2 is None and getattr(self, 'txt_html', None) is not None and self._last_render_args:
            try:
                rep, c_only, inc_ref = self._last_render_args
                self.render_report_to_text(rep, conflicts_only=c_only, include_reference=inc_ref)
            except Exception:
                pass
        # Apply font scale to maintain scaling after theme changes
        try:
            # Use geometry-preserving variant so window size remains stable
            try:
                self._apply_font_scale_preserving_size()
            except Exception:
                self.apply_font_scale()
        except Exception:
            pass
        # Update status bar and menus to reflect theme changes
        try:
            self._update_status_bar()
        except Exception:
            pass
        try:
            self._build_menus()
        except Exception:
            pass

    # ---- Session Temp Directory Management ---------------------------------
    def _init_session_temp_dir(self):
        """Create per-run temp directory and prune old/oversized sessions.

        Layout:
            %TEMP%/RedScriptConflictGUI/session_YYYYMMDD_HHMMSS_<id>/
        """
        base = self._temp_base_dir
        try:
            base.mkdir(exist_ok=True)
        except Exception:
            pass
        # Prune existing sessions by age & size
        try:
            sessions = []  # list[(Path, datetime, int)]
            total = 0
            for p in base.glob('session_*'):
                try:
                    if not p.is_dir():
                        continue
                    stat = p.stat()
                    mtime = datetime.utcfromtimestamp(stat.st_mtime)
                    size = 0
                    try:
                        for f in p.rglob('*'):
                            if f.is_file():
                                size += f.stat().st_size
                    except Exception:
                        pass
                    sessions.append((p, mtime, size))
                    total += size
                except Exception:
                    pass
            # Age pruning
            cutoff = datetime.now(timezone.utc) - timedelta(days=getattr(self, '_temp_max_days', 5) or 5)
            for p, mtime, size in list(sessions):
                if mtime < cutoff:
                    try:
                        shutil.rmtree(p, ignore_errors=True)
                        total -= size
                        sessions.remove((p, mtime, size))
                    except Exception:
                        pass
            # Size pruning
            limit_bytes = (getattr(self, '_temp_max_total_mb', 300) or 300) * 1024 * 1024
            if total > limit_bytes:
                for p, mtime, size in sorted(sessions, key=lambda t: t[1]):  # oldest first
                    if total <= limit_bytes:
                        break
                    try:
                        shutil.rmtree(p, ignore_errors=True)
                        total -= size
                    except Exception:
                        pass
        except Exception:
            pass
        # Create session directory
        ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        sid = uuid.uuid4().hex[:8]
        session_dir = base / f'session_{ts}_{sid}'
        try:
            session_dir.mkdir(exist_ok=True)
            self.session_temp_dir = session_dir
        except Exception:
            self.session_temp_dir = None

    def _cleanup_session_temp_dir(self):
        if getattr(self, '_retain_temp_files', False):
            return
        # Remove any loose temp files created outside the session folder
        try:
            for p in list(getattr(self, '_loose_temp_files', []) or []):
                try:
                    Path(p).unlink(missing_ok=True)  # type: ignore[arg-type]
                except Exception:
                    pass
            self._loose_temp_files = []
        except Exception:
            pass
        # Remove the per-session temp directory
        d = getattr(self, 'session_temp_dir', None)
        if d:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass

    def _cleanup_session_temp_dir_atexit(self):
        try:
            self._cleanup_session_temp_dir()
        except Exception:
            pass
        # Also purge the base directory (best-effort) after cleaning session dir
        try:
            self._purge_temp_base_dir()
        except Exception:
            pass

    # --- Temp base directory purge (startup & exit) ----------------------------------
    def _purge_temp_base_dir(self):
        """Remove the entire RedScriptConflictGUI temp base directory safely.

        This is invoked at startup (to ensure a clean environment) and at app exit.
        It ignores errors (locked files, in-use handles)."""
        base = getattr(self, '_temp_base_dir', None)
        if not base:
            return
        try:
            if base.exists():
                shutil.rmtree(base, ignore_errors=True)
        except Exception:
            pass

    # --- WebView2 Runtime probe (diagnostics only) ----------------------------------
    def _probe_webview2_runtime(self) -> Dict[str, Any]:
        """Best-effort probe for Edge WebView2 Runtime presence and version.

        Returns: { found: bool, version: Optional[str], path: Optional[str] }
        Note: This is diagnostic only; initialization still relies on tkwebview2 internals.
        """
        info: Dict[str, Any] = {'found': False, 'version': None, 'path': None, 'arch': None}
        try:
            # Windows only: check registry keys
            if sys.platform.startswith('win'):
                try:
                    import winreg  # type: ignore
                    # 64-bit machine has entries under both 64/32 views depending on installer
                    reg_paths = [
                        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients", 'x64'),
                        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients", 'x86'),
                    ]
                    product_code = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'  # Evergreen Runtime
                    for root, base, arch in reg_paths:
                        try:
                            with winreg.OpenKey(root, base) as k:
                                i = 0
                                while True:
                                    try:
                                        sub = winreg.EnumKey(k, i)
                                    except OSError:
                                        break
                                    i += 1
                                    if product_code and product_code.lower() not in sub.lower():
                                        continue
                                    try:
                                        with winreg.OpenKey(k, sub) as sk:
                                            try:
                                                version, _ = winreg.QueryValueEx(sk, 'pv')
                                            except OSError:
                                                version = None
                                            try:
                                                name, _ = winreg.QueryValueEx(sk, 'name')
                                            except OSError:
                                                name = None
                                            info['found'] = True
                                            info['version'] = version
                                            info['path'] = name
                                            info['arch'] = arch
                                            return info
                                    except OSError:
                                        continue
                        except OSError:
                            continue
                except Exception:
                    pass
            # Fallback: look for default install directories (best effort)
            try:
                common_dirs = [
                    (os.path.expandvars(r"%ProgramFiles%\Microsoft\EdgeWebView\Application"), 'x64'),
                    (os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\EdgeWebView\Application"), 'x86'),
                ]
                for d, arch in common_dirs:
                    if not d or not os.path.isdir(d):
                        continue
                    # pick highest version folder
                    try:
                        subs = [p for p in os.listdir(d) if os.path.isdir(os.path.join(d, p))]
                        if subs:
                            subs.sort(reverse=True)
                            info['found'] = True
                            info['version'] = subs[0]
                            info['path'] = os.path.join(d, subs[0])
                            info['arch'] = arch
                            return info
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass
        return info

    # --- Fixed Version WebView2 auto-detection ------------------------------------
    def _maybe_set_fixed_webview2(self) -> Optional[str]:
        """If a fixed-version WebView2 is bundled, set WEBVIEW2_BROWSER_EXECUTABLE_FOLDER.

        Priority:
          1) Respect pre-set WEBVIEW2_BROWSER_EXECUTABLE_FOLDER (do nothing)
          2) exe-adjacent 'wv2fixed-x64' on 64-bit OS
          3) exe-adjacent 'wv2fixed-x86'

        Returns the folder path used, or None if not set.
        """
        try:
            # Respect existing configuration
            cur = os.environ.get('WEBVIEW2_BROWSER_EXECUTABLE_FOLDER')
            if cur and os.path.isdir(cur):
                try:
                    log_message('info', self.log, f"Using pre-set WEBVIEW2_BROWSER_EXECUTABLE_FOLDER={cur}")
                except Exception:
                    pass
                return cur
            # Determine candidates near the executable/source directory
            base = getattr(self, '_exe_dir', None)
            if not base:
                base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else SRC_DIR
            candidates: list[tuple[str, str]] = []
            try:
                import platform as _plat
                os_is_64 = _plat.machine().endswith('64')
            except Exception:
                os_is_64 = True
            # Prefer x64 on 64-bit OS
            if os_is_64:
                candidates.append((str(base / 'wv2fixed-x64'), 'x64'))
            candidates.append((str(base / 'wv2fixed-x86'), 'x86'))
            for folder, arch in candidates:
                try:
                    if os.path.isdir(folder):
                        os.environ['WEBVIEW2_BROWSER_EXECUTABLE_FOLDER'] = folder
                        try:
                            log_message('info', self.log, f"Using fixed WebView2 ({arch}) at {folder}")
                        except Exception:
                            pass
                        return folder
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _update_font_px_label(self):
        """Update the font size label to show multiplier (e.g. 90%)."""
        try:
            scale = float(self.var_font_scale.get() or 1.0)
            # Clamp to 1.5 (150%). Earlier logic clamped at 1.4 causing stalled updates above 140%.
            scale = max(0.5, min(1.5, scale))
            self.var_font_px.set(f"{int(scale*100)}%")
        except Exception:
            self.var_font_px.set("")

    # Automatic button height sync disabled (fixed value)

    def log(self, msg: str):
        tag = None
        if msg.startswith('[WARN]'):
            tag = 'WARN'
        elif msg.startswith('[ERROR]'):
            tag = 'ERROR'
        elif msg.startswith('[INFO]') or msg.startswith('[START]') or msg.startswith('[DONE]'):
            tag = 'INFO'
        lw = getattr(self, '_get_log_widget', lambda: None)()
        if lw is None:
            try:
                self._early_logs.append((msg, tag))
            except Exception:
                pass
            return
        try:
            if tag:
                lw.insert('end', msg + '\n', tag)
            else:
                lw.insert('end', msg + '\n')
            lw.see('end')
        except Exception:
            pass

    # --- Commonized helpers (template/theme) ---------------------------------
    def _is_dark_mode(self) -> bool:
        try:
            return bool(self.var_dark_mode.get())
        except Exception:
            return False

    def _theme_class(self) -> str:
        return 'dark' if self._is_dark_mode() else ''

    def _render_full_html(self, body_html: str, inline_css: bool, tr=None) -> tuple[str, bool]:
        """Central wrapper applying template placeholders consistently.

        Returns (full_html, used_external_template_flag).
        """
        t0 = time.time()
        try:
            tpl, used_tpl = _load_template_and_css(inline_css=inline_css)
        except Exception:
            tpl, used_tpl = ('<html><body>{{BODY}}</body></html>', False)
        _t = tr if callable(tr) else self._
        try:
            header = _t('report.header')
        except Exception:
            header = 'Report'
        # Normalize header to str for type checkers / safety (some translators might not return plain str)
        try:
            if not isinstance(header, str):
                header = str(header)
        except Exception:
            header = 'Report'
        try:
            full_html = (tpl
                         .replace('{{TITLE}}', header)
                         .replace('{{HEADER_LABEL}}', header)
                         .replace('{{THEME_CLASS}}', self._theme_class())
                         .replace('{{BODY}}', body_html))
        except Exception:
            full_html = '<html><body>' + body_html + '</body></html>'
        try:
            self._timings['html_wrap'] = self._timings.get('html_wrap', 0.0) + (time.time() - t0) * 1000.0
        except Exception:
            pass
        return full_html, used_tpl

    # --- Safe text widget update helper (guards Optional widgets) -----------
    def _safe_set_text(self, widget_attr: str, content: str):  # pragma: no cover - GUI
        """Safely update a tk.Text widget attribute if it exists.

        Schedules on the Tk event loop via after(0, ...) to avoid threading
        issues. Silently no-ops if the attribute is missing or not a widget.
        """
        try:
            widget = getattr(self, widget_attr, None)
        except Exception:
            return
        if widget is None:
            return
        def _update():
            try:
                widget.configure(state='normal')
                widget.delete('1.0', 'end')
                widget.insert('1.0', content)
                widget.configure(state='normal')
            except Exception:
                pass
        try:
            self.after(0, _update)
        except Exception:
            # If after not yet available (very early), fallback immediate
            _update()

    def apply_font_scale(self):
        """Apply current font scale (multiplier) to text widgets & HTML preview.

        Unlike the previous implementation (which forced a unified 12px base), this keeps each
        widget's original font size as its base and multiplies by the scale so relative differences
        remain intact.
        """
        try:
            scale = float(self.var_font_scale.get() or 1.0)
        except Exception:
            scale = 1.0
        scale = max(0.5, min(1.5, scale))

        try:
            import tkinter.font as tkfont
            # Lazy capture of per-widget base fonts the first time we scale
            widgets = [getattr(self, 'txt_md', None), getattr(self, 'txt_json', None), getattr(self, 'txt_log', None), getattr(self, 'txt_html', None)]
            if not hasattr(self, '_content_font_bases'):
                self._content_font_bases = {}
                for w in widgets:
                    try:
                        if w is None:
                            continue
                        f = tkfont.Font(font=w.cget('font'))
                        self._content_font_bases[w] = {
                            'family': f.cget('family'),
                            'size': int(f.cget('size') or 12),
                            'weight': f.cget('weight'),
                            'slant': f.cget('slant')
                        }
                    except Exception:
                        pass
            # Also capture and scale Text fallback rendering fonts used by tags (h1/h2/mono)
            try:
                if hasattr(self, 'font_base') and self.font_base is not None:
                    if not hasattr(self, '_text_font_bases'):
                        self._text_font_bases = {}
                        try:
                            self._text_font_bases['base'] = int(self.font_base.cget('size') or 10)
                        except Exception:
                            self._text_font_bases['base'] = 10
                        try:
                            self._text_font_bases['bold'] = int(self.font_bold.cget('size') or self._text_font_bases['base'])
                        except Exception:
                            self._text_font_bases['bold'] = self._text_font_bases['base']
                        try:
                            self._text_font_bases['h1'] = int(self.font_h1.cget('size') or (self._text_font_bases['base'] + 4))
                        except Exception:
                            self._text_font_bases['h1'] = self._text_font_bases['base'] + 4
                        try:
                            self._text_font_bases['h2'] = int(self.font_h2.cget('size') or (self._text_font_bases['base'] + 2))
                        except Exception:
                            self._text_font_bases['h2'] = self._text_font_bases['base'] + 2
                        try:
                            self._text_font_bases['mono'] = int(self.font_mono.cget('size') or self._text_font_bases['base'])
                        except Exception:
                            self._text_font_bases['mono'] = self._text_font_bases['base']
                        try:
                            self._text_font_bases['meta'] = int(self.font_meta.cget('size') or max(self._text_font_bases['base'] - 1, 8))
                        except Exception:
                            self._text_font_bases['meta'] = max(self._text_font_bases['base'] - 1, 8)
                        try:
                            self._text_font_bases['impact'] = int(self.font_impact.cget('size') or self._text_font_bases['base'])
                        except Exception:
                            self._text_font_bases['impact'] = self._text_font_bases['base']
                    # Apply scaled sizes to these Font objects (tags will follow automatically)
                    try:
                        self.font_base.configure(size=max(6, int(round(self._text_font_bases['base'] * scale))))
                    except Exception:
                        pass
                    try:
                        self.font_bold.configure(size=max(6, int(round(self._text_font_bases['bold'] * scale))))
                    except Exception:
                        pass
                    try:
                        self.font_h1.configure(size=max(7, int(round(self._text_font_bases['h1'] * scale))))
                    except Exception:
                        pass
                    try:
                        self.font_h2.configure(size=max(7, int(round(self._text_font_bases['h2'] * scale))))
                    except Exception:
                        pass
                    try:
                        self.font_mono.configure(size=max(6, int(round(self._text_font_bases['mono'] * scale))))
                    except Exception:
                        pass
                    try:
                        self.font_meta.configure(size=max(6, int(round(self._text_font_bases['meta'] * scale))))
                    except Exception:
                        pass
                    try:
                        self.font_impact.configure(size=max(6, int(round(self._text_font_bases['impact'] * scale))))
                    except Exception:
                        pass
            except Exception:
                pass
            # Apply scaled size per widget
            for w in widgets:
                try:
                    if w is None:
                        continue
                    base = self._content_font_bases.get(w)
                    if not base:
                        continue
                    new_size = max(6, int(round(base['size'] * scale)))
                    f = tkfont.Font(font=w.cget('font'))
                    f.configure(size=new_size)
                    w.configure(font=f)
                except Exception:
                    pass
            # After scaling fonts, adjust displayed line counts to keep pixel height stable
            try:
                self._adjust_text_widget_heights_for_scale()
            except Exception:
                pass
        except Exception:
            pass
        # Ensure widget fonts pick up updated base family (if changed elsewhere)
        try:
            self._refresh_text_widget_font_family()
        except Exception:
            pass

    def _refresh_text_widget_font_family(self):  # pragma: no cover - GUI
        """Propagate current base font family to Markdown/JSON/Log widgets.

        Reason: earlier each widget received an independent tkfont.Font clone,
        so later family changes (e.g. Noto Sans selection) did not propagate.
        We mutate the existing Font objects bound to the widgets so future
        scaling preserves per-widget size differentials while sharing family.
        """
        try:
            import tkinter.font as tkfont
            family = None
            try:
                if hasattr(self, 'font_base') and self.font_base is not None:
                    family = self.font_base.cget('family')
            except Exception:
                family = None
            if not family:
                return
            widgets = [getattr(self, 'txt_md', None), getattr(self, 'txt_json', None), getattr(self, 'txt_log', None)]
            for w in widgets:
                if w is None:
                    continue
                try:
                    f = tkfont.Font(font=w.cget('font'))
                    if f.cget('family') != family:
                        f.configure(family=family)
                        w.configure(font=f)
                except Exception:
                    pass
        except Exception:
            pass

    # --- Timing context manager -------------------------------------------
    from contextlib import contextmanager as _cm
    @_cm
    def _timed(self, label: str):  # pragma: no cover - GUI
        t0 = time.time()
        try:
            yield
        finally:
            try:
                self._timings[label] = self._timings.get(label, 0.0) + (time.time() - t0) * 1000.0
            except Exception:
                pass

    def _apply_font_scale_preserving_size(self):
        """Apply font scaling and re-render preview without changing the window size.

        - Captures current geometry (size/position) before scaling
        - Applies scaling and triggers preview re-render
        - Restores geometry unless the window is maximized (state == 'zoomed')
        """
        try:
            try:
                state = self.state()
            except Exception:
                state = None
            # Snapshot geometry
            try:
                self.update_idletasks()
            except Exception:
                pass
            w = int(self.winfo_width() or 0)
            h = int(self.winfo_height() or 0)
            x = int(self.winfo_x() or 0)
            y = int(self.winfo_y() or 0)
            # Track if user moved window so we avoid forcing position restoration.
            self._fs_user_moved = False
            move_threshold = 3  # Pixel delta threshold to treat as a user move.
            # Pre-lock window size to prevent geometry growth due to layout recalcs
            locked = False
            sw = sh = None
            if state != 'zoomed' and w > 1 and h > 1:
                try:
                    sw = int(self.winfo_screenwidth() or 0)
                    sh = int(self.winfo_screenheight() or 0)
                except Exception:
                    sw = sh = None
                try:
                    self.minsize(w, h)
                except Exception:
                    pass
                try:
                    self.maxsize(w, h)
                except Exception:
                    pass
                locked = True

            # Do the scaling work
            try:
                self.apply_font_scale()
            except Exception:
                pass
            try:
                self._rerender_preview()
            except Exception:
                pass
            try:
                self._update_font_px_label()
            except Exception:
                pass

            # Restore geometry / defer unlock if not maximized and meaningful
            if state != 'zoomed' and w > 1 and h > 1:
                # Restore size/position immediately while keeping min/max lock
                try:
                    pos_allowed = not (getattr(self, '_fs_user_moved', False) or getattr(self, '_first_run', False))
                    if not pos_allowed:
                        self.geometry(f"{w}x{h}")
                    else:
                        self.geometry(f"{w}x{h}+{x}+{y}")
                except Exception:
                    pass

                def _unlock(final: bool = True):
                    # Enforce geometry again after a few frames then release size locks
                    try:
                        pos_allowed2 = not (getattr(self, '_fs_user_moved', False) or getattr(self, '_first_run', False))
                        if not pos_allowed2:
                            self.geometry(f"{w}x{h}")
                        else:
                            self.geometry(f"{w}x{h}+{x}+{y}")
                    except Exception:
                        pass
                    if final:
                        try:
                            if sw and sh:
                                self.maxsize(sw, sh)
                            else:
                                self.maxsize(10000, 10000)
                        except Exception:
                            pass
                        try:
                            self.minsize(720, 720)
                        except Exception:
                            pass

                # Multiple short delayed restores to suppress late layout expansion.
                try:
                    self.after(0, lambda: _unlock(False))      # immediately after idle
                except Exception:
                    pass
                try:
                    self.after(40, lambda: _unlock(False))     # roughly one frame later (~40ms)
                except Exception:
                    pass
                # Final unlock delayed until after watch/guard period to prevent late growth.
                try:
                    self.after(1400, _unlock)  # final unlock after guard window
                except Exception:
                    pass

                # Rebound watch: prevent post-unlock size creep on some platforms.
                try:
                    if not hasattr(self, '_fs_watch_active'):
                        self._fs_watch_active = False
                    if getattr(self, '_fs_watch_active', False):
                        # Skip if already watching.
                        return
                    self._fs_watch_active = True
                    target_w, target_h = w, h

                    def _watch(step=0):
                        try:
                            cur_w = int(self.winfo_width() or 0)
                            cur_h = int(self.winfo_height() or 0)
                            cur_x = int(self.winfo_x() or 0)
                            cur_y = int(self.winfo_y() or 0)
                            # Detect user move
                            if not getattr(self, '_fs_user_moved', False):
                                if abs(cur_x - x) > move_threshold or abs(cur_y - y) > move_threshold:
                                    self._fs_user_moved = True
                            # Enforce: allow <=1px; otherwise snap back.
                            if abs(cur_w - target_w) > 1 or abs(cur_h - target_h) > 1:
                                try:
                                    pos_allowed3 = not (getattr(self, '_fs_user_moved', False) or getattr(self, '_first_run', False))
                                    if not pos_allowed3:
                                        self.geometry(f"{target_w}x{target_h}")
                                    else:
                                        self.geometry(f"{target_w}x{target_h}+{x}+{y}")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # Limit watch iterations (~600ms total: 0,40,...,560).
                        if step < 14:
                            try:
                                self.after(40, lambda: _watch(step + 1))
                            except Exception:
                                pass
                        else:
                            self._fs_watch_active = False

                    # Start watch slightly after first unlock (unlock ~120ms -> start ~160ms).
                    try:
                        self.after(160, _watch)
                    except Exception:
                        self._fs_watch_active = False
                except Exception:
                    pass
                    # <Configure> guard: clamp size during late layout expansion attempts.
                    try:
                        guard_duration_ms = 1200  # Guard total duration (ms).
                        target_w, target_h = w, h
                        if not hasattr(self, '_fs_geom_guard_active') or not self._fs_geom_guard_active:
                            self._fs_geom_guard_active = True
                            self._fs_geom_guard_reentry = False
                            start_ts = time.time()

                            def _fs_geom_guard(event=None):
                                # Reentry guard
                                if getattr(self, '_fs_geom_guard_reentry', False):
                                    return
                                try:
                                    cur_x = int(self.winfo_x() or 0)
                                    cur_y = int(self.winfo_y() or 0)
                                    # Detect user move; stop forcing position once moved.
                                    if not getattr(self, '_fs_user_moved', False):
                                        if abs(cur_x - x) > move_threshold or abs(cur_y - y) > move_threshold:
                                            self._fs_user_moved = True
                                    if (time.time() - start_ts) * 1000.0 > guard_duration_ms:
                                        # Guard expired: unbind and stop.
                                        try:
                                            self.unbind('<Configure>', self._fs_geom_guard_bind_id)
                                        except Exception:
                                            pass
                                        self._fs_geom_guard_active = False
                                        return
                                    cur_w = int(self.winfo_width() or 0)
                                    cur_h = int(self.winfo_height() or 0)
                                    # Allow up to +1px; restore if exceeded.
                                    if cur_w - target_w > 1 or cur_h - target_h > 1:
                                        try:
                                            self._fs_geom_guard_reentry = True
                                            pos_allowed4 = not (getattr(self, '_fs_user_moved', False) or getattr(self, '_first_run', False))
                                            if not pos_allowed4:
                                                self.geometry(f"{target_w}x{target_h}")
                                            else:
                                                self.geometry(f"{target_w}x{target_h}+{x}+{y}")
                                        finally:
                                            self._fs_geom_guard_reentry = False
                                except Exception:
                                    pass

                            try:
                                self._fs_geom_guard_bind_id = self.bind('<Configure>', _fs_geom_guard, add='+')
                            except Exception:
                                self._fs_geom_guard_active = False
                    except Exception:
                        pass
        except Exception:
            return

    def _adjust_text_widget_heights_for_scale(self):
        """Inverse-adjust Text widget 'height' lines when scale > 1.0 to curb toplevel growth.

        Keeps approximate pixel height of each text area constant so overall window doesn't request
        additional vertical space at larger font scales (observed threshold ~115%).
        """
        try:
            try:
                s = float(self.var_font_scale.get() or 1.0)
            except Exception:
                s = 1.0
            widgets = getattr(self, '_text_widgets', []) or []
            bases = getattr(self, '_text_base_heights', {}) or {}
            if not widgets or not bases:
                return
            if s <= 1.0:
                # Use original height values
                for w in widgets:
                    try:
                        base = bases.get(w, 12)
                        if int(w.cget('height')) != base:
                            w.configure(height=base)
                    except Exception:
                        pass
                return
            # scale > 1.0
            for w in widgets:
                try:
                    base = bases.get(w, 12)
                    new_lines = max(4, int(round(base / s)))
                    if int(w.cget('height')) != new_lines:
                        w.configure(height=new_lines)
                except Exception:
                    pass
        except Exception:
            pass

    # WebView2 note: callers already trigger _rerender_preview, so no explicit
    # re-render is required here. Text fallback reflects font size changes immediately.

    def _log_i18n(self, prefix: str, key: str, **kwargs):
        """Log a localized message using an i18n key.

        Example:
            self._log_i18n('[START]', 'log.startScan', path=str(root))
        """
        try:
            msg = self._(key)
            for k, v in (kwargs or {}).items():
                msg = msg.replace('{' + k + '}', str(v))
            self.log(f"{prefix} {msg}")
        except Exception:
            # Fallback to key if missing
            self.log(f"{prefix} {key}")


    def on_browse_root(self):
        import time, threading
        kind = 'root'
        # Delayed dispatch (B)
        if getattr(self, '_browse_delay_mode', False) and not getattr(self, '_browse_delay_skip_next', False):
            self._browse_delay_skip_next = True
            try: self.log(f"[BROWSE] schedule delay=50ms kind={kind}")
            except Exception: pass
            self.after(50, self.on_browse_root)
            return
        if getattr(self, '_browse_delay_skip_next', False):
            self._browse_delay_skip_next = False
        t0 = time.time()
        try: self.log(f"[BROWSE] start kind={kind}")
        except Exception: pass
        # Setup initial directory
        try:
            cur = (self.var_root.get() or '').strip()
            init = cur if cur and Path(cur).exists() else str(self._exe_dir)
        except Exception:
            init = str(getattr(self, '_exe_dir', Path.cwd()))
        t1 = time.time()
        # Watchdog thread
        done = {'v': False}
        def _watch():
            n = 1
            while not done['v']:
                time.sleep(3)
                if done['v']:
                    break
                try: self.log(f"[BROWSE][WATCHDOG] kind={kind} still waiting +{int(time.time()-t1)}s")
                except Exception: pass
        threading.Thread(target=_watch, daemon=True).start()
        # Busy cursor feedback
        try:
            old_cursor = self['cursor']
            self.configure(cursor='wait')
            self.update_idletasks()
        except Exception:
            old_cursor = ''
        dryrun = bool(os.environ.get('RCR_BROWSE_DRYRUN'))
        if dryrun:
            p = ''
        else:
            try:
                p = filedialog.askdirectory(parent=self, title=self._('scan.root'), initialdir=init, mustexist=True)
            except Exception:
                p = ''
        t2 = time.time()
        done['v'] = True
        # Restore cursor
        try:
            if old_cursor is not None:
                self.configure(cursor=old_cursor)
        except Exception:
            pass
        # Post-set
        if p:
            try: self.var_root.set(p)
            except Exception: pass
        t3 = time.time()
        try:
            self.log(
                f"[BROWSE] kind={kind} prep={(t1-t0)*1000:.1f}ms dialog={(t2-t1)*1000:.1f}ms post={(t3-t2)*1000:.1f}ms total={(t3-t0)*1000:.1f}ms init='{init}' result='{p}'")
        except Exception:
            pass

    def on_browse_json(self):
        import time, threading
        kind='json'
        if getattr(self,'_browse_delay_mode', False) and not getattr(self,'_browse_delay_skip_next', False):
            self._browse_delay_skip_next = True
            try: self.log(f"[BROWSE] schedule delay=50ms kind={kind}")
            except Exception: pass
            self.after(50, self.on_browse_json)
            return
        if getattr(self,'_browse_delay_skip_next', False):
            self._browse_delay_skip_next = False
        t0=time.time()
        try: self.log(f"[BROWSE] start kind={kind}")
        except Exception: pass
        cur = (self.var_out_json.get() or '').strip()
        init_dir = str(Path(cur).parent) if cur else str(self._exe_dir)
        t1=time.time()
        done={'v':False}
        def _watch():
            while not done['v']:
                time.sleep(3)
                if done['v']: break
                try: self.log(f"[BROWSE][WATCHDOG] kind={kind} still waiting +{int(time.time()-t1)}s")
                except Exception: pass
        threading.Thread(target=_watch, daemon=True).start()
        try:
            old_cursor=self['cursor']
            self.configure(cursor='wait'); self.update_idletasks()
        except Exception:
            old_cursor=''
        dryrun = bool(os.environ.get('RCR_BROWSE_DRYRUN'))
        if dryrun:
            p=''
        else:
            try:
                p = filedialog.asksaveasfilename(parent=self, title=self._('scan.outJson'), defaultextension='.json', initialdir=init_dir, filetypes=[('JSON', '*.json'), ('All Files', '*.*')])
            except Exception:
                p=''
        # Capture dialog completion timestamp for duration metrics
        t2 = time.time()
                # Store current font for next switch.
        try: self.configure(cursor=old_cursor)
        except Exception: pass
        if p:
            try: self.var_out_json.set(p)
            except Exception: pass
        t3=time.time()
        try: self.log(f"[BROWSE] kind={kind} prep={(t1-t0)*1000:.1f}ms dialog={(t2-t1)*1000:.1f}ms post={(t3-t2)*1000:.1f}ms total={(t3-t0)*1000:.1f}ms init='{init_dir}' result='{p}'")
        except Exception: pass

    def on_browse_md(self):
        import time, threading
        kind='md'
        if getattr(self,'_browse_delay_mode', False) and not getattr(self,'_browse_delay_skip_next', False):
            self._browse_delay_skip_next = True
            try: self.log(f"[BROWSE] schedule delay=50ms kind={kind}")
            except Exception: pass
            self.after(50, self.on_browse_md)
            return
        if getattr(self,'_browse_delay_skip_next', False): self._browse_delay_skip_next=False
        t0=time.time();
        try: self.log(f"[BROWSE] start kind={kind}")
        except Exception: pass
        cur = (self.var_out_md.get() or '').strip()
        init_dir = str(Path(cur).parent) if cur else str(self._exe_dir)
        t1=time.time(); done={'v':False}
        def _watch():
            while not done['v']:
                time.sleep(3)
                if done['v']: break
                try: self.log(f"[BROWSE][WATCHDOG] kind={kind} still waiting +{int(time.time()-t1)}s")
                except Exception: pass
        threading.Thread(target=_watch, daemon=True).start()
        try: old_cursor=self['cursor']; self.configure(cursor='wait'); self.update_idletasks()
        except Exception: old_cursor=''
        dryrun = bool(os.environ.get('RCR_BROWSE_DRYRUN'))
        if dryrun:
            p=''
        else:
            try:
                p = filedialog.asksaveasfilename(parent=self, title=self._('scan.outMd'), defaultextension='.md', initialdir=init_dir, filetypes=[('Markdown', '*.md'), ('All Files', '*.*')])
            except Exception: p=''
        t2=time.time(); done['v']=True
        try: self.configure(cursor=old_cursor)
        except Exception: pass
        if p:
            try: self.var_out_md.set(p)
            except Exception: pass
        t3=time.time()
        try: self.log(f"[BROWSE] kind={kind} prep={(t1-t0)*1000:.1f}ms dialog={(t2-t1)*1000:.1f}ms post={(t3-t2)*1000:.1f}ms total={(t3-t0)*1000:.1f}ms init='{init_dir}' result='{p}'")
        except Exception: pass

    def on_browse_html(self):
        import time, threading
        kind='html'
        if getattr(self,'_browse_delay_mode', False) and not getattr(self,'_browse_delay_skip_next', False):
            self._browse_delay_skip_next=True
            try: self.log(f"[BROWSE] schedule delay=50ms kind={kind}")
            except Exception: pass
            self.after(50, self.on_browse_html); return
        if getattr(self,'_browse_delay_skip_next', False): self._browse_delay_skip_next=False
        t0=time.time();
        try: self.log(f"[BROWSE] start kind={kind}")
        except Exception: pass
        cur = (self.var_out_html.get() or '').strip()
        init_dir = str(Path(cur).parent) if cur else str(self._exe_dir)
        t1=time.time(); done={'v':False}
        def _watch():
            while not done['v']:
                time.sleep(3)
                if done['v']: break
                try: self.log(f"[BROWSE][WATCHDOG] kind={kind} still waiting +{int(time.time()-t1)}s")
                except Exception: pass
        threading.Thread(target=_watch, daemon=True).start()
        try: old_cursor=self['cursor']; self.configure(cursor='wait'); self.update_idletasks()
        except Exception: old_cursor=''
        dryrun = bool(os.environ.get('RCR_BROWSE_DRYRUN'))
        if dryrun:
            p=''
        else:
            try:
                p = filedialog.asksaveasfilename(parent=self, title=self._('scan.outHtml'), defaultextension='.html', initialdir=init_dir, filetypes=[('HTML', '*.html'), ('All Files', '*.*')])
            except Exception: p=''
        t2=time.time(); done['v']=True
        try: self.configure(cursor=old_cursor)
        except Exception: pass
        if p:
            try: self.var_out_html.set(p)
            except Exception: pass
        t3=time.time()
        try: self.log(f"[BROWSE] kind={kind} prep={(t1-t0)*1000:.1f}ms dialog={(t2-t1)*1000:.1f}ms post={(t3-t2)*1000:.1f}ms total={(t3-t0)*1000:.1f}ms init='{init_dir}' result='{p}'")
        except Exception: pass

    def on_browse_settings(self):
        import time, threading
        kind='settings'
        if getattr(self,'_browse_delay_mode', False) and not getattr(self,'_browse_delay_skip_next', False):
            self._browse_delay_skip_next=True
            try: self.log(f"[BROWSE] schedule delay=50ms kind={kind}")
            except Exception: pass
            self.after(50, self.on_browse_settings); return
        if getattr(self,'_browse_delay_skip_next', False): self._browse_delay_skip_next=False
        t0=time.time();
        try: self.log(f"[BROWSE] start kind={kind}")
        except Exception: pass
        try:
            cur = (self.var_settings_path.get() or '').strip()
            initialdir = str(Path(cur).parent) if cur else str(self._exe_dir)
            if not Path(initialdir).exists():
                initialdir = str(getattr(self, '_exe_dir', Path.cwd()))
            initialfile = Path(cur).name if cur else 'redscript_conflict_gui.json'
        except Exception:
            initialdir = str(getattr(self, '_exe_dir', Path.cwd())); initialfile='redscript_conflict_gui.json'
        t1=time.time(); done={'v':False}
        def _watch():
            while not done['v']:
                time.sleep(3)
                if done['v']: break
                try: self.log(f"[BROWSE][WATCHDOG] kind={kind} still waiting +{int(time.time()-t1)}s")
                except Exception: pass
        threading.Thread(target=_watch, daemon=True).start()
        try: old_cursor=self['cursor']; self.configure(cursor='wait'); self.update_idletasks()
        except Exception: old_cursor=''
        dryrun = bool(os.environ.get('RCR_BROWSE_DRYRUN'))
        if dryrun:
            p=''
        else:
            try:
                p = filedialog.asksaveasfilename(parent=self, title=self._('scan.saveAs'), defaultextension='.json', initialdir=initialdir, initialfile=initialfile, filetypes=[('JSON', '*.json'), ('All Files', '*.*')])
            except Exception: p=''
        t2=time.time(); done['v']=True
        try: self.configure(cursor=old_cursor)
        except Exception: pass
        if p:
            try: self.var_settings_path.set(p)
            except Exception: pass
            try: self._settings_path = Path(p)
            except Exception: pass
            try: self._save_settings_pointer()
            except Exception: pass
        t3=time.time()
        try: self.log(f"[BROWSE] kind={kind} prep={(t1-t0)*1000:.1f}ms dialog={(t2-t1)*1000:.1f}ms post={(t3-t2)*1000:.1f}ms total={(t3-t0)*1000:.1f}ms init='{initialdir}' file='{initialfile}' result='{p}'")
        except Exception: pass

    # --- Core availability helper -------------------------------------------------
    def _require_core(self) -> bool:
        """Ensure the core scanner module is available; show error if missing.

        Returns True when core is usable; False otherwise.
        Centralizes the import failure UX so multiple call sites stay minimal.
        """
        try:
            if core is None:
                try:
                    messagebox.showerror(self._('dialog.cannotRun.title'), self._('dialog.cannotRun.body'))
                except Exception:
                    pass
                return False
        except Exception:
            return False
        return True

    def on_open_folder(self):
        try:
            out_md = Path(self.var_out_md.get())
            folder = out_md.parent
            if sys.platform.startswith('win'):
                os.startfile(str(folder))
            else:
                import subprocess
                subprocess.Popen(['xdg-open', str(folder)])
        except Exception as e:
            messagebox.showerror(self._('dialog.error.title'), f'Failed to open folder:\n{e}')

    def open_preview_in_browser(self):
        """Render the current preview (with filters, theme, scale) to a temp HTML file and open in the default browser."""
        try:
            html_body = getattr(self, '_last_html_body', '')
            if not html_body and self._last_report is not None:
                # Build on the fly using current mode and filters
                report = self._last_report
                conflicts_only = self.var_mode_conflicts.get()
                include_reference = not conflicts_only
                filtered = self._filter_report_for_preview(report, conflicts_only=conflicts_only)
                html_body = self.build_html_body(filtered, conflicts_only=conflicts_only, include_reference=include_reference)
            if not html_body:
                messagebox.showinfo(self._('dialog.info.title'), self._('dialog.noPreview'))
                return
            # Inline CSS for external browser preview (self-contained)
            full_html, _ = self._render_full_html(html_body, inline_css=True, tr=self._)
            # Prefer placing temp HTML inside the per-session folder to ensure cleanup on exit
            try:
                dest_dir = self.session_temp_dir if self.session_temp_dir and Path(self.session_temp_dir).exists() else None
            except Exception:
                dest_dir = None
            temp_path: str
            if dest_dir is not None:
                try:
                    fname = f"preview_{uuid.uuid4().hex}.html"
                    fpath = Path(dest_dir) / fname
                    fpath.write_text(full_html, encoding='utf-8')
                    temp_path = str(fpath)
                except Exception:
                    # Fallback to system temp and track for manual cleanup on exit
                    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html', encoding='utf-8') as tf:
                        tf.write(full_html)
                        temp_path = tf.name
                    try:
                        self._loose_temp_files.append(Path(temp_path))
                    except Exception:
                        pass
            else:
                # No session dir available; use system temp and track
                with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html', encoding='utf-8') as tf:
                    tf.write(full_html)
                    temp_path = tf.name
                try:
                    self._loose_temp_files.append(Path(temp_path))
                except Exception:
                    pass
            # Open by default browser
            try:
                if sys.platform.startswith('win'):
                    os.startfile(temp_path)  # type: ignore[attr-defined]
                else:
                    webbrowser.open(f'file://{temp_path}')
            except Exception:
                webbrowser.open(f'file://{temp_path}')
        except Exception as e:
            messagebox.showerror(self._('dialog.error.title'), f'Failed to open in browser:\n{e}')

    def on_open_browser(self):
        """Button callback wrapper for opening preview in external browser."""
        try:
            self.open_preview_in_browser()
        except Exception:
            pass

    # (internal) Utilities for i18n key reordering (currently inactive)

    def on_run(self):
        if not self._require_core():
            return
        root = Path(self.var_root.get())
        out_json = Path(self.var_out_json.get())
        out_md = Path(self.var_out_md.get())
        out_html = Path(self.var_out_html.get())
        # Exclusive mode: conflicts_only vs include_reference
        conflicts_only = self.var_mode_conflicts.get()
        include_reference = not conflicts_only
        enable_preview_html = self.var_enable_preview.get()
        enable_json = self.var_enable_json.get()
        enable_md = self.var_enable_md.get()
        localize_output = bool(getattr(self, 'var_localize_output', tk.BooleanVar(value=True)).get())

        if not root.exists():
            messagebox.showwarning(self._('dialog.inputCheck.title'), f"{self._('scan.root')} does not exist:\n{root}")
            return
        preview_only = not (enable_json or enable_md)
        if preview_only:
            log_message('info', self.log, 'No file outputs selected; generating Preview only (no files will be written).')
    # Create parent folders for enabled outputs only (skip entirely if none selected)
        def _ensure_output_dirs():
            if not (enable_preview_html or enable_json or enable_md):
                return
            parents = set()
            if enable_preview_html:
                parents.add(out_html.parent)
            if enable_json:
                parents.add(out_json.parent)
            if enable_md:
                parents.add(out_md.parent)
            for p in parents:
                try:
                    p.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    raise RuntimeError(f'Failed to create output folder: {p} -> {e}')
        try:
            _ensure_output_dirs()
        except Exception as e:
            messagebox.showerror(self._('dialog.error.title'), str(e))
            return

        def work():
            """Background worker thread: run scan, write files, populate previews, and render GUI-only views."""
            try:
                import time as _tprof
                t0_total = _tprof.time()
                t_build = t_html_write = t_md_write = t_json_write = 0.0
                t_preview_json = t_preview_md = t_preview_html = t_preview_text = 0.0
                # Lazy safety: recheck/create parent just before each write in case user deleted it
                def _safe_parent(path: Path):
                    try:
                        path.parent.mkdir(parents=True, exist_ok=True)
                    except Exception:
                        pass
                # UI: indicate running
                def _start_ui():
                    try:
                        self.btn_run.configure(state='disabled')
                        self.btn_open_folder.configure(state='disabled')
                        self.progress.pack(side='right')
                        self.progress.start(10)
                    except Exception:
                        pass
                self.after(0, _start_ui)
                self._log_i18n('[START]', 'log.startScan', path=str(root))
                t0 = _tprof.time()
                # Collect internal phase metrics from core (discover/parse/enrich/group)
                if core is None or not hasattr(core, 'build_report'):
                    raise RuntimeError('core.build_report not available')
                _ret = core.build_report(root, collect_metrics=True)
                if isinstance(_ret, tuple) and len(_ret) == 2:
                    report, core_metrics = _ret
                else:  # fallback safety
                    report, core_metrics = _ret, {}
                t_build = _tprof.time() - t0
                try:
                    if core_metrics:
                        self.log(
                            "[TIMER] core discover={d:.1f}ms parse={p:.1f}ms enrich={e:.1f}ms group={g:.1f}ms total={tot:.1f}ms".format(
                                d=core_metrics.get('discover', 0.0),
                                p=core_metrics.get('parse', 0.0),
                                e=core_metrics.get('enrich', 0.0),
                                g=core_metrics.get('group', 0.0),
                                tot=core_metrics.get('total', t_build * 1000.0)
                            )
                        )
                    self.log(f"[TIMER] build_report wrapper {t_build*1000:.1f}ms (includes core.total)")
                except Exception:
                    pass
                # Propagate include_wrap flag to report options for shared writers
                try:
                    opts = dict(report.get('_options') or {})
                    opts['include_wrap_coexistence'] = bool(self.var_include_wrap.get())
                    report['_options'] = opts
                except Exception:
                    pass
                # Cache last full report for re-rendering/filters
                self._last_report = report
                # Write files (order: HTML -> MD -> JSON)
                if conflicts_only:
                    trimmed = {
                        'scanned_root': report['scanned_root'],
                        'files_scanned': report['files_scanned'],
                        'annotation_counts': report['annotation_counts'],
                        'conflicts': report['conflicts'],
                    }
                    try:
                        trimmed['_options'] = dict(report.get('_options') or {})
                    except Exception:
                        pass
                # HTML first
                try:
                    if enable_preview_html:
                        t0w = _tprof.time()
                        _safe_parent(out_html)
                        src_report = report
                        tr = self._ if localize_output else self._make_gettext_for('en')
                        html_body = self.build_html_body(src_report, conflicts_only=conflicts_only, include_reference=include_reference, tr=tr)
                        full_html, used_tpl = self._wrap_full_html_for_file(html_body)
                        out_html.write_text(full_html, encoding='utf-8')
                        if used_tpl:
                            self._maybe_copy_report_css(out_html)
                        t_html_write += (_tprof.time() - t0w)
                        # HTML write done (no dedicated i18n key)
                except Exception as e:
                    self._log_i18n('[WARN]', 'log.warnRenderHtml', err=str(e))
                # Markdown second
                if not preview_only and enable_md:
                    try:
                        t0w = _tprof.time()
                        _safe_parent(out_md)
                        if localize_output:
                            with self._timed('markdown_build'):
                                md_text = self._build_localized_markdown(report, conflicts_only=conflicts_only, include_reference=include_reference)
                            out_md.write_text(md_text, encoding='utf-8')
                        else:
                            if core and hasattr(core, 'write_markdown'):
                                core.write_markdown(report, out_md, conflicts_only=conflicts_only, include_reference=include_reference)  # type: ignore[attr-defined]
                        t_md_write += (_tprof.time() - t0w)
                        self._log_i18n('[DONE]', 'log.doneMd', path=str(out_md))
                    except Exception as e:
                        self._log_i18n('[WARN]', 'log.warnBuildMdPreview', err=str(e))
                # JSON last
                if not preview_only and enable_json:
                    try:
                        t0w = _tprof.time()
                        _safe_parent(out_json)
                        if conflicts_only:
                            data = dict(trimmed)
                        else:
                            data = dict(report)
                            if not bool(self.var_include_wrap.get()):
                                data.pop('wrap_coexistence', None)
                                data.pop('replace_wrap_coexistence', None)
                        if localize_output:
                            data = self._augment_json_with_localized(data)
                        out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                        t_json_write += (_tprof.time() - t0w)
                        self._log_i18n('[DONE]', 'log.doneJson', path=str(out_json))
                    except Exception as e:
                        self._log_i18n('[WARN]', 'log.warnBuildJsonPreview', err=str(e))
                if preview_only:
                    self._log_i18n('[DONE]', 'log.previewOnly')

                # Always render localized Markdown/JSON into the GUI tabs (independent of file outputs)
                try:
                    # JSON preview (trim if conflicts_only)
                    t0p = _tprof.time()
                    if conflicts_only:
                        data = {
                            'scanned_root': report['scanned_root'],
                            'files_scanned': report['files_scanned'],
                            'annotation_counts': report['annotation_counts'],
                            'conflicts': report['conflicts'],
                        }
                        try:
                            data['_options'] = dict(report.get('_options') or {})
                        except Exception:
                            pass
                    else:
                        # Copy to avoid mutating original when pruning wrap sections
                        data = dict(report)
                        # Respect include_wrap for JSON preview (prune sections when off)
                        try:
                            if not bool(self.var_include_wrap.get()):
                                data.pop('wrap_coexistence', None)
                                data.pop('replace_wrap_coexistence', None)
                            # Ensure options are present
                            opts = dict(data.get('_options') or {})
                            opts['include_wrap_coexistence'] = bool(self.var_include_wrap.get())
                            data['_options'] = opts
                        except Exception:
                            pass
                    data_disp = self._augment_json_with_localized(data)
                    self.set_preview_json(json.dumps(data_disp, ensure_ascii=False, indent=2))
                    t_preview_json += (_tprof.time() - t0p)
                except Exception as e:
                    self._log_i18n('[WARN]', 'log.warnBuildJsonPreview', err=str(e))
                try:
                    # Markdown preview (localized)
                    t0p = _tprof.time()
                    with self._timed('markdown_build'):
                        md_text = self._build_localized_markdown(report, conflicts_only=conflicts_only, include_reference=include_reference)
                    self.set_preview_md(md_text)
                    t_preview_md += (_tprof.time() - t0p)
                except Exception as e:
                    self._log_i18n('[WARN]', 'log.warnBuildMdPreview', err=str(e))

                # Build HTML body (GUI-only) and render (apply filters for Preview only)
                try:
                    t0p = _tprof.time()
                    filtered = self._filter_report_for_preview(report, conflicts_only=conflicts_only)
                    html_body = self.build_html_body(filtered, conflicts_only=conflicts_only, include_reference=include_reference)
                    self._last_html_body = html_body
                    try:
                        self._last_filtered_conflicts_count = len(filtered.get('conflicts', []) or [])
                    except Exception:
                        self._last_filtered_conflicts_count = 0
                    if self.webview2 is not None:
                        self.set_preview_html_from_body(html_body)
                    t_preview_html += (_tprof.time() - t0p)
                except Exception as e:
                    self._log_i18n('[WARN]', 'log.warnRenderHtml', err=str(e))

                # Styled Text fallback (no external deps)
                try:
                    # Reuse previously filtered result
                    t0p = _tprof.time()
                    if 'filtered' not in locals():  # safety, should exist
                        filtered = self._filter_report_for_preview(report, conflicts_only=conflicts_only)
                    self._last_render_args = (filtered, conflicts_only, include_reference)
                    if self.webview2 is None and self.txt_html is not None:
                        self.render_report_to_text(filtered, conflicts_only=conflicts_only, include_reference=include_reference)
                    try:
                        if not hasattr(self, '_last_filtered_conflicts_count'):
                            self._last_filtered_conflicts_count = len(filtered.get('conflicts', []) or [])
                    except Exception:
                        pass
                    t_preview_text += (_tprof.time() - t0p)
                except Exception as e:
                    self._log_i18n('[WARN]', 'log.warnRenderText', err=str(e))

                # Auto-switch to an available preview tab
                def _post_success():
                    try:
                        self.nb.select(0)
                    except Exception:
                        pass
                    try:
                        self._update_status_bar()
                    except Exception:
                        pass
                    # Timing summary (only after successful finish)
                    try:
                        t_total = _tprof.time() - t0_total
                        self.log(
                            f"[TIMER] summary build={t_build*1000:.1f}ms htmlW={t_html_write*1000:.1f}ms mdW={t_md_write*1000:.1f}ms jsonW={t_json_write*1000:.1f}ms prevJson={t_preview_json*1000:.1f}ms prevMd={t_preview_md*1000:.1f}ms prevHtml={t_preview_html*1000:.1f}ms prevText={t_preview_text*1000:.1f}ms total={t_total*1000:.1f}ms")
                    except Exception:
                        pass
                    # Show browser open button after first successful run
                    try:
                        if hasattr(self, 'btn_open_browser') and self.btn_open_browser and not self.btn_open_browser.winfo_ismapped():
                            # Show second, right after the Run button
                            self.btn_open_browser.pack(side='left', padx=(0, 6))
                    except Exception:
                        pass
                    # Show 'Open folder' button only when any output file was requested and written
                    try:
                        any_output = bool(enable_preview_html or enable_json or enable_md)
                        if any_output and hasattr(self, 'btn_open_folder') and self.btn_open_folder and not self.btn_open_folder.winfo_ismapped():
                            # Show third, after the browser button
                            self.btn_open_folder.pack(side='left', padx=(0, 6))
                    except Exception:
                        pass
                    # Toast instead of blocking messagebox
                    try:
                        # Simple localized toast using report.header if available
                        self._toast(self._('report.header') + ' - done')
                    except Exception:
                        self._toast(self._('toast.done'))
                    try:
                        if self.var_auto_open.get() and not preview_only and (enable_json or enable_md):
                            self.on_open_folder()
                    except Exception:
                        pass
                self.after(0, _post_success)
            except Exception as e:
                def _post_error():
                    messagebox.showerror(self._('dialog.error.title'), f'Failed to run:\n{e}')
                    log_message('error', self.log, f'{e}')
                self.after(0, _post_error)
            finally:
                # UI: restore when done
                def _stop_ui():
                    try:
                        self.progress.stop()
                        self.progress.pack_forget()
                        self.btn_run.configure(state='normal')
                        # Enable the button now; actual visibility is controlled on success via pack
                        try:
                            self.btn_open_folder.configure(state='normal')
                        except Exception:
                            pass
                    except Exception:
                        pass
                self.after(0, _stop_ui)
        threading.Thread(target=work, daemon=True).start()

    def _on_include_wrap_toggle(self):
        """Handle include-wrap toggle: rerender preview and refresh Markdown/JSON tabs and outwin status."""
        try:
            self._rerender_preview()
        except Exception:
            pass
        try:
            lr = getattr(self, '_last_report', None)
            if lr:
                conflicts_only = self.var_mode_conflicts.get()
                include_reference = not conflicts_only
                # JSON tab
                try:
                    if conflicts_only:
                        data = {}
                        try:
                            data['scanned_root'] = lr.get('scanned_root')  # type: ignore[index]
                            data['files_scanned'] = lr.get('files_scanned')  # type: ignore[index]
                            data['annotation_counts'] = lr.get('annotation_counts')  # type: ignore[index]
                            data['conflicts'] = lr.get('conflicts')  # type: ignore[index]
                        except Exception:
                            pass
                        try:
                            opts_src = getattr(lr, 'get', lambda *_: None)('_options')  # type: ignore[call-arg]
                            if isinstance(opts_src, dict):
                                data['_options'] = dict(opts_src)  # type: ignore[index]
                        except Exception:
                            pass
                    else:
                        try:
                            data = dict(lr)  # type: ignore[arg-type]
                        except Exception:
                            data = {}
                        try:
                            if not bool(self.var_include_wrap.get()):
                                data.pop('wrap_coexistence', None)  # type: ignore[call-arg]
                                data.pop('replace_wrap_coexistence', None)  # type: ignore[call-arg]
                        except Exception:
                            pass
                        try:
                            opts2 = data.get('_options') if isinstance(data, dict) else None  # type: ignore[index]
                            if not isinstance(opts2, dict):
                                opts2 = {}
                            opts2['include_wrap_coexistence'] = bool(self.var_include_wrap.get())  # type: ignore[index]
                            data['_options'] = opts2  # type: ignore[index]
                        except Exception:
                            pass
                    data_disp = self._augment_json_with_localized(data)
                    self.set_preview_json(json.dumps(data_disp, ensure_ascii=False, indent=2))
                except Exception:
                    pass
                # MD tab
                try:
                    md_text = self._build_localized_markdown(lr, conflicts_only=conflicts_only, include_reference=include_reference)
                    self.set_preview_md(md_text)
                except Exception:
                    pass
        except Exception:
            pass
    # Status footer update logic inactive

    # --- WebView2 safe loaders -------------------------------------------------
    def _webview2_can_load(self) -> bool:
        """Return True if the embedded engine seems ready to accept a load call.

        Some tkwebview2 backends expose internal attributes lazily (e.g., EdgeChrome.web_view).
        We conservatively check common attributes before calling load APIs.
        """
        try:
            wv = getattr(self, 'webview2', None)
            if wv is None:
                return False
            # Heuristic readiness: widget is mapped and has a width/height > 0
            try:
                if wv.winfo_ismapped() and wv.winfo_width() >= 1 and wv.winfo_height() >= 1:
                    return True
            except Exception:
                pass
            # Fall back to attribute probes used by certain implementations
            if hasattr(wv, 'web_view') or hasattr(wv, 'browser') or hasattr(wv, '_webview'):
                return True
            return False
        except Exception:
            return False

    def _webview2_try_load_blank(self, attempt: int = 1, max_attempts: int = 1):
        """Attempt to navigate to blank safely (safe_call wrapper)."""
        if not (HAS_WEBVIEW2 and getattr(self, 'webview2', None) is not None):
            return
        if not self._webview2_can_load():
            log_message('warn', self.log, 'WebView2 blank load skipped (engine not ready, single-attempt mode)')
            return
        safe_call(self._webview2_dispatch_load, None, blank=True)

    def _webview2_try_load_html(self, html: str, attempt: int = 1, max_attempts: int = 1):
        """Safely load provided full HTML (safe_call)."""
        if not (HAS_WEBVIEW2 and getattr(self, 'webview2', None) is not None):
            return
        if not self._webview2_can_load():
            log_message('warn', self.log, 'WebView2 HTML load skipped (engine not ready, single-attempt mode)')
            return
        safe_call(self._webview2_dispatch_load, html, blank=False)

    def _webview2_dispatch_load(self, html: Optional[str], blank: bool):
        """Internal unified dispatcher for WebView2 loading strategies.

        Tries (in order): load_html / load_html_string / navigate(data URL or about:blank).
        """
        try:
            wv = getattr(self, 'webview2', None)
            if wv is None:
                return
            try:
                if blank:
                    if hasattr(wv, 'load_html'):
                        wv.load_html("")  # type: ignore[attr-defined]
                        return
                    if hasattr(wv, 'load_html_string'):
                        wv.load_html_string("")  # type: ignore[attr-defined]
                        return
                    if hasattr(wv, 'navigate'):
                        wv.navigate('about:blank')  # type: ignore[attr-defined]
                        return
                else:
                    if html is None:
                        return
                    if hasattr(wv, 'load_html'):
                        wv.load_html(html)  # type: ignore[attr-defined]
                        return
                    if hasattr(wv, 'load_html_string'):
                        wv.load_html_string(html)  # type: ignore[attr-defined]
                        return
                    if hasattr(wv, 'navigate'):
                        import base64
                        data_url = 'data:text/html;base64,' + base64.b64encode(html.encode('utf-8')).decode('ascii')
                        wv.navigate(data_url)  # type: ignore[attr-defined]
                        return
            except Exception as e:
                kind = 'blank' if blank else 'HTML'
                log_message('warn', self.log, f"WebView2 {kind} load failed: {e.__class__.__name__}: {e}")
        except Exception:
            pass

    def set_preview_md(self, content: str):  # pragma: no cover - GUI
        """Push text into the Markdown tab (read-only-ish) with None guard."""
        self._safe_set_text('txt_md', content)

    def set_preview_json(self, content: str):  # pragma: no cover - GUI
        """Push text into the JSON tab (read-only-ish) with None guard."""
        self._safe_set_text('txt_json', content)

    # --- HTML preview helpers (GUI-only) ---
    def set_preview_html_from_body(self, body_html: str):
        """Wrap body HTML with external template (inline CSS for preview) and load it."""
        full_html, _ = self._render_full_html(body_html, inline_css=True, tr=self._)
        self._last_full_html = full_html
        def _update():
            try:
                if HAS_WEBVIEW2 and self.webview2 is not None:
                    self._webview2_try_load_html(full_html)
                elif self.txt_html is not None and self._last_render_args:
                    rep, c_only, inc_ref = self._last_render_args
                    self.render_report_to_text(rep, conflicts_only=c_only, include_reference=inc_ref)
            except Exception:
                pass
        self.after(0, _update)

    # Restored high-level renderer (not currently called directly but kept for parity)
    def render_report_to_html(self, report: dict, conflicts_only: bool, include_reference: bool):  # pragma: no cover - GUI
        """Build body then delegate to set_preview_html_from_body (legacy API)."""
        try:
            body_html = self.build_html_body(report, conflicts_only=conflicts_only, include_reference=include_reference)
            self._last_html_body = body_html
            self.set_preview_html_from_body(body_html)
        except Exception:
            pass

    def _wrap_full_html_for_file(self, body_html: str) -> tuple[str, bool]:
        """Return (html, used_external_template) for file export.

        When an external template is used we DO NOT inline CSS so that the
        companion report.css can be copied next to the output file for reuse.
        Callers should, when the bool is True, invoke _maybe_copy_report_css().
        """
        return self._render_full_html(body_html, inline_css=False, tr=self._)

    def _maybe_copy_report_css(self, destination_html: Path, overwrite: bool = False):
        """Delegate CSS copy to common_assets.ensure_css_copy.

        We locate the first asset dir containing report.css (same order as discovery)
        and copy it next to destination if needed.
        """
        def _copy():
            chosen: Optional[Path] = None
            for d in discover_asset_dirs():
                if (d / 'report.css').exists():
                    chosen = d
                    break
            if chosen:
                _ca_ensure_css_copy(destination_html, chosen, overwrite=overwrite)
        safe_call(_copy)

    # Copy handlers omitted

    def build_html_body(self, report: dict, conflicts_only: bool, include_reference: bool, tr=None) -> str:
        from builders.report_builders import build_html_body_gui  # type: ignore
        from typing import Callable, cast
        # Determine include_wrap from GUI state
        try:
            include_wrap = bool(self.var_include_wrap.get())
        except Exception:
            include_wrap = False
        # Determine disable_file_links from report options
        try:
            disable_file_links = bool((report.get('_options') or {}).get('disable_file_links', False))
        except Exception:
            disable_file_links = False
        # Prepare legend lines (GUI bundles) injected so common builder can use them
        try:
            cur_lang = self.var_lang.get() if hasattr(self, 'var_lang') else 'en'
            bundle = (self._bundles.get(cur_lang) or {})
            if isinstance(bundle.get('legend.lines'), list):
                report = dict(report)
                report['_localized_legend_lines'] = bundle.get('legend.lines')
        except Exception:
            pass
        # Ensure translator has (str)->str signature for type checkers
        raw_tr = tr if callable(tr) else self._
        tr_fn = cast(Callable[[str], str], raw_tr)
        # Delegate; pass GUI impact & anchor helpers
        return build_html_body_gui(
            report,
            tr_fn,
            conflicts_only=conflicts_only,
            include_reference=include_reference,
            include_wrap=include_wrap,
            disable_file_links=disable_file_links,
            impact_fn=lambda cls, meth, mods, entries: self._assess_conflict_impact(cls, meth, mods, entries),
            anchor_fn=lambda idx, cls, meth: self._anchor_id_for_conflict(idx, cls, meth),
        )

    # --- Helper: anchor id for conflicts ---
    def _anchor_id_for_conflict(self, idx: Optional[int], cls: str, meth: str) -> str:
        base = (cls + '-' + meth).lower().replace(' ', '-')
        base = ''.join(ch for ch in base if ch.isalnum() or ch in ('-', '_', '.'))
        if idx is not None:
            return f"conf-{idx}-{base}"
        return f"conf-{base}"

    # --- Styled Text fallback rendering (no external deps) ---
    def _init_fonts(self):
        """Initialize fonts for the styled Text fallback renderer."""
        try:
            # Prefer Segoe UI on Windows to match HTML preview; fallback to TkDefaultFont size
            try:
                default_size = tkfont.nametofont('TkDefaultFont').cget('size')
            except Exception:
                default_size = 10
            family = getattr(self, 'var_font_family', tk.StringVar(value='Segoe UI')).get() or 'Segoe UI'
            # Base font (Segoe UI)
            self.font_base = tkfont.Font(family=family, size=default_size)
            self.font_bold = tkfont.Font(family=family, size=default_size, weight='bold')
            self.font_h1 = tkfont.Font(family=family, size=max(default_size+4, 12), weight='bold')
            self.font_h2 = tkfont.Font(family=family, size=max(default_size+2, 11), weight='bold')
            # Unify mono as well to Segoe UI for consistency with HTML (which inherits body font)
            self.font_mono = tkfont.Font(family=family, size=default_size)
            # Meta/Impact fonts (slightly smaller / base-equivalent)
            self.font_meta = tkfont.Font(family=family, size=max(default_size-1, 8))
            self.font_impact = tkfont.Font(family=family, size=default_size)
        except Exception:
            # Reasonable fallbacks
            self.font_base = tkfont.Font(size=10)
            self.font_bold = tkfont.Font(size=10, weight='bold')
            self.font_h1 = tkfont.Font(size=14, weight='bold')
            self.font_h2 = tkfont.Font(size=12, weight='bold')
            self.font_mono = tkfont.Font(size=10)
            self.font_meta = tkfont.Font(size=9)
            self.font_impact = tkfont.Font(size=10)
        # Apply base font to the HTML Text widget so untagged text also uses Segoe UI
        try:
            if hasattr(self, 'txt_html') and self.txt_html is not None:
                self.txt_html.configure(font=self.font_base)
        except Exception:
            pass

    # Font stack / family helpers ------------------------------------------------
    def _current_css_font_stack(self) -> str:
        try:
            fam = (self.var_font_family.get() or '').strip()
        except Exception:
            fam = ''
        if not fam:
            fam = 'Segoe UI'
        if any(ch in fam for ch in (' ', '-')):
            fam_css = f'"{fam}"'
        else:
            fam_css = fam
        return f"{fam_css},Segoe UI,Arial,sans-serif"

    def apply_font_family_flow(self, explicit_family: Optional[str] = None):  # pragma: no cover - GUI
        """Unified font family apply flow.

        Handles:
          - Determining target family (explicit or var)
          - MRU list maintenance & submenu refresh
          - Updating all custom Font objects & Tk named defaults
          - Propagating family to Text widgets (HTML + Markdown/JSON/Log)
          - Re-render + status bar update
        """
        try:
            fam = (explicit_family or (self.var_font_family.get() if hasattr(self, 'var_font_family') else '') or 'Segoe UI').strip()
            # MRU maintenance
            try:
                prev = getattr(self, '_last_font_family', None)
                mru = list(getattr(self, '_font_mru', []))
                if fam in mru:
                    mru.remove(fam)
                mru.insert(0, fam)
                if prev and prev != fam and prev not in mru:
                    mru.append(prev)
                self._font_mru = mru[:5]
                try: self._refresh_font_family_submenu()
                except Exception: pass
                self._last_font_family = fam
            except Exception:
                pass
            # Update custom font objects
            fonts = [getattr(self, n, None) for n in ('font_base','font_bold','font_h1','font_h2','font_mono','font_meta','font_impact')]
            for f in fonts:
                if f is not None:
                    try:
                        f.configure(family=fam)
                    except Exception:
                        pass
            # Named defaults
            try:
                for tkname in ("TkDefaultFont","TkHeadingFont","TkTextFont","TkFixedFont","TkMenuFont","TkTooltipFont"):
                    try:
                        nf = tkfont.nametofont(tkname)
                        nf.configure(family=fam)
                    except Exception:
                        pass
            except Exception:
                pass
            # Apply to existing Text widgets (HTML + others)
            try:
                if hasattr(self, 'txt_html') and self.txt_html is not None:
                    self.txt_html.configure(font=self.font_base)
            except Exception:
                pass
            try:
                self._refresh_text_widget_font_family()
            except Exception:
                pass
            # Trigger re-render + status bar update
            try: self._rerender_preview()
            except Exception: pass
            try: self._update_status_bar()
            except Exception: pass
        except Exception:
            pass

    # Backward compatibility wrapper
    def apply_font_family(self):  # pragma: no cover - GUI
        self.apply_font_family_flow()

    def _refresh_font_family_submenu(self):
        """Rebuild font family submenu after MRU update."""
        try:
            m = getattr(self, '_menu_font_family_submenu', None)
            if not m:
                return
            # Remove existing items.
            try:
                m.delete(0, 'end')
            except Exception:
                pass
            # Rebuild MRU entries.
            try:
                recent = getattr(self, '_font_mru', [])
            except Exception:
                recent = []
            # Current font display row.
            try:
                cur_fam = (self.var_font_family.get() or 'Segoe UI').strip()
                cur_label_key = self._('fontChooser.current')
                cur_label = cur_label_key
                m.add_command(label=f'{cur_label} {cur_fam}', state='disabled')
                m.add_separator()
            except Exception:
                pass
            # MRU excluding current font.
            recent_filtered = [r for r in recent if r != (self.var_font_family.get() or '').strip()]
            if recent_filtered:
                try:
                    # Localized recent section header
                    recent_label = self._('menu.display.fontRecent')
                    m.add_command(label=f'— {recent_label} —', state='disabled')
                except Exception:
                    pass
                for rf in recent_filtered:
                    try:
                        m.add_radiobutton(
                            label=rf,
                            value=rf,
                            variable=self.var_font_family,
                            command=lambda v=rf: (self.var_font_family.set(v), self.apply_font_family())
                        )
                    except Exception:
                        pass
                try:
                    m.add_separator()
                except Exception:
                    pass
            # "More..." entry opens chooser.
            try:
                more_label = self._('menu.display.fontMore')
                m.add_command(label=more_label, command=self.open_font_chooser)
            except Exception:
                pass
        except Exception:
            pass

    # --- Font chooser dialog -------------------------------------------------------
    def open_font_chooser(self):
        """Enhanced font selection dialog with search + category grouping.

        Keeps existing simple menu for quick picks; this dialog helps when font count is large.
        """
        try:
            import tkinter.font as tkfont
            if getattr(self, '_font_chooser_win', None) and self._font_chooser_win.winfo_exists():
                try:
                    self._font_chooser_win.lift()
                    self._font_chooser_win.focus_set()
                except Exception: pass
                return
            win = tk.Toplevel(self)
            self._font_chooser_win = win
            win.title(self._('fontChooser.title'))
            try: win.transient(self)
            except Exception: pass
            try: win.grab_set()
            except Exception: pass
            # Center relative to parent only on first show.
            try: self._center_on_map_once(win)
            except Exception: pass
            frm = ttk.Frame(win)
            frm.pack(fill='both', expand=True, padx=8, pady=8)

            # Gather & normalize fonts (reuse same logic as menu: remove '@', dedupe)
            try:
                raw = list(tkfont.families())
            except Exception:
                raw = []
            norm_seen = set(); fonts = []
            for r in raw:
                base = r[1:] if r.startswith('@') else r
                if not base or base in norm_seen: continue
                norm_seen.add(base); fonts.append(base)
            fonts.sort(key=str.lower)

            # Categorize
            def categorize(name: str) -> str:
                n = name.lower()
                # very lightweight heuristics
                if any(k in n for k in ('mono','console','terminal','courier','coder','code','fixed')):
                    return 'mono'
                if any(k in n for k in ('gothic','ui','segoe','arial','helvetica','sans','verdana','roboto','noto','meiryo','yu ')):
                    return 'sans'
                if any(k in n for k in ('serif','times','georgia','garamond','roman')):
                    return 'serif'
                if any(k in n for k in ('meiryo','gothic','yu ','noto sans cjk','ms pgothic','ms gothic','hiragino','ud ')):
                    return 'cjk'
                return 'other'
            cat_map = {f: categorize(f) for f in fonts}

            # UI controls
            topbar = ttk.Frame(frm); topbar.pack(fill='x', pady=(0,6))
            lbl_search = ttk.Label(topbar, text=self._('fontChooser.search')); lbl_search.pack(side='left')
            var_search = tk.StringVar()
            ent_search = ttk.Entry(topbar, textvariable=var_search, width=24); ent_search.pack(side='left', padx=(4,12))
            lbl_cat = ttk.Label(topbar, text=self._('fontChooser.category')); lbl_cat.pack(side='left')
            var_cat = tk.StringVar(value='all')
            cat_values = [
                ('all', self._('fontChooser.categories.all')),
                ('sans', self._('fontChooser.categories.sans')),
                ('serif', self._('fontChooser.categories.serif')),
                ('mono', self._('fontChooser.categories.mono')),
                ('cjk', self._('fontChooser.categories.cjk')),
                ('other', self._('fontChooser.categories.other')),
            ]
            opt_cat = ttk.Combobox(topbar, state='readonly', width=10, values=[c[1] for c in cat_values])
            opt_cat.current(0)
            opt_cat.pack(side='left', padx=(4,0))

            # Mapping displayed name -> internal key for category selection
            displayed_to_key = {c[1]: c[0] for c in cat_values}
            def on_cat_change(event=None):
                key = displayed_to_key.get(opt_cat.get(), 'all')
                var_cat.set(key)
                refresh()
            opt_cat.bind('<<ComboboxSelected>>', on_cat_change)

            # Listbox of fonts
            list_frame = ttk.Frame(frm); list_frame.pack(fill='both', expand=True)
            lb = tk.Listbox(list_frame, activestyle='dotbox')
            lb.pack(side='left', fill='both', expand=True)
            sb = ttk.Scrollbar(list_frame, orient='vertical', command=lb.yview)
            sb.pack(side='right', fill='y')
            lb.configure(yscrollcommand=sb.set)

            # Preview area
            sample_frame = ttk.Frame(frm); sample_frame.pack(fill='x', pady=(6,4))
            # Fallback sample string kept ASCII-only to comply with English-only comment/content policy
            sample_label = ttk.Label(sample_frame, text=self._('fontChooser.previewSample'))
            sample_label.pack(fill='x')

            # Buttons
            btn_frame = ttk.Frame(frm); btn_frame.pack(fill='x', pady=(8,0))
            # Left area: current font display.
            cur_wrap = ttk.Frame(btn_frame)
            cur_wrap.pack(side='left', fill='x', expand=True)
            lbl_cur_caption = ttk.Label(cur_wrap, text=self._('fontChooser.current'))
            lbl_cur_caption.pack(side='left')
            var_cur_font_status = tk.StringVar(value=self.var_font_family.get())
            lbl_cur_value = ttk.Label(cur_wrap, textvariable=var_cur_font_status)
            lbl_cur_value.pack(side='left', padx=(4,0))

            def _apply_selected(close_after=False):
                try:
                    sel = lb.curselection()
                    if not sel:
                        return
                    picked = lb.get(sel[0])
                    self.var_font_family.set(picked)
                    self.apply_font_family()
                    var_cur_font_status.set(picked)
                    if close_after:
                        try:
                            win.destroy()
                        except Exception:
                            pass
                except Exception:
                    pass

            # Right side: Apply only.
            btn_apply = ttk.Button(btn_frame, text=self._('fontChooser.ok'), command=lambda: _apply_selected(True))
            btn_apply.pack(side='right')

            # Filtering logic
            def refresh(event=None):
                term = var_search.get().strip().lower()
                cat = var_cat.get()
                lb.delete(0, 'end')
                for fnt in fonts:
                    if term and term not in fnt.lower():
                        continue
                    if cat != 'all' and cat_map.get(fnt) != cat:
                        continue
                    lb.insert('end', fnt)
                # try to select current
                cur = (self.var_font_family.get() or '').strip()
                if cur:
                    try:
                        idxs = lb.get(0,'end')
                        if cur in idxs:
                            lb.selection_set(idxs.index(cur))
                            lb.see(idxs.index(cur))
                    except Exception: pass
                upd_preview_font()

            def upd_preview_font(event=None):
                try:
                    sel = lb.curselection()
                    fam = lb.get(sel[0]) if sel else (self.var_font_family.get() or 'Segoe UI')
                    fprev = tkfont.Font(family=fam, size=12)
                    sample_label.configure(font=fprev)
                except Exception:
                    pass

            lb.bind('<<ListboxSelect>>', upd_preview_font)
            # Double-click: apply only (do not close).
            lb.bind('<Double-Button-1>', lambda e: (_apply_selected(False), win.focus_set()))
            var_search.trace_add('write', lambda *_: refresh())
            refresh()

            # --- Theming (Dark/Light) -------------------------------------------------
            # Follow root dark mode variable; apply styles without altering global ttk theme.
            def _apply_theme():
                try:
                    dark = bool(getattr(self, 'var_dark_mode', tk.BooleanVar(value=False)).get())
                    style = ttk.Style(win)
                    if dark:
                        bg   = '#1e1f22'
                        bg2  = '#26282b'  # list / preview background
                        fg   = '#d8d8d8'
                        sel_bg = '#3d6fa5'
                        sel_fg = '#ffffff'
                        entry_bg = '#2a2c30'
                        border = '#3a3d41'
                    else:
                        bg   = '#f2f2f2'
                        bg2  = '#ffffff'
                        fg   = '#202020'
                        sel_bg = '#0a64c2'
                        sel_fg = '#ffffff'
                        entry_bg = '#ffffff'
                        border = '#c5c5c5'
                    # Toplevel background
                    try: win.configure(bg=bg)
                    except Exception: pass
                    # Styles for frames/labels/entry/buttons
                    try:
                        style.configure('FontChooser.TFrame', background=bg)
                        style.configure('FontChooser.Section.TFrame', background=bg2)
                        style.configure('FontChooser.TLabel', background=bg, foreground=fg)
                        style.configure('FontChooser.Section.TLabel', background=bg2, foreground=fg)
                        style.configure('FontChooser.TButton')  # Let OS theme buttons
                        style.configure('FontChooser.TEntry', fieldbackground=entry_bg, foreground=fg, bordercolor=border)
                        style.map('FontChooser.TEntry', foreground=[('disabled', fg), ('!disabled', fg)])
                    except Exception:
                        pass
                    # Apply frame/label styles
                    for f_ in (frm, topbar, list_frame, sample_frame, btn_frame, cur_wrap):
                        try: f_.configure(style='FontChooser.TFrame')
                        except Exception: pass
                    for lbl_ in (lbl_search, lbl_cat, sample_label, lbl_cur_caption, lbl_cur_value):
                        try: lbl_.configure(style='FontChooser.TLabel')
                        except Exception: pass
                    try: ent_search.configure(style='FontChooser.TEntry')
                    except Exception: pass
                    # Listbox / sample area colors
                    try:
                        lb.configure(bg=bg2, fg=fg, selectbackground=sel_bg, selectforeground=sel_fg, highlightthickness=1, highlightbackground=border, relief='flat')
                    except Exception: pass
                    try:
                        sample_frame.configure(style='FontChooser.Section.TFrame')
                        sample_label.configure(style='FontChooser.Section.TLabel')
                    except Exception: pass
                except Exception:
                    pass

            _apply_theme()
            # Reapply theme when dark mode toggles (trace cleared on window close)
            trace_id = None
            try:
                if hasattr(self, 'var_dark_mode'):
                    trace_id = self.var_dark_mode.trace_add('write', lambda *_: _apply_theme())
            except Exception:
                trace_id = None

            def _on_close():
                try:
                    if trace_id and hasattr(self, 'var_dark_mode'):
                        self.var_dark_mode.trace_remove('write', trace_id)
                except Exception:
                    pass
                try:
                    win.destroy()
                except Exception:
                    pass

            win.protocol('WM_DELETE_WINDOW', _on_close)
        except Exception:
            pass

    # Recursive per-widget font application avoided to prevent size drift across sessions.

    def _setup_text_tags(self):
        """Define tags for Text renderer (headings, badges, severity colors)."""
        if self.txt_html is None:
            return
        t = self.txt_html
        t.tag_configure('h1', font=self.font_h1, spacing1=6, spacing3=6)
        t.tag_configure('h2', font=self.font_h2, spacing1=4, spacing3=4)
        t.tag_configure('b', font=self.font_bold)
        t.tag_configure('mono', font=self.font_mono)
        t.tag_configure('meta', font=self.font_meta)
        t.tag_configure('impact', font=self.font_impact)
        # Colors adjust by theme via apply_text_widget_theme; we keep simple tags here
        t.tag_configure('badge', relief='ridge', borderwidth=1, spacing1=1, spacing3=1)
        t.tag_configure('conflict', lmargin1=6, lmargin2=6, spacing1=3, spacing3=4)
        # Severity color tags
        t.tag_configure('sev_critical', foreground='#ff3b3b')
        t.tag_configure('sev_high', foreground='#ff6f6f')
        t.tag_configure('sev_medium', foreground='#ffb347')
        t.tag_configure('sev_low', foreground='#7ac943')
        # Hyperlink-matching color tag for file paths (updated on theme change)
        try:
            dark = bool(getattr(self, 'var_dark_mode').get()) if hasattr(self, 'var_dark_mode') else False
        except Exception:
            dark = False
        t.tag_configure('filelink', foreground=('#4ea3ff' if dark else '#0066cc'))
        # Always-black line number tag
        t.tag_configure('lineno', foreground='#000000')

    def render_report_to_text(self, report: dict, conflicts_only: bool, include_reference: bool):
        """Render a readable text-only preview with minimal styling tags."""
        if self.txt_html is None:
            return
        t = self.txt_html
        t.configure(state='normal')
        t.delete('1.0', 'end')
        # Ensure the currently rendered report is treated as the active one so that
        # impact assessment logic (_assess_conflict_impact) can see wrap coexistence
        # arrays even when render_report_to_text is invoked directly in tests without
        # going through the normal scan/update pipeline.
        try:
            self._last_report = report  # type: ignore[attr-defined]
        except Exception:
            pass
        self._setup_text_tags()
        # Header
        t.insert('end', self._('report.header') + '\n', ('h1',))
        meta = f"{self._('report.scannedRoot')} {report.get('scanned_root','')} | {self._('report.filesScanned')} {report.get('files_scanned',0)}\n"
        t.insert('end', meta, ('meta',))
        # Annotation counts badges (simple inline)
        ann = report.get('annotation_counts', {}) or {}
        if ann:
            badges = [
                f"replaceMethod: {ann.get('replaceMethod',0)}",
                f"wrapMethod: {ann.get('wrapMethod',0)}",
                f"replaceGlobal: {ann.get('replaceGlobal',0)}",
            ]
            t.insert('end', ' | '.join(badges) + '\n')
        t.insert('end', '\n')

        # Conflicts
        conflicts = report.get('conflicts', []) or []
        t.insert('end', f"{self._('report.conflicts').split('(')[0].strip()} ({self._('summary.total')}: {len(conflicts)})\n", ('h2',))
        if not conflicts:
            t.insert('end', self._('report.noConflicts') + '\n')
        else:
            for c in conflicts:
                header = f"{c.get('class','')}.{c.get('method','')} — {c.get('count',0)} occurrences — MODs: {', '.join(c.get('mods', []))}\n"
                t.insert('end', header, ('b',))
                # Impact (Preview-only heuristic)
                impact = self._assess_conflict_impact(
                    c.get('class',''), c.get('method',''), c.get('mods', []), (c.get('occurrences') or c.get('entries') or [])
                )
                sev_tag = f"sev_{impact['severity'].lower()}"
                sev_key = f"filters.sev.{impact['severity'].lower()}"
                sev_label = self._(sev_key)
                if sev_label == sev_key:
                    sev_label = self._(f'filters.sev.{impact['severity'].lower()}') if self._(f'filters.sev.{impact['severity'].lower()}') != f'filters.sev.{impact['severity'].lower()}' else impact['severity']
                # Impact line uses a dedicated impact font + color tag
                msg = impact.get('message', '') or ''
                try:
                    from common.common_i18n import localize_impact_placeholders as _loc_imp
                    msg = _loc_imp(msg, self._)
                except Exception:
                    pass
                t.insert('end', f"  {self._('impact.label')} [{sev_label}] {msg}\n", ('impact', sev_tag))
                # Baseline (no wrap bonus) line if wrap coexistence present and differs
                try:
                    from common.common_util import method_has_wrap as _mhwrap  # type: ignore
                except Exception:
                    _mhwrap = lambda *_a, **_k: False  # type: ignore
                # Detect wrap coexistence even if original wrapMethod entries are omitted from 'entries'
                has_wrap = False
                try:
                    # Primary: method_has_wrap (original entries based)
                    has_wrap = _mhwrap(report, c.get('class',''), c.get('method',''))
                except Exception:
                    has_wrap = False
                if not has_wrap:
                    try:
                        wc = report.get('wrap_coexistence') or []
                        for g in wc:
                            if g.get('class')==c.get('class','') and g.get('method')==c.get('method',''):
                                has_wrap = True
                                break
                    except Exception:
                        pass
                if has_wrap:
                    try:
                        # Recompute baseline severity without wrap bonus (config identical)
                        from common.common_impact import compute_impact_unified as _ciu  # type: ignore
                        baseline = _ciu(c.get('class',''), c.get('method',''), c.get('mods', []), (c.get('occurrences') or c.get('entries') or []), wrap_coexist=False, config=getattr(self,'_impact_cfg',{}) or {})
                        bsev = (baseline or {}).get('severity','')
                        bmsg = (baseline or {}).get('message','') or ''
                        try:
                            from common.common_i18n import localize_impact_placeholders as _loc_imp2
                            bmsg = _loc_imp2(bmsg, self._)
                        except Exception:
                            pass
                        # Baseline display rule: show only when severity differs (not for message-only differences)
                        if bsev and (bsev != impact.get('severity')):
                            bsev_key = f"filters.sev.{bsev.lower()}"
                            bsev_label = self._(bsev_key)
                            if bsev_label == bsev_key:
                                bsev_label = bsev
                            base_lbl = self._('impact.label.baseline') if self._('impact.label.baseline')!='impact.label.baseline' else 'Baseline'
                            t.insert('end', f"  {base_lbl} [{bsev_label}] {bmsg}\n", ('impact', f'sev_{bsev.lower()}'))
                    except Exception:
                        pass
                # Entries list; support both keys to be safe. Show target method once.
                entries = c.get('occurrences') or c.get('entries') or []
                if entries:
                    sig = entries[0].get('func_sig') or entries[0].get('signature') or ''
                    if sig:
                        t.insert('end', f"  {self._('report.targetMethod')}: {sig}\n", ('mono',))
                for e in entries:
                    mod = e.get('mod','')
                    rel = e.get('relpath', e.get('file',''))
                    ln = e.get('line','')
                    # Indent normal occurrences with four spaces before dash
                    t.insert('end', f"    - [{mod}] ", ('mono',))
                    t.insert('end', rel, ('filelink','mono'))
                    t.insert('end', f":{ln}\n", ('lineno','mono'))
                # Inline wrap occurrences (always show even if global wrap section disabled)
                try:
                    wrap_groups = report.get('wrap_coexistence') or []
                    matched = [g for g in wrap_groups if g.get('class')==c.get('class','') and g.get('method')==c.get('method','')]
                    if matched:
                        occs = matched[0].get('occurrences') or []
                        if occs:
                            heading = self._('conflict.wrapInlineHeading')
                            if heading == 'conflict.wrapInlineHeading':
                                heading = 'Other mods @wrapMethod (coexisting)'
                            t.insert('end', f"  {heading}\n", ('b',))
                            for w in occs:
                                w_mod = w.get('mod','')
                                w_rel = w.get('relpath', w.get('file',''))
                                w_ln = w.get('line','')
                                t.insert('end', f"    - [{w_mod}] ", ('mono',))
                                t.insert('end', w_rel, ('filelink','mono'))
                                t.insert('end', f":{w_ln}\n", ('lineno','mono'))
                except Exception:
                    pass
                t.insert('end', '\n', ('conflict',))

    # wrapMethod coexistence (optional, gated)
        try:
            include_wrap = bool(self.var_include_wrap.get())
        except Exception:
            include_wrap = False
        if include_wrap:
            wrap_co = report.get('wrap_coexistence', []) or []
            if wrap_co:
                h = self._('report.wrapCoexist')
                t.insert('end', h + '\n', ('h2',))
                for c in sorted(wrap_co, key=lambda x: (x.get('class',''), x.get('method',''))):
                    t.insert('end', f"{c.get('class','')}.{c.get('method','')} — wraps: {c.get('wrap_count',0)}\n", ('b',))
                    for occ in c.get('occurrences') or []:
                        mod = occ.get('mod','')
                        rel = occ.get('relpath', occ.get('file',''))
                        ln = occ.get('line','')
                        t.insert('end', f"- [{mod}] ", ('mono',))
                        t.insert('end', rel, ('filelink','mono'))
                        t.insert('end', f":{ln}\n", ('lineno','mono'))
                    t.insert('end', '\n')
            rw_co = report.get('replace_wrap_coexistence', []) or []
            if rw_co:
                h2 = self._('report.replaceWrapCoexist')
                t.insert('end', h2 + '\n', ('h2',))
                for c in sorted(rw_co, key=lambda x: (x.get('class',''), x.get('method',''))):
                    t.insert('end', f"{c.get('class','')}.{c.get('method','')} — replace: {c.get('replace_count',0)}, wrap: {c.get('wrap_count',0)}\n", ('b',))
                t.insert('end', '\n')

        # Reference (optional)
        if not conflicts_only and include_reference:
            t.insert('end', self._('report.reference') + '\n', ('h2',))
            # Match core's annotation value without '@'
            items = [e for e in report.get('entries', []) if e.get('annotation') == 'replaceMethod']
            # Group by class/method
            grouped = {}
            for e in items:
                key = (e.get('class',''), e.get('method',''))
                grouped.setdefault(key, []).append(e)
            for (cls, meth) in sorted(grouped.keys()):
                mods = sorted({e.get('mod','<unknown>') for e in grouped[(cls, meth)]})
                t.insert('end', f"{cls}.{meth} — MODs: {', '.join(mods)}\n", ('b',))
                # Show signature once per method in reference, then list occurrences
                gitems = grouped[(cls, meth)]
                if gitems:
                    sig = gitems[0].get('func_sig') or gitems[0].get('signature') or ''
                    if sig:
                        t.insert('end', f"  {self._('report.targetMethod')}: {sig}\n", ('mono',))
                for e in gitems:
                    mod = e.get('mod','')
                    rel = e.get('relpath', e.get('file',''))
                    ln = e.get('line','')
                    t.insert('end', f"- [{mod}] ", ('mono',))
                    t.insert('end', rel, ('filelink','mono'))
                    t.insert('end', f":{ln}\n", ('lineno','mono'))
                t.insert('end', '\n')

        t.configure(state='normal')

    # --- Impact heuristic (Preview only) ---
    def _assess_conflict_impact(self, cls: str, meth: str, mods: list, entries: list):
        """Unified impact computation (preview path).

        Ensures parity with exported HTML/Markdown by:
        - Using the shared default impact configuration (unless user overrides via settings).
        - Applying wrap bonus only if BOTH (a) user enabled wrap coexistence output AND
          (b) the specific method actually has wrap coexistence (per report arrays).
        """
        from common.common_impact import compute_impact_unified  # lazy import to avoid circular dependencies
        try:
            from common.common_util import method_has_wrap as _mhwrap  # type: ignore
        except Exception:
            _mhwrap = lambda *_a, **_k: False  # type: ignore
        # Preview should still reflect higher (overall) impact even if wrap section hidden.
        # Therefore: treat presence of wrap coexistence as bonus regardless of user toggle.
        has_wrap = False
        try:
            if self._last_report:
                has_wrap = _mhwrap(self._last_report, cls, meth)
                if not has_wrap:
                    # Fallback: consult wrap_coexistence array directly
                    for g in (self._last_report.get('wrap_coexistence') or []):
                        if g.get('class')==cls and g.get('method')==meth:
                            has_wrap = True
                            break
        except Exception:
            has_wrap = False
        impact_cfg = getattr(self, '_impact_cfg', {}) or {}
        return compute_impact_unified(cls, meth, mods, entries, wrap_coexist=has_wrap, config=impact_cfg)

    def _extract_signature_complexity(self, cls: str, meth: str, entries: list):
        """Derive (args_count, has_return) from available signature text (best-effort)."""
        sig = None
        # Try conflict-level signature present in entries (first occurrence)
        if entries:
            e0 = entries[0]
            sig = e0.get('func_sig') or e0.get('signature')
        # As a fallback, nothing found
        if not sig or not isinstance(sig, str):
            return 0, False
        s = sig.strip()
        # Count args in parentheses
        args_count = 0
        has_return = False
        try:
            if '(' in s and ')' in s:
                inside = s[s.find('(')+1:s.rfind(')')].strip()
                if inside:
                    # crude split by commas
                    args_count = len([x for x in inside.split(',') if x.strip()])
            # Heuristic: if there's a ':' after parens or '->' like return annotation
            if '):' in s or '->' in s:
                has_return = True
        except Exception:
            pass
        return args_count, has_return

    def _has_wrap_coexistence(self, cls: str, meth: str) -> bool:
        """Check if @wrapMethod exists for the same class.method anywhere in last report."""
        try:
            report = self._last_report
            if not report:
                return False
            entries_obj = report.get('entries')
            if not isinstance(entries_obj, (list, tuple)):
                return False
            for e in entries_obj:  # type: ignore[operator]
                if e.get('annotation') == 'wrapMethod' and e.get('class') == cls and e.get('method') == meth:
                    return True
            return False
        except Exception:
            return False

    # --- Symptom filter UI helpers ---
    def _get_symptom_order(self) -> list:
        """Return preferred symptom code order from i18n if available; else default order."""
        try:
            # The i18n key holds codes like ["uiHud","player",...]
            order = self._bundles.get(self.var_lang.get(), {}).get('filters.symptoms.order')
            if not order and self.var_lang.get() != 'en':
                order = (self._bundles.get('en') or {}).get('filters.symptoms.order')
            if isinstance(order, list) and all(isinstance(x, str) for x in order):
                return order
        except Exception:
            pass
        return ['uiHud', 'player', 'vehicle', 'quest', 'inventory', 'damage', 'other']

    def _build_symptom_filter_row(self):
        """Build or rebuild the symptom checkbox row using i18n order; preserve states.

        Note: Widgets are created inside self.ff_sym_checks and positioned by
        _relayout_symptom_checks() using grid, so they wrap automatically based
        on available width.
        """
        try:
            if not hasattr(self, 'ff_sym_row') or self.ff_sym_row is None:
                return
            # Preserve current states
            current = {code: bool(var.get()) for code, var in (self.var_filter_symptoms or {}).items()}
            # Clear existing widgets under the checks frame (keep label on left)
            try:
                if hasattr(self, 'ff_sym_checks') and self.ff_sym_checks is not None:
                    for child in list(self.ff_sym_checks.winfo_children()):
                        try:
                            child.destroy()
                        except Exception:
                            pass
            except Exception:
                pass
            # Recreate checkboxes by preferred order; keep unknown codes after
            order = self._get_symptom_order()
            known_codes = list(self.var_filter_symptoms.keys())
            ordered = [c for c in order if c in known_codes]
            tail = [c for c in known_codes if c not in order]
            self.chk_symptoms = {}
            for code in ordered + tail:
                var = self.var_filter_symptoms.get(code)
                if var is None:
                    continue
                # restore state if existed
                try:
                    if code in current:
                        var.set(bool(current[code]))
                except Exception:
                    pass
                try:
                    try:
                        from common.common_i18n import symptom_label as _symptom_label  # type: ignore
                        label = _symptom_label(code, self._)
                    except Exception:
                        label = self._(f'impact.symptom.{code}')
                except Exception:
                    label = code
                # Increase potential line breaks (inject a zero-width space before " / ")
                try:
                    label = label.replace(' / ', ' \u200B/ ')
                except Exception:
                    pass
                # Use ttk.Checkbutton for consistent look (checkmark/focus ring)
                # wraplength assigned later in _relayout_symptom_checks (works with ttk)
                chk = ttk.Checkbutton(
                    self.ff_sym_checks,
                    text=label,
                    variable=var,
                    command=self._rerender_preview_with_filters
                )
                self.chk_symptoms[code] = chk
            # Initial layout; enable a one-time forced relayout for the next pass
            try:
                self._sym_relayout_force = True
            except Exception:
                pass
            self._relayout_symptom_checks()
            # On first show, geometry might not be settled yet.
            # Schedule additional relayouts after map/idle with small delays.
            try:
                if hasattr(self, 'ff_sym_row') and self.ff_sym_row is not None:
                    self.ff_sym_row.bind('<Map>', lambda *_: (setattr(self, '_sym_relayout_force', True), self._on_sym_checks_configure()))
            except Exception:
                pass
            try:
                self.after(120, lambda: (setattr(self, '_sym_relayout_force', True), self._on_sym_checks_configure()))
                # Also force once after idle
                self.after_idle(lambda: (setattr(self, '_sym_relayout_force', True), self._on_sym_checks_configure()))
                # Add two more delayed retries (deal with slow UI settlements)
                self.after(240, lambda: (setattr(self, '_sym_relayout_force', True), self._on_sym_checks_configure()))
                self.after(480, lambda: (setattr(self, '_sym_relayout_force', True), self._on_sym_checks_configure()))
            except Exception:
                pass
            # Reapply symptom checkbox container style on dark mode toggle
            def _retheme_symptom_checks(*_):
                # ttk.Checkbutton follows style; only frame background sync needed
                try:
                    dark2 = bool(getattr(self, 'var_dark_mode', tk.BooleanVar(value=False)).get())
                    if hasattr(self, 'ff_sym_checks') and self.ff_sym_checks is not None:
                        self.ff_sym_checks.configure(style='TFrame')  # Apply base frame style
                except Exception:
                    pass
            try:
                if not hasattr(self, '_symptom_theme_trace_added'):
                    self._symptom_theme_trace_added = True
                    if hasattr(self, 'var_dark_mode'):
                        self.var_dark_mode.trace_add('write', _retheme_symptom_checks)
            except Exception:
                pass
        except Exception:
            pass

    def _relayout_symptom_checks(self):
        """Lay out symptom checkbuttons in rows that wrap to available width.

        Strategy:
        - Measure each checkbutton's requested width (winfo_reqwidth)
        - Place them left-to-right until the next button would exceed the available
          frame width; then wrap to the next row.
        - Use grid with sticky='w' (left align) and a small horizontal padding.
        """
        try:
            if not hasattr(self, 'ff_sym_checks') or self.ff_sym_checks is None:
                return
            # Ensure geometry is updated to get accurate widths once
            try:
                self.ff_sym_checks.update_idletasks()
            except Exception:
                pass
            avail = max(0, int(self.ff_sym_checks.winfo_width()))
            if avail <= 0:
                # Fallback to parent width if not yet realized
                try:
                    avail = int(self.ff_sym_row.winfo_width()) - (self.lbl_symptoms.winfo_width() if hasattr(self, 'lbl_symptoms') and self.lbl_symptoms else 0) - 16
                except Exception:
                    avail = 600
            # Skip re-layout if width hasn't changed (unless force is set)
            try:
                force = bool(getattr(self, '_sym_relayout_force', False))
            except Exception:
                force = False
            try:
                if not force and getattr(self, '_sym_layout_last_avail', None) == avail:
                    return
                self._sym_layout_last_avail = avail
                if force:
                    self._sym_relayout_force = False
            except Exception:
                pass
            # Clear any previous grid placements
            for w in list(self.ff_sym_checks.winfo_children()):
                try:
                    w.grid_forget()
                except Exception:
                    pass
            xpad = 4
            cur_x = 0
            row = 0
            col = 0
            # Tunables for wrapping (prefer wrapping a bit more aggressively)
            wrap_margin = 14              # Padding when wrapping inside a label
            wrap_aggressive_margin = 40   # If leftover at row end is less than this, prefer in-row wrapping
            inline_wrap_threshold = 180   # If leftover is at least this value, set wraplength to keep it in-row
            for code, chk in self.chk_symptoms.items():
                # On first render only: when reaching the specified code (inventory), force a line break
                try:
                    if (not getattr(self, '_sym_force_break_applied', True)
                            and code == getattr(self, '_sym_force_break_code_initial', '')
                            and col > 0):
                        row += 1
                        col = 0
                        cur_x = 0
                        self._sym_force_break_applied = True
                except Exception:
                    pass
                try:
                    # Clear wraplength first to get the raw requested width
                    try:
                        chk.configure(wraplength=0)
                    except Exception:
                        pass
                    w = int(chk.winfo_reqwidth())
                except Exception:
                    w = 120
                need = (xpad if col > 0 else 0) + w
                # Remaining width in the current row
                leftover = max(0, avail - (cur_x + (xpad if col > 0 else 0)))
                # If it doesn't fit within the remaining width
                if col > 0 and (w + wrap_aggressive_margin) > leftover:
                    # If there's still enough space, prefer an in-row wrap using wraplength
                    if leftover >= inline_wrap_threshold:
                        try:
                            chk.configure(wraplength=max(0, leftover - wrap_margin), justify='left')
                            # After wrapping, update required width assuming it now fits within leftover space
                            w = min(w, max(0, leftover - wrap_margin))
                            need = (xpad if col > 0 else 0) + w
                        except Exception:
                            pass
                    else:
                        # Remaining width is too small, wrap to the next row
                        row += 1
                        col = 0
                        cur_x = 0
                        need = w
                        leftover = avail
                        # If it still doesn't fit on the next row, wrap within the label
                        if w > avail:
                            try:
                                chk.configure(wraplength=max(0, avail - wrap_margin), justify='left')
                                w = min(w, max(0, avail - wrap_margin))
                                need = w
                            except Exception:
                                pass
                # If it barely fits even at col==0, wrap within the label early
                if col == 0 and w > max(0, avail - wrap_aggressive_margin):
                    try:
                        # Use a lower bound so labels don't clip on very small first render
                        base = max(220, avail - wrap_margin)
                        chk.configure(wraplength=max(0, base), justify='left')
                        # Recalculate (conservatively, to avoid excessive remeasurement)
                        w = min(w, max(0, base))
                        need = w
                    except Exception:
                        pass
                try:
                    chk.grid(row=row, column=col, padx=(0, xpad), pady=2, sticky='w')
                except Exception:
                    pass
                cur_x += need
                col += 1
            # Configure columns to not stretch
            try:
                for i in range(0, col + 1):
                    self.ff_sym_checks.columnconfigure(i, weight=0)
            except Exception:
                pass
        except Exception:
            pass

    def _rebuild_symptom_row(self):
        """Safely rebuild the Symptom (Impact) row after language/visibility changes.

        Preserves existing BooleanVar states in self.var_filter_symptoms, recreates
        the row container/label/checks frame, rebuilds checkbuttons via
        _build_symptom_filter_row(), and forces a relayout.
        """
        try:
            if not hasattr(self, 'ff') or self.ff is None:
                return
            # Ensure row container exists at row=3
            need_new_row = False
            if not hasattr(self, 'ff_sym_row') or self.ff_sym_row is None:
                need_new_row = True
            else:
                try:
                    if not self.ff_sym_row.winfo_exists():
                        need_new_row = True
                except Exception:
                    need_new_row = True
            if need_new_row:
                try:
                    self.ff_sym_row = ttk.Frame(self.ff)
                    self.ff_sym_row.grid(row=3, column=0, columnspan=4, sticky='ew', padx=4, pady=(0,4))
                    self.ff_sym_row.columnconfigure(0, weight=0)
                    # Ensure right container has a minimum width so long labels don't truncate on rebuild
                    self.ff_sym_row.columnconfigure(1, weight=1, minsize=320)
                except Exception:
                    return
            # Recreate/update label via ensure_row_visibility helper
            sym_label = self._('impact.label')
            def _build_sym_label():
                if not (hasattr(self, 'lbl_symptoms') and self.lbl_symptoms and self.lbl_symptoms.winfo_exists()):
                    self.lbl_symptoms = ttk.Label(self.ff_sym_row, text=sym_label)
                    self.lbl_symptoms.grid(row=0, column=0, sticky='w', padx=(0, 10))
                else:
                    try:
                        self.lbl_symptoms.configure(text=sym_label)
                    except Exception:
                        pass
            try:
                from common.common_util import ensure_row_visibility as _erv
                _erv(self.ff_sym_row, _build_sym_label, is_visible_fn=lambda: bool(getattr(self, 'lbl_symptoms', None)))
            except Exception:
                try:
                    _build_sym_label()
                except Exception:
                    pass
            # Always (re)assert column sizing constraints after rebuild
            try:
                self.ff_sym_row.columnconfigure(0, weight=0)
                self.ff_sym_row.columnconfigure(1, weight=1, minsize=320)
            except Exception:
                pass
            # Destroy/recreate checks container
            try:
                if hasattr(self, 'ff_sym_checks') and self.ff_sym_checks is not None and self.ff_sym_checks.winfo_exists():
                    self.ff_sym_checks.destroy()
            except Exception:
                pass
            try:
                self.ff_sym_checks = ttk.Frame(self.ff_sym_row)
                self.ff_sym_checks.grid(row=0, column=1, sticky='ew')
                self._sym_layout_scheduled = False
                self._sym_layout_last_avail = None
                self.ff_sym_checks.bind('<Configure>', self._on_sym_checks_configure)
            except Exception:
                self.ff_sym_checks = None
            # Rebuild checks and relayout
            try:
                self._build_symptom_filter_row()
            except Exception:
                pass
            try:
                if hasattr(self, 'ff_sym_row') and self.ff_sym_row is not None:
                    self.ff_sym_row.bind('<Map>', lambda *_: self._on_sym_checks_configure())
            except Exception:
                pass
            try:
                self._relayout_symptom_checks()
            except Exception:
                pass
            try:
                self.after(120, lambda: self._on_sym_checks_configure())
            except Exception:
                pass
            # Ensure row min height and grid propagate
            try:
                if hasattr(self, 'ff') and self.ff is not None:
                    self.ff.rowconfigure(3, minsize=26)
                if hasattr(self, 'ff_sym_row') and self.ff_sym_row is not None:
                    self.ff_sym_row.grid_propagate(True)
                if hasattr(self, 'ff_sym_checks') and self.ff_sym_checks is not None:
                    self.ff_sym_checks.grid_propagate(True)
                self.update_idletasks()
            except Exception:
                pass
        except Exception:
            pass

    def _rebuild_severity_row(self):
        """Safely rebuild the Severity row widgets after language/visibility changes.

        Keeps the existing BooleanVar states; recreates label/frame/checkbuttons
        and rebinds layout handlers, then forces a fresh relayout.
        """
        try:
            # Ensure parent filters frame exists
            if not hasattr(self, 'ff') or self.ff is None:
                return
            # Ensure row container exists (row=2 under self.ff)
            need_new_row = False
            if not hasattr(self, 'ff_sev_row') or self.ff_sev_row is None:
                need_new_row = True
            else:
                try:
                    if not self.ff_sev_row.winfo_exists():
                        need_new_row = True
                except Exception:
                    need_new_row = True
            if need_new_row:
                try:
                    self.ff_sev_row = ttk.Frame(self.ff)
                    self.ff_sev_row.grid(row=2, column=0, columnspan=4, sticky='ew', padx=4, pady=2)
                    self.ff_sev_row.columnconfigure(0, weight=0)
                    self.ff_sev_row.columnconfigure(1, weight=1)
                except Exception:
                    return
            # Always ensure grid weights and a minimal row height
            try:
                self.ff_sev_row.columnconfigure(0, weight=0)
                self.ff_sev_row.columnconfigure(1, weight=1)
            except Exception:
                pass
            try:
                if hasattr(self, 'ff') and self.ff is not None:
                    self.ff.rowconfigure(2, minsize=26)
            except Exception:
                pass
            # Recreate or refresh label on the left (common helper)
            def _build_sev_label():
                if not (hasattr(self, 'lbl_severity') and self.lbl_severity and self.lbl_severity.winfo_exists()):
                    self.lbl_severity = ttk.Label(self.ff_sev_row, text=self._('filters.severity'))
                    self.lbl_severity.grid(row=0, column=0, sticky='w', padx=(0, 10))
                else:
                    self.lbl_severity.configure(text=self._('filters.severity'))
            try:
                from common.common_util import ensure_row_visibility as _erv  # local import safety
                _erv(self.ff_sev_row, _build_sev_label, is_visible_fn=lambda: bool(getattr(self, 'lbl_severity', None)))
            except Exception:
                # Fallback to direct build
                try:
                    _build_sev_label()
                except Exception:
                    pass
            # Destroy and recreate checks container frame to reset grid state cleanly
            try:
                if hasattr(self, 'ff_sev_checks') and self.ff_sev_checks is not None and self.ff_sev_checks.winfo_exists():
                    self.ff_sev_checks.destroy()
            except Exception:
                pass
            try:
                self.ff_sev_checks = ttk.Frame(self.ff_sev_row)
                self.ff_sev_checks.grid(row=0, column=1, sticky='ew')
                # Reset debounced layout state and bind Configure
                self._sev_layout_scheduled = False
                self._sev_layout_last_avail = None
                self.ff_sev_checks.bind('<Configure>', self._on_sev_checks_configure)
            except Exception:
                self.ff_sev_checks = None
            # Recreate checkbuttons bound to existing variables
            try:
                self.chk_sev_c = ttk.Checkbutton(self.ff_sev_checks, text=self._('filters.sev.critical'), variable=self.var_filter_sev_critical)
                self.chk_sev_h = ttk.Checkbutton(self.ff_sev_checks, text=self._('filters.sev.high'), variable=self.var_filter_sev_high)
                self.chk_sev_m = ttk.Checkbutton(self.ff_sev_checks, text=self._('filters.sev.medium'), variable=self.var_filter_sev_medium)
                self.chk_sev_l = ttk.Checkbutton(self.ff_sev_checks, text=self._('filters.sev.low'), variable=self.var_filter_sev_low)
            except Exception:
                pass
            # Force immediate and delayed relayout to settle geometry
            try:
                # Bind Map to trigger once visible
                if hasattr(self, 'ff_sev_row') and self.ff_sev_row is not None:
                    self.ff_sev_row.bind('<Map>', lambda *_: self._on_sev_checks_configure())
            except Exception:
                pass
            try:
                self._relayout_severity_checks()
            except Exception:
                pass
            try:
                self.after(120, lambda: self._on_sev_checks_configure())
            except Exception:
                pass
            # Propagate and finalize geometry (guard against rare zero-width cases)
            try:
                if hasattr(self, 'ff_sev_row') and self.ff_sev_row is not None:
                    self.ff_sev_row.grid_propagate(True)
                if hasattr(self, 'ff_sev_checks') and self.ff_sev_checks is not None:
                    self.ff_sev_checks.grid_propagate(True)
                self.update_idletasks()
            except Exception:
                pass
        except Exception:
            pass

    def _relayout_severity_checks(self):
        """Lay out severity checkbuttons in rows that wrap within remaining width after the label.

        Follows the same policy as the symptom check group: use a dedicated container
        (self.ff_sev_checks) on the right, place widgets with grid, and wrap within
        the row as needed. The label occupies the left column, so we can treat the
        effective width of self.ff_sev_checks as the available space.
        """
        try:
            if not hasattr(self, 'ff_sev_checks') or self.ff_sev_checks is None:
                return
            try:
                self.ff_sev_checks.update_idletasks()
            except Exception:
                pass
            avail = max(0, int(self.ff_sev_checks.winfo_width()))
            if avail <= 0:
                try:
                    avail = int(self.ff_sev_row.winfo_width()) - (self.lbl_severity.winfo_width() if hasattr(self, 'lbl_severity') and self.lbl_severity else 0) - 16
                except Exception:
                    avail = 400
            try:
                if getattr(self, '_sev_layout_last_avail', None) == avail:
                    return
                self._sev_layout_last_avail = avail
            except Exception:
                pass

            # Clear existing grid placements
            try:
                for w in list(self.ff_sev_checks.winfo_children()):
                    w.grid_forget()
            except Exception:
                pass

            checks = [self.chk_sev_c, self.chk_sev_h, self.chk_sev_m, self.chk_sev_l]
            # Measure widths (including label content)
            widths = []
            for chk in checks:
                if chk is None:
                    widths.append(0)
                    continue
                try:
                    chk.configure(wraplength=0)  # type: ignore[arg-type]
                except Exception:
                    pass
                try:
                    widths.append(int(chk.winfo_reqwidth()))
                except Exception:
                    widths.append(120)

            total_w = sum(widths)
            # Fixed gap for evenly-spaced, left-aligned layout (only when there is enough width)
            fixed_gap = 24
            n = len(checks)

            if avail >= total_w + (n - 1) * fixed_gap:
                # If it fits on one row, use fixed gaps with left-aligned, evenly spaced layout
                try:
                    for i in range(n + 2):
                        # Set weight=0 to avoid unwanted stretching
                        self.ff_sev_checks.columnconfigure(i, weight=0)
                except Exception:
                    pass
                col = 0
                for i, chk in enumerate(checks):
                    if chk is None:
                        continue
                    try:
                        pad = (0, fixed_gap) if i < n - 1 else (0, 0)
                        chk.grid(row=0, column=col, padx=pad, pady=2, sticky='w')
                    except Exception:
                        pass
                    col += 1
                return

            # When narrow, fall back to the wrap algorithm similar to symptoms row
            xpad = 4
            row = 0
            col = 0
            cur_x = 0
            wrap_margin = 8
            for idx, chk in enumerate(checks):
                if chk is None:
                    continue
                w = widths[idx] if idx < len(widths) else 120
                need = (xpad if col > 0 else 0) + w
                leftover = max(0, avail - (cur_x + (xpad if col > 0 else 0)))
                if col > 0 and w > leftover:
                    if leftover >= 100:
                        try:
                            chk.configure(wraplength=max(0, leftover - wrap_margin), justify='left')  # type: ignore[arg-type]
                            w = min(w, leftover - wrap_margin)
                            need = (xpad if col > 0 else 0) + w
                        except Exception:
                            pass
                    else:
                        row += 1
                        col = 0
                        cur_x = 0
                        need = w
                        leftover = avail
                        if w > avail:
                            try:
                                chk.configure(wraplength=max(0, avail - wrap_margin), justify='left')  # type: ignore[arg-type]
                                w = min(w, avail - wrap_margin)
                                need = w
                            except Exception:
                                pass
                if col == 0 and w > avail:
                    try:
                        chk.configure(wraplength=max(0, avail - wrap_margin), justify='left')  # type: ignore[arg-type]
                        w = min(w, avail - wrap_margin)
                        need = w
                    except Exception:
                        pass
                try:
                    chk.grid(row=row, column=col, padx=(0, xpad), pady=2, sticky='w')
                except Exception:
                    pass
                cur_x += need
                col += 1
            try:
                for i in range(0, col + 1):
                    self.ff_sev_checks.columnconfigure(i, weight=0)
            except Exception:
                pass
        except Exception:
            pass

    def _on_sev_checks_configure(self, *_):
        """Debounce Configure events for severity checks container."""
        try:
            if getattr(self, '_sev_layout_scheduled', False):
                return
            self._sev_layout_scheduled = True
            self.after(60, self._run_sev_relayout_scheduled)
        except Exception:
            try:
                self._relayout_severity_checks()
            except Exception:
                pass

    def _run_sev_relayout_scheduled(self):
        try:
            self._sev_layout_scheduled = False
            self._relayout_severity_checks()
        except Exception:
            pass

    def _on_sym_checks_configure(self, *_):
        """Debounce-heavy Configure events for symptom checks container."""
        try:
            # No-op if already scheduled (coalesce rapid bursts)
            if getattr(self, '_sym_layout_scheduled', False):
                return
            self._sym_layout_scheduled = True
            # Delay slightly to batch rapid events
            self.after(60, self._run_symptom_relayout_scheduled)
        except Exception:
            # Fallback: execute immediately
            try:
                self._relayout_symptom_checks()
            except Exception:
                pass

    def _run_symptom_relayout_scheduled(self):
        try:
            self._sym_layout_scheduled = False
            self._relayout_symptom_checks()
        except Exception:
            pass

    def _reset_filters(self):
        """(deprecated) Reset filters. Kept for compatibility; not wired to UI."""
        try:
            # Clear text inputs
            try:
                self.var_filter_mods.set('')
            except Exception:
                pass
            try:
                self.var_filter_class.set('')
            except Exception:
                pass
            # Reset severities to initial (all ON)
            try:
                self.var_filter_sev_critical.set(True)
                self.var_filter_sev_high.set(True)
                self.var_filter_sev_medium.set(True)
                self.var_filter_sev_low.set(True)
            except Exception:
                pass
            # Reset symptoms to initial (all ON)
            try:
                for _, var in (self.var_filter_symptoms or {}).items():
                    try:
                        var.set(True)
                    except Exception:
                        pass
            except Exception:
                pass
            # Re-render
            self._rerender_preview_with_filters()
        except Exception:
            pass

    def _set_all_symptoms(self, state: bool):
        """Set all symptom checkboxes to given state and re-render."""
        try:
            for code, var in (self.var_filter_symptoms or {}).items():
                try:
                    var.set(bool(state))
                except Exception:
                    pass
            self._rerender_preview_with_filters()
        except Exception:
            pass

    def _set_all_filters(self, state: bool):
        """Set all filter checkboxes (severity + symptoms) to given state and re-render."""
        try:
            # Severities
            try:
                self.var_filter_sev_critical.set(bool(state))
                self.var_filter_sev_high.set(bool(state))
                self.var_filter_sev_medium.set(bool(state))
                self.var_filter_sev_low.set(bool(state))
            except Exception:
                pass
            # Symptoms
            try:
                for _, var in (self.var_filter_symptoms or {}).items():
                    try:
                        var.set(bool(state))
                    except Exception:
                        pass
            except Exception:
                pass
            self._rerender_preview_with_filters()
        except Exception:
            pass

    # (Removed legacy _classify_symptom_code / _symptom_label_for_code; unified logic lives in report_builders)

    # --- Filters / Re-render / Settings / Toast ---
    def _filter_report_for_preview(self, report: dict, conflicts_only: bool) -> dict:
        """Filter conflicts by mods/class/severity for Preview only (does not affect saved files)."""
        mods_tokens = [t.strip().lower() for t in (self.var_filter_mods.get() or '').split(',') if t.strip()]
        cls_token = (self.var_filter_class.get() or '').strip().lower()
        allowed_sev = set()
        if self.var_filter_sev_critical.get():
            allowed_sev.add('critical')
        if self.var_filter_sev_high.get():
            allowed_sev.add('high')
        if self.var_filter_sev_medium.get():
            allowed_sev.add('medium')
        if self.var_filter_sev_low.get():
            allowed_sev.add('low')

        def mod_matches(mod_name: str) -> bool:
            if not mods_tokens:
                return True
            mn = (mod_name or '').lower()
            return any(tok in mn for tok in mods_tokens)

        # Symptom whitelist logic (code-based): if any checkbox active, restrict to selected codes
        symptom_vars = getattr(self, 'var_filter_symptoms', {}) or {}
        active_symptom_codes = [code for code, v in symptom_vars.items() if v.get()]
        restrict_symptoms = True  # Spec change: when all False, match none; only match when at least one is True

        new_conflicts = []
        for c in (report.get('conflicts') or []):
            cls = c.get('class','')
            meth = c.get('method','')
            entries = list(c.get('occurrences') or c.get('entries') or [])
            if cls_token and cls_token not in (cls or '').lower():
                continue
            if mods_tokens:
                entries = [e for e in entries if mod_matches(e.get('mod',''))]
                if not entries:
                    continue
            sev = self._assess_conflict_impact(cls, meth, c.get('mods', []), entries).get('severity','').lower()
            # Severity: empty set (= all False) → match none
            if not allowed_sev:
                continue
            if sev not in allowed_sev:
                continue
            # Symptoms: when zero selected (= active_symptom_codes is empty), match none
            if restrict_symptoms:
                try:
                    from common.common_impact import classify_conflict_symptom as _classify_symptom
                    code = _classify_symptom((cls or '').lower(), meth)
                except Exception:
                    code = 'other'
                if not active_symptom_codes or code not in active_symptom_codes:
                    continue
            nc = dict(c)
            if 'occurrences' in nc:
                nc['occurrences'] = entries
            elif 'entries' in nc:
                nc['entries'] = entries
            new_conflicts.append(nc)

        new_report = dict(report)
        new_report['conflicts'] = new_conflicts
        return new_report

    def _rerender_preview(self):
        """Rebuild Preview HTML/Text with current theme, language, and filters."""
        try:
            if not self._last_report:
                return
            report = self._last_report  # local narrowing
            conflicts_only = self.var_mode_conflicts.get()
            include_reference = not conflicts_only
            filtered = self._filter_report_for_preview(report, conflicts_only=conflicts_only)
            html_body = self.build_html_body(filtered, conflicts_only=conflicts_only, include_reference=include_reference)
            if self.webview2 is not None:
                self.set_preview_html_from_body(html_body)
            self._last_render_args = (filtered, conflicts_only, include_reference)
            if self.webview2 is None and self.txt_html is not None:
                self.render_report_to_text(filtered, conflicts_only=conflicts_only, include_reference=include_reference)
            # Preview-updated event emission intentionally skipped
        except Exception as e:
            self._log_i18n('[WARN]', 'log.warnRerender', err=str(e))

    def _rerender_preview_with_filters(self):
        """Apply filters and refresh preview (separate handler for the button)."""
        self._rerender_preview()

    def is_html_engine(self) -> bool:
        """Return True if WebView2 engine is active, otherwise False (Text fallback)."""
        try:
            return getattr(self, 'webview2', None) is not None
        except Exception:
            return False

    def _update_status_bar(self):
        """Refresh status bar text (engine / theme / current language)."""
        try:
            if not hasattr(self, 'status_bar') or self.status_bar is None:
                return
            # Debounce: if called again within 50ms, reschedule in 60ms
            try:
                now_ts = time.time()
                last_ts = getattr(self, '_last_status_bar_update_ts', 0)
                if now_ts - last_ts < 0.05:  # 50ms threshold
                    try:
                        if hasattr(self, '_status_bar_after_id') and self._status_bar_after_id:
                            self.after_cancel(self._status_bar_after_id)
                    except Exception:
                        pass
                    self._status_bar_after_id = self.after(60, self._update_status_bar)
                    return
                self._last_status_bar_update_ts = now_ts
            except Exception:
                pass

            eng_id = self.get_preview_engine()
            # Localized engine name (fallback to id if the key is missing)
            eng = self._(f'ui.engine.{eng_id}') if self._(f'ui.engine.{eng_id}') != f'ui.engine.{eng_id}' else eng_id
            theme = self._('theme.dark') if self.var_dark_mode.get() else self._('theme.light')
            lang = self.var_lang.get()
            # Counts
            total_conflicts = getattr(self, '_last_report', {}).get('conflicts', []) if getattr(self, '_last_report', None) else []
            total_count = len(total_conflicts) if isinstance(total_conflicts, list) else 0
            filtered_count = getattr(self, '_last_filtered_conflicts_count', total_count)
            # Filters summary (mods/class/severity)
            mods_f = self.var_filter_mods.get().strip()
            class_f = self.var_filter_class.get().strip()
            sev_parts = []
            if self.var_filter_sev_critical.get(): sev_parts.append('C')
            if self.var_filter_sev_high.get(): sev_parts.append('H')
            if self.var_filter_sev_medium.get(): sev_parts.append('M')
            if self.var_filter_sev_low.get(): sev_parts.append('L')
            sev_summary = ''.join(sev_parts) if sev_parts and len(sev_parts) < 4 else ('-' if not sev_parts else 'ALL')
            mods_lbl = self._('status.mods')
            class_lbl = self._('status.class')
            sev_lbl = self._('status.sev')
            filt_summary = f"{mods_lbl}={mods_f or '-'} {class_lbl}={class_f or '-'} {sev_lbl}={sev_summary}"
            # i18n keys used (fallback to English if missing)
            lbl_engine = self._('ui.engine')
            lbl_theme = self._('ui.theme')
            lbl_lang = self._('ui.lang')
            lbl_conflicts = self._('ui.conflicts')
            # Font family label
            try:
                lbl_font = self._('status.font')
                fam = (self.var_font_family.get() or 'Segoe UI').strip()
            except Exception:
                lbl_font, fam = 'font', 'Segoe UI'
            txt = f"{lbl_engine}: {eng} | {lbl_theme}: {theme} | {lbl_lang}: {lang} | {lbl_font}: {fam} | {lbl_conflicts}: {filtered_count}/{total_count} | {filt_summary}"
            self.status_bar.configure(text=txt)
        except Exception:
            pass

    # --- Engine introspection helpers -------------------------------------------------
    def get_preview_engine(self) -> str:
        """Return a short identifier of the active preview engine.

        Values:
            'webview2' : WebView2 control active and rendering HTML
            'text'     : Fallback styled Text widget

        This is useful for diagnostics (e.g., exposing in an About dialog or status bar).
        """
        try:
            if getattr(self, 'webview2', None) is not None:
                return 'webview2'
        except Exception:
            pass
        return 'text'

    @property
    def preview_engine(self) -> str:  # convenience alias
        return self.get_preview_engine()


    def open_about_dialog(self):
        """Show an About / Diagnostic dialog with environment & engine info."""
        try:
            dlg = tk.Toplevel(self)
            dlg.title(self._('about.title'))
            dlg.transient(self)
            # Modal: while open, the main window is not interactive
            try:
                dlg.grab_set()
            except Exception:
                pass
            frm = ttk.Frame(dlg, padding=12)
            frm.pack(fill='both', expand=True)
            snap = self.get_status_snapshot()
            rows = []
            rows.append(('Engine', snap['engine']))
            rows.append(('Theme', snap['theme']))
            rows.append(('Language', snap['lang']))
            rows.append(('Conflicts (filtered/total)', f"{snap['filtered_conflicts']}/{snap['total_conflicts']}"))
            try:
                import platform
                rows.append(('Python', platform.python_version()))
                rows.append(('Platform', platform.platform()))
            except Exception:
                pass
            # WebView2 presence
            rows.append(('WebView2 available', 'yes' if snap['engine']=='webview2' else 'no'))
            # Filter summary
            filt = snap['filters']
            sev_flags = filt.get('sev', {})
            sev_enabled = [k for k,v in sev_flags.items() if v]
            rows.append((self._('about.filters'), f"mods={filt.get('mods') or '-'} class={filt.get('class') or '-'} sev={','.join(sev_enabled) or '-'}"))
            for i,(k,v) in enumerate(rows):
                ttk.Label(frm, text=k+':', anchor='e').grid(row=i, column=0, sticky='e', padx=(0,8), pady=2)
                ttk.Label(frm, text=v, anchor='w').grid(row=i, column=1, sticky='w', padx=(0,4), pady=2)
            btns = ttk.Frame(frm)
            btns.grid(row=len(rows), column=0, columnspan=2, sticky='we', pady=(12,0))
            ttk.Button(btns, text=self._('about.close'), command=dlg.destroy).pack(side='right')
            dlg.geometry(f"420x{min(480, 120 + len(rows)*28)}")
            # Always center the dialog when it opens (no need to keep position afterward)
            try:
                dlg.bind('<Map>', lambda *_: self._center_over_parent(dlg))
            except Exception:
                pass
        except Exception:
            pass

    def get_status_snapshot(self) -> Dict[str, Any]:
        """Return a structured snapshot of current UI status for external tools/tests.

        Includes:
            engine               : 'webview2' | 'text'
            theme                : 'dark' | 'light'
            lang                 : current language code
            total_conflicts      : int (0 if no report)
            filtered_conflicts   : int (after active filters)
            filters              : dict (mods/class/severity flags/conflicts_only)
        """
        try:
            total_conflicts = len((getattr(self, '_last_report', {}) or {}).get('conflicts') or [])
        except Exception:
            total_conflicts = 0
        try:
            filtered_conflicts = len((getattr(self, '_last_render_args', [None])[0] or {}).get('conflicts') or [])
        except Exception:
            filtered_conflicts = total_conflicts
        filt_state = {
            'mods': self.var_filter_mods.get().strip(),
            'class': self.var_filter_class.get().strip(),
            'sev': {
                'critical': self.var_filter_sev_critical.get(),
                'high': self.var_filter_sev_high.get(),
                'medium': self.var_filter_sev_medium.get(),
                'low': self.var_filter_sev_low.get(),
            },
            'conflicts_only': bool(self.var_mode_conflicts.get())
        }
        return {
            'engine': self.get_preview_engine(),
            'theme': 'dark' if self.var_dark_mode.get() else 'light',
            'lang': self.var_lang.get(),
            'total_conflicts': total_conflicts,
            'filtered_conflicts': filtered_conflicts,
            'filters': filt_state,
        }

    # --- WebView2 context menu --------------------------------------------------------
    def _on_webview_context_menu(self, event):
        menu = None
        try:
            menu = tk.Menu(self, tearoff=False)
            menu.add_command(label=self._('ctx.copyHtml'), command=self._ctx_copy_html)
            menu.add_command(label=self._('ctx.openExternal'), command=self.open_preview_in_browser)
            menu.add_separator()
            menu.add_command(label=f"{self._('ui.engine')}: {self.get_preview_engine()}", state='disabled')
            menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass
        finally:
            try:
                if menu is not None:
                    menu.grab_release()
            except Exception:
                pass

    def _ctx_copy_html(self):
        try:
            if getattr(self, '_last_full_html', ''):
                self.clipboard_clear()
                self.clipboard_append(self._last_full_html)
                self._toast(self._('toast.htmlCopied'))
        except Exception:
            pass

    def _toast(self, message: str, ms: int = 2200):
        """Small non-blocking toast window near the top-right of the output area.

        Change: Show near the top-right of the output window (the current Notebook tab).
        If that position cannot be determined, fall back to the app window's top-right.
        """
        try:
            tw = tk.Toplevel(self)
            tw.overrideredirect(True)
            tw.attributes('-topmost', True)
            lbl = ttk.Label(tw, text=message)
            try:
                lbl.pack(padx=10, pady=6)
            except Exception:
                pass
            # Compute coordinates after layout is finalized
            self.update_idletasks()
            # 1) Prefer the screen coordinates of the current Notebook tab
            rx = ry = None
            try:
                nb = getattr(self, 'nb', None)
                if nb is not None:
                    # Get the child frame of the current tab
                    cur = nb.nametowidget(nb.select()) if nb.select() else None
                    if cur is not None:
                        # Screen coordinates of the current tab's top-right
                        rx = cur.winfo_rootx() + cur.winfo_width() - tw.winfo_reqwidth() - 12
                        ry = cur.winfo_rooty() + 12
            except Exception:
                rx = ry = None
            # 2) If unavailable, fall back to the app window's top-right
            if rx is None or ry is None:
                try:
                    rx = self.winfo_x() + self.winfo_width() - tw.winfo_reqwidth() - 12
                    ry = self.winfo_y() + 12
                except Exception:
                    rx = 20; ry = 20
            tw.geometry(f"+{max(0,int(rx))}+{max(0,int(ry))}")
            tw.after(ms, tw.destroy)
        except Exception:
            pass

    def _load_settings_silent(self):
        """Load persisted settings (language, toggles, filters, impact config, etc.)."""
        try:
            if hasattr(self, '_settings_path') and self._settings_path.exists():
                data = json.loads(self._settings_path.read_text(encoding='utf-8'))
                # Window size (optional)
                try:
                    ww = data.get('win_width'); wh = data.get('win_height')
                    if isinstance(ww, int) and isinstance(wh, int) and ww > 100 and wh > 100:
                        self.geometry(f"{ww}x{wh}")
                except Exception:
                    pass
                # language
                if 'lang' in data and isinstance(data['lang'], str):
                    self.var_lang.set(data['lang'])
                # Scan settings (paths)
                try:
                    if 'root' in data:
                        self.var_root.set(str(data.get('root', self.var_root.get())))
                    if 'out_json' in data:
                        self.var_out_json.set(str(data.get('out_json', self.var_out_json.get())))
                    if 'out_md' in data:
                        self.var_out_md.set(str(data.get('out_md', self.var_out_md.get())))
                    if hasattr(self, 'var_out_html') and 'out_html' in data:
                        self.var_out_html.set(str(data.get('out_html', self.var_out_html.get())))
                except Exception:
                    pass
                self.var_mode_conflicts.set(bool(data.get('mode_conflicts', True)))
                # Output toggles
                self.var_enable_preview.set(bool(data.get('enable_preview', self.var_enable_preview.get())))
                self.var_enable_json.set(bool(data.get('enable_json', False)))
                self.var_enable_md.set(bool(data.get('enable_md', False)))
                self.var_dark_mode.set(bool(data.get('dark_mode', False)))
                # Include wrapMethod coexistence toggle
                try:
                    if hasattr(self, 'var_include_wrap'):
                        self.var_include_wrap.set(bool(data.get('include_wrap', False)))
                except Exception:
                    pass
                self.var_filter_mods.set(str(data.get('filter_mods', '')))
                self.var_filter_class.set(str(data.get('filter_class', '')))
                self.var_filter_sev_critical.set(bool(data.get('sev_critical', True)))
                self.var_filter_sev_high.set(bool(data.get('sev_high', True)))
                self.var_filter_sev_medium.set(bool(data.get('sev_medium', True)))
                self.var_filter_sev_low.set(bool(data.get('sev_low', True)))
                try:
                    val = float(data.get('font_scale', 1.0))
                except Exception:
                    val = 1.0
                # Clamp to new range
                self.var_font_scale.set(max(0.5, min(1.5, val)))
                # Font family (optional)
                try:
                    fam = data.get('font_family')
                    if isinstance(fam, str) and fam.strip():
                        self.var_font_family.set(fam.strip())
                        # If a font object already exists apply it now
                        try:
                            self.apply_font_family()
                        except Exception:
                            pass
                except Exception:
                    pass
                # Font MRU list (optional)
                try:
                    mru = data.get('font_mru')
                    if isinstance(mru, list):
                        self._font_mru = [str(x) for x in mru if isinstance(x, str)][:5]
                except Exception:
                    pass
                self.var_auto_open.set(bool(data.get('auto_open', False)))
                # localize outputs option
                try:
                    if hasattr(self, 'var_localize_output'):
                        self.var_localize_output.set(bool(data.get('localize_output', True)))
                except Exception:
                    pass
                # Temp session management overrides
                try:
                    if 'retain_temp_files' in data:
                        self._retain_temp_files = bool(data.get('retain_temp_files'))
                    if 'temp_max_days' in data:
                        self._temp_max_days = int(data.get('temp_max_days') or self._temp_max_days)
                    if 'temp_max_total_mb' in data:
                        self._temp_max_total_mb = int(data.get('temp_max_total_mb') or self._temp_max_total_mb)
                except Exception:
                    pass
                # Optional: impact override
                impact_in = data.get('impact') or data.get('impact_config')
                if isinstance(impact_in, dict):
                    try:
                        # thresholds
                        th = impact_in.get('thresholds')
                        if isinstance(th, dict):
                            self._impact_cfg['thresholds'].update({k: int(v) for k, v in th.items() if isinstance(v, (int, float))})
                        # weights
                        w = impact_in.get('weights')
                        if isinstance(w, dict):
                            for key in ('per_mod', 'wrap_coexist_bonus'):
                                if key in w and isinstance(w[key], (int, float)):
                                    self._impact_cfg['weights'][key] = int(w[key])
                            if isinstance(w.get('signature'), dict):
                                self._impact_cfg['weights'].setdefault('signature', {}).update(
                                    {k: int(v) for k, v in w['signature'].items() if isinstance(v, (int, float))}
                                )
                            if isinstance(w.get('class_keywords'), dict):
                                self._impact_cfg['weights'].setdefault('class_keywords', {}).update(
                                    {str(k): int(v) for k, v in w['class_keywords'].items() if isinstance(v, (int, float))}
                                )
                            if isinstance(w.get('method_keywords'), dict):
                                self._impact_cfg['weights'].setdefault('method_keywords', {}).update(
                                    {str(k): int(v) for k, v in w['method_keywords'].items() if isinstance(v, (int, float))}
                                )
                    except Exception:
                        pass
        except Exception as e:
            self.log(f'[WARN] Failed to load settings: {e}')

    def _save_settings(self):
        """Persist current settings to a JSON file in the user's home folder."""
        try:
            # Sync settings path from UI
            try:
                self._settings_path = Path(self.var_settings_path.get()) if getattr(self, 'var_settings_path', None) else self._settings_path
            except Exception:
                pass
            # Ensure parent dir exists
            try:
                self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            # Capture current window size
            try:
                self.update_idletasks()
                win_w = int(self.winfo_width())
                win_h = int(self.winfo_height())
            except Exception:
                win_w = None; win_h = None
            # Compose data in GUI order for readability when opened by users
            items = []
            # UI / Language
            items.append(('lang', self.var_lang.get()))
            items.append(('dark_mode', self.var_dark_mode.get()))
            # Window size (if available)
            if isinstance(win_w, int) and isinstance(win_h, int):
                items.append(('win_width', win_w))
                items.append(('win_height', win_h))
            # Scan settings
            items.append(('root', self.var_root.get()))
            # Output paths (HTML/MD/JSON)
            items.append(('out_html', getattr(self, 'var_out_html', tk.StringVar(value='')).get()))
            items.append(('out_md', self.var_out_md.get()))
            items.append(('out_json', self.var_out_json.get()))
            # Mode
            items.append(('mode_conflicts', self.var_mode_conflicts.get()))
            # Options toggles (order mirrors UI: HTML, MD, JSON, Auto-open, Localize)
            items.append(('enable_preview', self.var_enable_preview.get()))
            items.append(('enable_md', self.var_enable_md.get()))
            items.append(('enable_json', self.var_enable_json.get()))
            items.append(('auto_open', self.var_auto_open.get()))
            items.append(('localize_output', bool(getattr(self, 'var_localize_output', tk.BooleanVar(value=False)).get())))
            # Include wrapMethod coexistence
            items.append(('include_wrap', bool(getattr(self, 'var_include_wrap', tk.BooleanVar(value=False)).get())))
            # Preview options
            items.append(('font_scale', float(self.var_font_scale.get() or 1.0)))
            try:
                items.append(('font_family', str(self.var_font_family.get() or 'Segoe UI')))
            except Exception:
                pass
            # Persist MRU font list if available
            try:
                if hasattr(self, '_font_mru') and isinstance(self._font_mru, list) and self._font_mru:
                    items.append(('font_mru', [str(x) for x in self._font_mru[:5]]))
            except Exception:
                pass
            # Filters (mods/class then severities: Critical, High, Medium, Low)
            items.append(('filter_mods', self.var_filter_mods.get()))
            items.append(('filter_class', self.var_filter_class.get()))
            items.append(('sev_critical', self.var_filter_sev_critical.get()))
            items.append(('sev_high', self.var_filter_sev_high.get()))
            items.append(('sev_medium', self.var_filter_sev_medium.get()))
            items.append(('sev_low', self.var_filter_sev_low.get()))
            # Temp session config
            items.append(('retain_temp_files', bool(getattr(self, '_retain_temp_files', False))))
            items.append(('temp_max_days', int(getattr(self, '_temp_max_days', 5))))
            items.append(('temp_max_total_mb', int(getattr(self, '_temp_max_total_mb', 300))))

            data = {k: v for (k, v) in items}
            if hasattr(self, '_settings_path'):
                self._settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                self._save_settings_pointer()
        except Exception as e:
            self.log(f'[WARN] Failed to save settings: {e}')

    def _save_settings_pointer(self):
        """Persist the chosen settings path into the bootstrap JSON next to the exe/source.

        The bootstrap file is redscript_conflict_gui.json and contains at least:
        { "settings_path": "<absolute path to actual settings json>" }
        """
        try:
            if not getattr(self, '_settings_bootstrap', None):
                self._exe_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else SRC_DIR
                self._settings_bootstrap = self._exe_dir / 'redscript_conflict_gui.json'
            # Merge/update existing bootstrap content
            data = {}
            try:
                if self._settings_bootstrap.exists():
                    data = json.loads(self._settings_bootstrap.read_text(encoding='utf-8'))
                    if not isinstance(data, dict):
                        data = {}
            except Exception:
                data = {}
            data['settings_path'] = str(self._settings_path)
            # Ensure parent exists and write
            try:
                self._settings_bootstrap.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            self._settings_bootstrap.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass

    # --- Window positioning helpers ---
    def _center_over_parent(self, child: tk.Toplevel):
        """Center a child window over this main window with safe clamping to screen bounds."""
        try:
            # Ensure sizes are calculated
            self.update_idletasks()
            child.update_idletasks()
            # Parent geometry
            px = int(self.winfo_x()); py = int(self.winfo_y())
            pw = int(self.winfo_width()); ph = int(self.winfo_height())
            # Child desired size (reqwidth/height may be 1 before layout); fallback to current size
            cw = int(max(child.winfo_reqwidth(), child.winfo_width()))
            ch = int(max(child.winfo_reqheight(), child.winfo_height()))
            # Calculate centered position
            x = px + (pw - cw) // 2
            y = py + (ph - ch) // 2
            # Clamp to visible screen
            sw = int(self.winfo_screenwidth()); sh = int(self.winfo_screenheight())
            x = max(0, min(x, max(0, sw - cw)))
            y = max(0, min(y, max(0, sh - ch)))
            child.geometry(f"+{x}+{y}")
            # Optional: caller may schedule an extra recenter after ~50ms if drift observed
        except Exception:
            pass

    def _center_on_map_once(self, win: tk.Toplevel):
        """Bind <Map> to center a toplevel once, then unbind (helper)."""
        def _do_center(_e=None):
            try:
                self._center_over_parent(win)
            except Exception:
                pass
            # One retry after Windows WM adjust (occasional small drift)
            try:
                win.after(40, lambda: self._center_over_parent(win) if win.winfo_exists() else None)
            except Exception:
                pass
            try:
                win.unbind('<Map>')
            except Exception:
                pass
        try:
            win.bind('<Map>', _do_center)
        except Exception:
            pass



    # --- i18n helpers ---
    def _make_gettext(self):
        """Return a gettext-like lookup bound to current self.var_lang.

        Falls back to English if the key is missing in the selected language, then to
        a best-effort last-segment of the key (e.g., 'label' from 'foo.bar.label').
        """
        def _(key: str) -> str:
            lang = getattr(self, 'var_lang', tk.StringVar(value='en')).get()
            b = self._bundles.get(lang) or {}
            if key in b:
                try: self._i18n_used_keys.add(key)
                except Exception: pass
                return b[key]
            enb = self._bundles.get('en') or {}
            if lang != 'en' and key in enb:
                try: self._i18n_used_keys.add(key)
                except Exception: pass
                return enb[key]
            return key.split('.')[-1]
        return _

    def _make_gettext_for(self, lang: str):
        """Return a gettext-like lookup bound to a specific language code (used for file outputs)."""
        def _(key: str) -> str:
            b = self._bundles.get(lang) or {}
            if key in b:
                return b[key]
            if lang != 'en' and key in (self._bundles.get('en') or {}):
                return (self._bundles.get('en') or {})[key]
            return key.split('.')[-1]
        return _

    def on_change_language(self, event=None):
        """Update language state from combobox and refresh all visible labels/tabs."""
        try:
            # Rebind _() to new language (var_lang already updated by menu radiobutton)
            try:
                self._ = self._make_gettext()
            except Exception:
                pass
            # Update window title and static labels
            self.title(self._('app.title'))
            try:
                if hasattr(self, 'lbl_theme') and self.lbl_theme:
                    self.lbl_theme.configure(text=self._('theme.label'))
            except Exception:
                pass
            try:
                if hasattr(self, 'var_dark_label') and self.var_dark_label:
                    self.var_dark_label.set(self._('theme.dark') if self.var_dark_mode.get() else self._('theme.light'))
            except Exception:
                pass
            # Tabs
            try:
                # Preview HTML tab label (localized)
                self.nb.tab(0, text=self._('tabs.html'))
                self.nb.tab(1, text=self._('tabs.markdown'))
                self.nb.tab(2, text=self._('tabs.json'))
                self.nb.tab(3, text=self._('tabs.log'))
            except Exception:
                pass
            # Mode label
            self.var_mode_text.set(self._('mode.conflicts') if self.var_mode_conflicts.get() else self._('mode.reference'))
            # Scan settings labels/buttons
            try:
                self.lf.configure(text=self._('scan.settings'))
            except Exception:
                pass
            try:
                self.lbl_scan_root.configure(text=self._('scan.root'))
            except Exception:
                pass
            try:
                btn = self.btn_browse_root
                if btn is not None:
                    btn.configure(text=self._('scan.browse'))
            except Exception:
                pass
            # Rebuild menus to reflect new language
            try:
                self._build_menus()
            except Exception:
                pass
            # If the right-aligned Theme menubutton exists, update its text as well
            try:
                lbl_t = self.lbl_theme_text
                if lbl_t is not None and lbl_t.winfo_exists():
                    title_theme = self._('theme.label')
                    lbl_t.configure(text=title_theme)
                if hasattr(self, 'var_dark_label'):
                    self.var_dark_label.set(self._('theme.dark') if self.var_dark_mode.get() else self._('theme.light'))
            except Exception:
                pass
            # Refresh texts in the Output settings window if open
            try:
                self._refresh_output_window_texts()
            except Exception:
                pass
            # Filters labels/buttons
            try:
                self.ff.configure(text=self._('filters.title'))
                self.lbl_filters_mods.configure(text=self._('filters.mods'))
                self.lbl_filters_class.configure(text=self._('filters.class'))
                # Update row labels (Severity / Symptoms)
                try:
                    if hasattr(self, 'lbl_severity') and self.lbl_severity:
                        self.lbl_severity.configure(text=self._('filters.severity'))
                except Exception:
                    pass
                # Safely rebuild the severity check row (handles rare cases where it becomes hidden)
                try:
                    self._rebuild_severity_row()
                except Exception:
                    # Fallback: update label texts only
                    try:
                        self.chk_sev_c.configure(text=self._('filters.sev.critical'))
                        self.chk_sev_h.configure(text=self._('filters.sev.high'))
                        self.chk_sev_m.configure(text=self._('filters.sev.medium'))
                        self.chk_sev_l.configure(text=self._('filters.sev.low'))
                    except Exception:
                        pass
                # Update symptom checkbox labels
                try:
                    # Safely rebuild the Impact (Symptoms) row as well
                    try:
                        self._rebuild_symptom_row()
                    except Exception:
                        # Fallback: only update labels and re-layout the existing row
                        self._build_symptom_filter_row()
                    try:
                        if hasattr(self, 'lbl_symptoms') and self.lbl_symptoms:
                            sym_label = self._('impact.label')
                            self.lbl_symptoms.configure(text=sym_label)
                    except Exception:
                        pass
                    # Update quick select buttons labels
                    try:
                        if hasattr(self, 'btn_sym_all') and self.btn_sym_all:
                            self.btn_sym_all.configure(text=self._('filters.symptoms.all'))
                        if hasattr(self, 'btn_sym_none') and self.btn_sym_none:
                            self.btn_sym_none.configure(text=self._('filters.symptoms.none'))
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                pass
            # Also verify Impact (Symptoms) row visibility and rebuild if it's not visible
            try:
                def _ensure_sym_visible():
                    try:
                        self.update_idletasks()
                    except Exception:
                        pass
                    try:
                        ok = True
                        _sym_row = getattr(self, 'ff_sym_row', None)
                        if not _sym_row or not _sym_row.winfo_ismapped():
                            ok = False
                        _sym_checks = getattr(self, 'ff_sym_checks', None)
                        if not _sym_checks or not _sym_checks.winfo_ismapped():
                            ok = False
                        w = int(_sym_checks.winfo_width()) if _sym_checks else 0
                        h = int(_sym_row.winfo_height()) if _sym_row else 0
                        if w < 10 or h < 10:
                            ok = False
                        if not ok:
                            try:
                                log_message('info', self.log, 'Symptom row not visible after lang change; rebuilding...')
                            except Exception:
                                pass
                            self._rebuild_symptom_row()
                            try:
                                self.after_idle(self._on_sym_checks_configure)
                            except Exception:
                                pass
                    except Exception:
                        pass
                self.after(260, _ensure_sym_visible)
                self.after(520, _ensure_sym_visible)
            except Exception:
                pass
            # Preview options
            try:
                self.pf.configure(text=self._('preview.options'))
                self.lbl_font_scale.configure(text=self._('preview.fontScale'))
                if self.chk_auto_open is not None:
                    self.chk_auto_open.configure(text=self._('options.autoOpen'))
            except Exception:
                pass
            # Copy toolbar not present
            # Options / action labels (previously one big try; now separate to avoid skipping later updates if one attribute is missing)
            # Mode frame title
            try:
                if hasattr(self, 'mf') and self.mf:
                    self.mf.configure(text=self._('mode.label'))
            except Exception:
                pass
            # wrapMethod coexistence checkbox label
            try:
                if hasattr(self, 'chk_include_wrap') and self.chk_include_wrap:
                    self.chk_include_wrap.configure(text=self._('options.includeWrap'))
            except Exception:
                pass
            # (Deprecated) old options frame title
            try:
                if hasattr(self, 'of') and self.of:
                    self.of.configure(text=self._('options.title'))
            except Exception:
                pass
            # Output settings window widgets (only if present)
            try:
                if hasattr(self, 'lbl_output_files') and self.lbl_output_files:
                    self.lbl_output_files.configure(text=self._('options.files'))
            except Exception:
                pass
            for attr_name, key in [
                ('chk_enable_preview', 'options.fileHtml'),
                ('chk_enable_md', 'options.fileMd'),
                ('chk_enable_json', 'options.fileJson'),
                ('chk_localize_output', 'options.localizeOutput'),
            ]:
                try:
                    w = getattr(self, attr_name, None)
                    if w:
                        w.configure(text=self._(key))
                except Exception:
                    pass
            # Actions buttons (main window)
            try:
                if hasattr(self, 'btn_run') and self.btn_run:
                    self.btn_run.configure(text=self._('actions.generate'))
            except Exception:
                pass
            try:
                if hasattr(self, 'btn_open_folder') and self.btn_open_folder:
                    self.btn_open_folder.configure(text=self._('actions.openFolder'))
            except Exception:
                pass
            try:
                if hasattr(self, 'btn_open_browser') and self.btn_open_browser:
                    self.btn_open_browser.configure(text=self._('actions.openBrowser'))
            except Exception:
                pass
            # Severity row: Force re-layout after updating labels/checks
            try:
                if hasattr(self, 'ff_sev_checks') and self.ff_sev_checks is not None:
                    # Reset width cache to ensure layout recomputation
                    try:
                        self._sev_layout_last_avail = None
                    except Exception:
                        pass
                    # Re-layout in two phases: immediately and after idle (not dependent on initial mapped state)
                    try:
                        self._relayout_severity_checks()
                    except Exception:
                        pass
                    try:
                        self.after(120, lambda: self._on_sev_checks_configure())
                    except Exception:
                        pass
                    # Additional visibility check (handles rare zero-width / unmapped cases)
                    try:
                        def _ensure_visible():
                            try:
                                # Ensure geometry is finalized just before measuring
                                try:
                                    self.update_idletasks()
                                except Exception:
                                    pass
                                ok = True
                                # Mapped state
                                _sev_row = self.ff_sev_row
                                _sev_checks = self.ff_sev_checks
                                if not _sev_row or not _sev_row.winfo_ismapped():
                                    ok = False
                                if not _sev_checks or not _sev_checks.winfo_ismapped():
                                    ok = False
                                w = int(_sev_checks.winfo_width()) if _sev_checks else 0
                                h = int(_sev_row.winfo_height()) if _sev_row else 0
                                if w < 10 or h < 10:
                                    ok = False
                                # Verify children are gridded and at least one has visible width
                                childs = [self.chk_sev_c, self.chk_sev_h, self.chk_sev_m, self.chk_sev_l]
                                any_visible_width = False
                                for ch in childs:
                                    try:
                                        if ch and ch.winfo_ismapped() and int(ch.winfo_width()) > 0:
                                            any_visible_width = True
                                            break
                                    except Exception:
                                        pass
                                if not any_visible_width:
                                    ok = False
                                if not ok:
                                    try:
                                        log_message('info', self.log, 'Severity row not visible after lang change; rebuilding...')
                                    except Exception:
                                        pass
                                    self._rebuild_severity_row()
                                    # Force layout once more after idle
                                    try:
                                        self.after_idle(self._on_sev_checks_configure)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        # Verify in two passes (after UI stabilization)
                        self.after(260, _ensure_visible)
                        self.after(520, _ensure_visible)
                    except Exception:
                        pass
            except Exception:
                pass
            # Re-render preview to update texts in HTML/Text
            self._rerender_preview()
            # Also refresh Markdown/JSON previews if we have a last report so language applies immediately
            try:
                if self._last_report is not None:
                    report = self._last_report  # local
                    conflicts_only = self.var_mode_conflicts.get()
                    include_reference = not conflicts_only
                    # JSON preview (trim if conflicts_only), always include localized labels for display
                    try:
                        if conflicts_only:
                            data = {
                                'scanned_root': report.get('scanned_root'),
                                'files_scanned': report.get('files_scanned'),
                                'annotation_counts': report.get('annotation_counts'),
                                'conflicts': report.get('conflicts'),
                            }
                        else:
                            data = dict(report)
                        data_disp = self._augment_json_with_localized(data)
                        self.set_preview_json(json.dumps(data_disp, ensure_ascii=False, indent=2))
                    except Exception:
                        pass
                    # Markdown preview (localized)
                    try:
                        md_src = dict(report)
                        md_text = self._build_localized_markdown(md_src, conflicts_only=conflicts_only, include_reference=include_reference)
                        self.set_preview_md(md_text)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            self.log(f'[WARN] Failed to apply language: {e}')
        try:
            self._update_status_bar()
        except Exception:
            pass

    def _build_menus(self):
        """Create or rebuild the main menubar (Language, Output settings, Theme button)."""
        try:
            # Debug logging (remove later if noisy)
            # Verbose debug log suppressed (previously '[INFO] Rebuilding menubar').
            # If needed for future troubleshooting, re-enable behind a debug flag:
            # if getattr(self, 'debug_logs', False): self.log('[DEBUG] Rebuilding menubar')
            # Top-level menus: Display settings (with Language submenu) + Output settings
            title_display = self._('menu.display')
            title_lang_sub = self._('menu.display.language')
            title_output = self._('menu.output')
            title_theme = self._('theme.label')
            open_outwin = self._('menu.output.openWindow')
            # Tooling (key re-order / i18n audit) not included in runtime build

            # Main menu instance
            if not hasattr(self, 'main_menu') or self.main_menu is None:
                self.main_menu = tk.Menu(self)
                self.config(menu=self.main_menu)
            else:
                try:
                    self.main_menu.delete(0, 'end')
                except Exception:
                    pass
                # Ensure still attached
                try:
                    self.config(menu=self.main_menu)
                except Exception:
                    pass

            # Display settings menu (contains Theme submenu, Language submenu, Font scale submenu)
            m_display = tk.Menu(self.main_menu, tearoff=False)

            # Dark mode toggle + Font scale submenu (moved before Language)
            def _set_theme(is_dark: bool):
                try:
                    # Directly set var_dark_mode (bypass toggle logic)
                    self.var_dark_mode.set(is_dark)
                    # on_toggle_dark will update label and theme
                    self.on_toggle_dark()
                except Exception:
                    pass
            m_theme = tk.Menu(m_display, tearoff=False)
            # Force apply theme to ensure consistent styling
            is_dark = self.var_dark_mode.get()
            m_theme.add_radiobutton(label=self._('theme.light'), value=False, variable=self.var_dark_mode, command=lambda: _set_theme(False))
            m_theme.add_radiobutton(label=self._('theme.dark'), value=True, variable=self.var_dark_mode, command=lambda: _set_theme(True))
            m_display.add_cascade(label=title_theme, menu=m_theme)

            # Language submenu (moved after Theme)
            m_lang = tk.Menu(m_display, tearoff=False)
            # System default option (maps to get_lang_default result)
            try:
                system_default = _ci_choose_lang(self._bundles)
            except Exception:
                system_default = 'en'
            label_system = self._('menu.display.systemDefault')
            def _set_system_lang():
                try:
                    self.var_lang.set(system_default)
                except Exception:
                    pass
            m_lang.add_command(label=f"{label_system} ({system_default})", command=_set_system_lang)
            if self._bundles:
                m_lang.add_separator()
            for code, bundle in self._bundles.items():
                try:
                    if not isinstance(bundle, dict):
                        continue
                    meta_raw = bundle.get('$meta')
                    meta = meta_raw if isinstance(meta_raw, dict) else {}
                    meta_type = meta.get('type')
                    # Legacy: only entries with type == 'langpack' were allowed.
                    # New: also accept entries where 'type' is missing.
                    # Future-proof: if we want to exclude some, use type=='internal' or meta.get('hidden') flags.
                    if meta_type in ('internal', 'hidden', 'skip'):
                        continue
                    lang_name = meta.get('name') or code
                    lang_name = f"{lang_name} ({code})" if code != 'en' else lang_name
                    m_lang.add_radiobutton(label=lang_name, value=code, variable=self.var_lang)
                except Exception:
                    pass
            m_display.add_cascade(label=self._('menu.display.language'), menu=m_lang)

            # Font family submenu (placed above font scale)
            try:
                label_font_family = self._('menu.display.fontFamily')
                m_fontfam = tk.Menu(m_display, tearoff=False)
                # Keep reference for live refresh
                self._menu_font_family_submenu = m_fontfam
                def _set_ff(val: str):
                    try:
                        self.var_font_family.set(val)
                        self.apply_font_family()
                    except Exception:
                        pass
                try:
                    import tkinter.font as tkfont  # noqa: F401
                    # Show current font (disabled line)
                    try:
                        cur_fam = (self.var_font_family.get() or 'Segoe UI').strip()
                        cur_label_key = self._('fontChooser.current')
                        cur_label = cur_label_key
                        m_fontfam.add_command(label=f'{cur_label} {cur_fam}', state='disabled')
                        m_fontfam.add_separator()
                    except Exception:
                        pass
                    # Show MRU entries excluding current font
                    recent = getattr(self, '_font_mru', [])
                    recent_filtered = [r for r in recent if r != cur_fam]
                    if recent_filtered:
                        recent_label = self._('menu.display.fontRecent')
                        if recent_label == 'menu.display.fontRecent':
                            recent_label = 'Recent'
                        m_fontfam.add_command(label=f'— {recent_label} —', state='disabled')
                        for rf in recent_filtered:
                            try:
                                m_fontfam.add_radiobutton(label=rf, value=rf, variable=self.var_font_family, command=lambda v=rf: _set_ff(v))
                            except Exception:
                                pass
                        m_fontfam.add_separator()
                    # More... launches full chooser (i18n fallback to English)
                    try:
                        more_label = self._('menu.display.fontMore')
                        if more_label == 'menu.display.fontMore':
                            more_label = 'More...'
                        m_fontfam.add_command(label=more_label, command=self.open_font_chooser)
                    except Exception:
                        pass
                except Exception:
                    pass
                m_display.add_cascade(label=label_font_family, menu=m_fontfam)
            except Exception:
                pass

            # Font scale submenu (50%-150% by 10% steps as radiobuttons)
            label_font_scale = self._('menu.display.fontScale')
            m_font = tk.Menu(m_display, tearoff=False)
            def _set_fs(val: float):
                try:
                    self.var_font_scale.set(val)
                except Exception:
                    pass
            try:
                cur = float(self.var_font_scale.get() or 1.0)
            except Exception:
                cur = 1.0
            # 0.5 -> 1.5 inclusive (0.1 step)
            v = 0.5
            while v < 1.5001:  # Float safety margin for inclusive 1.5 due to rounding
                pct = int(round(v * 100))
                label = f"{pct}%"
                try:
                    m_font.add_radiobutton(label=label, value=v, variable=self.var_font_scale, command=lambda val=v: _set_fs(val))
                except Exception:
                    pass
                v = round(v + 0.1, 2)
            m_display.add_cascade(label=label_font_scale, menu=m_font)

            # Separator before other future display items (if needed)
            self.main_menu.add_cascade(label=title_display, menu=m_display)
            self.menu_display = m_display
            self.menu_language = m_lang

            # Output submenu
            m_out = tk.Menu(self.main_menu, tearoff=False)
            m_out.add_command(label=open_outwin, command=self.open_output_settings_window)
            m_out.add_separator()
            # Reflect new labeling consistent with main UI row
            m_out.add_checkbutton(label=self._('options.fileHtml'), variable=self.var_enable_preview)
            m_out.add_checkbutton(label=self._('options.fileMd'), variable=self.var_enable_md)
            m_out.add_checkbutton(label=self._('options.fileJson'), variable=self.var_enable_json)
            m_out.add_separator()
            m_out.add_checkbutton(label=self._('options.localizeOutput'), variable=self.var_localize_output)
            m_out.add_checkbutton(label=self._('options.autoOpen'), variable=self.var_auto_open)
            # (Removed) includeWrap toggle: per latest spec, this option is no longer exposed in Output settings menu
            # Removed: reordering / i18n audit
            self.main_menu.add_cascade(label=title_output, menu=m_out)
            self.menu_output = m_out

            # Engine / diagnostics section moved from Output to Display menu
            try:
                m_display.add_separator()
                lbl_engine = self._('ui.engine')
                m_display.add_command(label=f"{lbl_engine}: {self.get_preview_engine()}", state='disabled')

                # WebView2 Diagnostics
                def _open_wv2_diag():  # pragma: no cover - GUI
                    try:
                        win = tk.Toplevel(self)
                        win.title(self._('webview2.diagnostics.title'))
                        win.geometry('520x360')
                        txt = tk.Text(win, wrap='word', state='normal', height=20)
                        txt.pack(fill='both', expand=True)
                        lines = []
                        lines.append(self._('webview2.diagnostics.header'))
                        lines.append(f"Imported: {bool(HAS_WEBVIEW2)} (source={_WEBVIEW2_IMPORT_SRC})")
                        if _WEBVIEW2_IMPORT_ERR:
                            e1, e2 = _WEBVIEW2_IMPORT_ERR
                            lines.append(f"Primary Import Error: {e1.__class__.__name__}: {e1}")
                            if e2:
                                lines.append(f"Secondary Import Error: {e2.__class__.__name__}: {e2}")
                        try:
                            can_load = self._webview2_can_load()
                        except Exception as exc:
                            can_load = False
                            lines.append(f"Probe Error: {exc}")
                        lines.append(f"Can Load Now: {can_load}")
                        try:
                            wv = getattr(self, 'webview2', None)
                            lines.append(f"Widget Present: {wv is not None}")
                            if wv is not None:
                                try:
                                    lines.append(f"Widget Size: {wv.winfo_width()}x{wv.winfo_height()}")
                                except Exception:
                                    pass
                                # Dump key attrs heuristically
                                for attr in ('web_view','browser','_webview','load_html','navigate'):
                                    try:
                                        lines.append(f"hasattr({attr})={hasattr(wv, attr)}")
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        try:
                            lines.append(f"Last Full HTML cached: {bool(getattr(self,'_last_full_html',None))}")
                            lines.append(f"Last Render Args set: {bool(getattr(self,'_last_render_args',None))}")
                        except Exception:
                            pass
                        try:
                            txt.insert('1.0', '\n'.join(lines))
                            txt.configure(state='disabled')
                        except Exception:
                            pass
                        # Center the window when it opens (same as About dialog)
                        try:
                            win.bind('<Map>', lambda *_: self._center_over_parent(win))
                        except Exception:
                            pass
                    except Exception:
                        pass
                try:
                    m_display.add_command(label=self._('webview2.diagnostics.menu'), command=_open_wv2_diag)
                except Exception:
                    pass

                m_display.add_separator()
                m_display.add_command(label=self._('about.menu'), command=self.open_about_dialog)
            except Exception:
                pass

            # (Removed) Right side theme button & label now replaced by Theme submenu.
            try:
                log_message('info', self.log, 'Menubar build complete')
            except Exception:
                pass
        except Exception as e:
            try:
                self.log(f'[WARN] Menubar build failed: {e}')
            except Exception:
                pass

    # (removed) on_reorder_keys and on_run_i18n_audit: now handled ad-hoc on the chat side

    def open_output_settings_window(self):
        """Open a dedicated window to manage output file settings with a layout similar to Scan settings."""
        try:
            # Reuse if already open
            if getattr(self, '_outwin', None) is not None and self._outwin.winfo_exists():
                self._outwin.lift(); self._outwin.focus_force(); return

            w = tk.Toplevel(self); self._outwin = w
            # Window title: separate concept (output.settings) from frame title (output.destDir)
            try:
                # Localized window title (fallback to English literal only if key missing)
                _title = self._('output.settings')
                if _title == 'output.settings':
                    _title = 'Output Settings'
                w.title(_title)
            except Exception:
                pass
            for fn in (lambda: w.transient(self), lambda: w.grab_set()):
                try: fn()
                except Exception: pass
            try: w.resizable(True, False)
            except Exception: pass

            frm = ttk.Frame(w)
            frm.pack(fill='both', expand=True)

            # File toggles area (placed ABOVE destination frame)
            self._outwin_toggles = {}
            file_toggles = ttk.Frame(frm)
            file_toggles.pack(fill='x', padx=8, pady=(6, 4), anchor='w')
            def _mk_file(label_key, var, r, c):
                try: txt = self._(label_key)
                except Exception: txt = label_key
                cb = ttk.Checkbutton(file_toggles, text=txt, variable=var)
                cb.grid(row=r, column=c, sticky='w', padx=(0, 10), pady=2)
                self._outwin_toggles[label_key] = cb; return cb
            self.lbl_outwin_files = ttk.Label(file_toggles, text=self._('options.files'))
            self.lbl_outwin_files.grid(row=0, column=0, sticky='w', padx=(0, 12))
            _mk_file('options.fileHtml', self.var_enable_preview, 0, 1)
            _mk_file('options.fileMd', self.var_enable_md, 0, 2)
            _mk_file('options.fileJson', self.var_enable_json, 0, 3)

            # Destination / paths frame
            lf = ttk.LabelFrame(frm, text=self._('output.destDir'))
            lf.pack(fill='x', padx=8, pady=6)
            self._outwin_frame = lf
            row = 0
            self.lbl_settings_path2 = ttk.Label(lf, text=self._('settings.file'))
            self.lbl_settings_path2.grid(row=row, column=0, sticky='w', padx=8, pady=6)
            self.ent_settings_path2 = ttk.Entry(lf, textvariable=self.var_settings_path)
            self.ent_settings_path2.grid(row=row, column=1, sticky='ew', padx=8, pady=6)
            self.btn_browse_settings2 = ttk.Button(lf, text=self._('scan.saveAs'), command=self.on_browse_settings)
            self.btn_browse_settings2.grid(row=row, column=2, padx=8, pady=6)
            row += 1
            ttk.Label(lf, text=self._('scan.outHtml')).grid(row=row, column=0, sticky='w', padx=8, pady=6)
            self.ent_out_html = ttk.Entry(lf, textvariable=self.var_out_html); self.ent_out_html.grid(row=row, column=1, sticky='ew', padx=8, pady=6)
            self.btn_browse_html = ttk.Button(lf, text=self._('scan.browse'), command=self.on_browse_html); self.btn_browse_html.grid(row=row, column=2, padx=8, pady=6); row += 1
            ttk.Label(lf, text=self._('scan.outMd')).grid(row=row, column=0, sticky='w', padx=8, pady=6)
            self.ent_out_md = ttk.Entry(lf, textvariable=self.var_out_md); self.ent_out_md.grid(row=row, column=1, sticky='ew', padx=8, pady=6)
            self.btn_browse_md = ttk.Button(lf, text=self._('scan.browse'), command=self.on_browse_md); self.btn_browse_md.grid(row=row, column=2, padx=8, pady=6); row += 1
            ttk.Label(lf, text=self._('scan.outJson')).grid(row=row, column=0, sticky='w', padx=8, pady=6)
            self.ent_out_json = ttk.Entry(lf, textvariable=self.var_out_json); self.ent_out_json.grid(row=row, column=1, sticky='ew', padx=8, pady=6)
            self.btn_browse_json = ttk.Button(lf, text=self._('scan.browse'), command=self.on_browse_json); self.btn_browse_json.grid(row=row, column=2, padx=8, pady=6); row += 1
            for c in (0,1,2):
                try: lf.columnconfigure(c, weight=1 if c==1 else 0)
                except Exception: pass

            # Misc toggles + open folder button in SAME row (bottom area)
            misc_toggles = ttk.Frame(frm)
            misc_toggles.pack(fill='x', padx=8, pady=(0,6), anchor='w')
            def _mk_misc(label_key, var, col):
                try: txt = self._(label_key)
                except Exception: txt = label_key
                cb = ttk.Checkbutton(misc_toggles, text=txt, variable=var)
                cb.grid(row=0, column=col, sticky='w', padx=(0,10), pady=2)
                self._outwin_toggles[label_key] = cb; return cb
            col_misc = 0
            if hasattr(self, 'var_localize_output'):
                _mk_misc('options.localizeOutput', self.var_localize_output, col_misc); col_misc += 1
            _mk_misc('options.autoOpen', self.var_auto_open, col_misc); col_misc += 1
            # spacer stretch
            try: misc_toggles.columnconfigure(col_misc, weight=1)
            except Exception: pass
            self.btn_open_folder_outwin = ttk.Button(misc_toggles, text=self._('actions.openFolder'), command=self.on_open_folder)
            self.btn_open_folder_outwin.grid(row=0, column=col_misc+1, sticky='e', padx=(4,0), pady=2)

            def _sync():
                try:
                    st_h = 'normal' if self.var_enable_preview.get() else 'disabled'
                    st_m = 'normal' if self.var_enable_md.get() else 'disabled'
                    st_j = 'normal' if self.var_enable_json.get() else 'disabled'
                    if self.ent_out_html is not None: self.ent_out_html.configure(state=st_h)
                    if self.btn_browse_html is not None: self.btn_browse_html.configure(state=st_h)
                    if self.ent_out_md is not None: self.ent_out_md.configure(state=st_m)
                    if self.btn_browse_md is not None: self.btn_browse_md.configure(state=st_m)
                    if self.ent_out_json is not None: self.ent_out_json.configure(state=st_j)
                    if self.btn_browse_json is not None: self.btn_browse_json.configure(state=st_j)
                except Exception: pass
            _sync()
            for v in (self.var_enable_preview, self.var_enable_md, self.var_enable_json):
                try: v.trace_add('write', lambda *_: _sync())
                except Exception: pass

            def _on_destroy(*_):
                try:
                    if getattr(self, '_outwin', None) is not None and not self._outwin.winfo_exists():
                        self._outwin = None
                except Exception: self._outwin = None
            try: w.bind('<Destroy>', _on_destroy)
            except Exception: pass

            def _center_once(evt=None):
                try: self._center_over_parent(w)
                except Exception: pass
                try: w.unbind('<Map>')
                except Exception: pass
            try: w.bind('<Map>', _center_once)
            except Exception: pass

            # After initial layout, widen window roughly 2x its requested width
            try:
                w.update_idletasks()
                cur_w = w.winfo_reqwidth()
                cur_h = w.winfo_reqheight()
                new_w = int(cur_w * 2)
                try:
                    if self.winfo_exists():
                        px = self.winfo_rootx(); py = self.winfo_rooty()
                        pw = self.winfo_width(); ph = self.winfo_height()
                        if pw > 0 and ph > 0:
                            x = px + max(0, (pw - new_w)//2)
                            y = py + max(0, (ph - cur_h)//2)
                            w.geometry(f"{new_w}x{cur_h}+{x}+{y}")
                        else:
                            w.geometry(f"{new_w}x{cur_h}")
                    else:
                        w.geometry(f"{new_w}x{cur_h}")
                except Exception:
                    w.geometry(f"{new_w}x{cur_h}")
            except Exception:
                pass
        except Exception:
            # Silently ignore; window may fail due to missing attributes during early startup
            try: self.log('[WARN] Failed to build Output Settings window')
            except Exception: pass

    def _refresh_output_window_texts(self):
        """Refresh labels/texts in the Output settings window if it is open (i18n update)."""
        try:
            if getattr(self, '_outwin', None) is None or not self._outwin.winfo_exists():
                return
            w = self._outwin
            # Window title uses output.settings key; frame uses output.destDir
            try:
                _title = self._('output.settings')
                if _title == 'output.settings':
                    _title = 'Output Settings'
                w.title(_title)
            except Exception:
                pass
            # Update frame title and widget texts if they exist
            for widget, key in [
                (getattr(self, 'lbl_settings_path2', None), 'settings.file'),
            ]:
                try:
                    if widget is not None:
                        widget.configure(text=self._(key))
                except Exception:
                    pass
            # Update options.files label
            try:
                lbl_files = getattr(self, 'lbl_outwin_files', None)
                if lbl_files is not None:
                    try:
                        # noinspection PyUnresolvedReferences
                        if lbl_files.winfo_exists():
                            lbl_files.configure(text=self._('options.files'))
                    except Exception:
                        pass
            except Exception:
                pass
            # Update toggle row checkbox labels (options.* keys)
            try:
                toggles = getattr(self, '_outwin_toggles', {}) or {}
                for key, cb in toggles.items():
                    try:
                        if cb is not None:
                            try:
                                # noinspection PyUnresolvedReferences
                                if cb.winfo_exists():
                                    cb.configure(text=self._(key))
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
            # Update static labels and browse buttons
            try:
                for child in w.winfo_children():
                    # Update LabelFrame title
                    if isinstance(child, ttk.LabelFrame) or child.winfo_class() == 'TLabelframe':
                        try:
                            cfg = getattr(child, 'configure', None)
                            if cfg:
                                cfg(text=self._('output.destDir'))
                        except Exception:
                            pass
            except Exception:
                pass
            # Update the specific label and button near settings entry
            try:
                if hasattr(self, 'btn_browse_settings2') and self.btn_browse_settings2.winfo_exists():
                    self.btn_browse_settings2.configure(text=self._('scan.saveAs'))
            except Exception:
                pass
            # Open folder button text refresh
            try:
                if hasattr(self, 'btn_open_folder_outwin') and self.btn_open_folder_outwin.winfo_exists():
                    self.btn_open_folder_outwin.configure(text=self._('actions.openFolder'))
            except Exception:
                pass
        except Exception:
            pass

    # --- Localized output helpers ---
    def _build_localized_markdown(self, report: dict, conflicts_only: bool, include_reference: bool) -> str:
        lines: List[str] = []
        _ = self._
        lines.append(f"# {_( 'report.header' )}\n")
        lines.append(f"- {_( 'report.scannedRoot' )} `{report.get('scanned_root','')}`\n")
        lines.append(f"- {_( 'report.filesScanned' )} {report.get('files_scanned',0)}\n")
        ac = report.get('annotation_counts') or {}
        lines.append(f"- Annotation counts: replaceMethod={ac.get('replaceMethod',0)}, wrapMethod={ac.get('wrapMethod',0)}, replaceGlobal={ac.get('replaceGlobal',0)}\n")
        # Conflicts
        lines.append(f"\n## {_( 'report.conflicts' ).split('(')[0].strip()}\n")
        confs = report.get('conflicts', []) or []
        if not confs:
            lines.append(f"{_( 'report.noConflicts' )}\n")
        else:
            for c in sorted(confs, key=lambda x: (x.get('class',''), x.get('method',''))):
                mods_str = ", ".join(c.get('mods', []))
                lines.append(f"### {c.get('class','')}.{c.get('method','')}  — {c.get('count',0)} occurrences  — MODs: {mods_str}\n")
                occs = c.get('occurrences') or c.get('entries') or []
                if occs:
                    sig = occs[0].get('func_sig') or occs[0].get('signature') or ''
                    if sig:
                        lines.append(f"{_('report.targetMethod')}: `{sig}`\n")
                for occ in occs:
                    mod = occ.get('mod', '<unknown>')
                    rel = occ.get('relpath', occ.get('file',''))
                    lines.append(f"- [{mod}] {rel}:{occ.get('line','')}\n")
                lines.append("")
    # wrapMethod coexistence (if present and enabled)
        include_wrap = False
        try:
            include_wrap = bool(self.var_include_wrap.get())
        except Exception:
            include_wrap = False
        wrap_co = report.get('wrap_coexistence', []) or []
        if include_wrap and wrap_co:
            h = _( 'report.wrapCoexist' )
            lines.append(f"\n## {h}\n")
            for c in sorted(wrap_co, key=lambda x: (x.get('class',''), x.get('method',''))):
                mods_str = ", ".join(c.get('mods', []))
                lines.append(f"### {c.get('class','')}.{c.get('method','')}  — wraps: {c.get('wrap_count',0)}  — MODs: {mods_str}\n")
                for occ in c.get('occurrences') or []:
                    mod = occ.get('mod','<unknown>')
                    rel = occ.get('relpath', occ.get('file',''))
                    lines.append(f"- [{mod}] {rel}:{occ.get('line','')}\n")
                lines.append("")
    # Replace + wrapMethod coexistence (if present and enabled)
        rw_co = report.get('replace_wrap_coexistence', []) or []
        if include_wrap and rw_co:
            h = _( 'report.replaceWrapCoexist' )
            lines.append(f"\n## {h}\n")
            for c in sorted(rw_co, key=lambda x: (x.get('class',''), x.get('method',''))):
                lines.append(f"### {c.get('class','')}.{c.get('method','')}  — replace: {c.get('replace_count',0)}, wrap: {c.get('wrap_count',0)}\n")
                mods_r = ", ".join(c.get('mods_replace', []))
                mods_w = ", ".join(c.get('mods_wrap', []))
                if mods_r:
                    lines.append(f"- Replace MODs: {mods_r}\n")
                if mods_w:
                    lines.append(f"- Wrap MODs: {mods_w}\n")
                lines.append("")

        # Reference section
        if (not conflicts_only) and include_reference:
            lines.append(f"\n## {_( 'report.reference' )}\n")
            # Core uses 'replaceMethod' (no leading '@')
            repl_entries = [e for e in report.get('entries', []) if e.get('annotation')=='replaceMethod']
            grouped: Dict[tuple, list] = {}
            for e in repl_entries:
                key = (e.get('class',''), e.get('method',''))
                grouped.setdefault(key, []).append(e)
            for (cls, meth), gitems in sorted(grouped.items()):
                mods = sorted({e.get('mod','<unknown>') for e in gitems})
                mod_str = ", ".join(mods)
                lines.append(f"### {cls}.{meth} — MODs: {mod_str}\n")
                if gitems:
                    sig = gitems[0].get('func_sig') or gitems[0].get('signature') or ''
                    if sig:
                        lines.append(f"{_('report.targetMethod')}: `{sig}`\n")
                for e in gitems:
                    rel = e.get('relpath', e.get('file',''))
                    mod = e.get('mod', '<unknown>')
                    lines.append(f"- [{mod}] {rel}:{e.get('line','')}\n")
                lines.append("")
        return "\n".join(lines)

    def _augment_json_with_localized(self, data: dict) -> dict:
        try:
            lang = self.var_lang.get()
            localized = {
                'lang': lang,
                'labels': {
                    'header': self._('report.header'),
                    'scannedRoot': self._('report.scannedRoot'),
                    'filesScanned': self._('report.filesScanned'),
                    'conflicts': self._('report.conflicts').split('(')[0].strip(),
                    'noConflicts': self._('report.noConflicts'),
                    'reference': self._('report.reference'),
                    'impact': self._('impact.label'),
                }
            }
            out = dict(data)
            out['localized'] = localized
            return out
        except Exception:
            return data

    def _on_close(self):
        try:
            self._save_settings()
        except Exception:
            pass
        # Attempt early cleanup (atexit will also try)
        try:
            self._cleanup_session_temp_dir()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

def main(argv=None):
    """Entry point.

    By default does NOT open the About/Diagnostics dialog on startup.
    Pass --diag to open it automatically for troubleshooting.
    """
    import sys
    if argv is None:
        argv = sys.argv[1:]
    show_diag = False
    # Simple arg parse (avoid adding argparse dependency to keep single-file clarity)
    cleaned = []
    for a in argv:
        if a == '--diag':
            show_diag = True
        else:
            cleaned.append(a)
    app = App()
    app.apply_theme()
    if show_diag:
        try:
            # Defer a little so window is realized
            app.after(200, app.open_about_dialog)
        except Exception:
            pass
    app.mainloop()


if __name__ == '__main__':
    main()
