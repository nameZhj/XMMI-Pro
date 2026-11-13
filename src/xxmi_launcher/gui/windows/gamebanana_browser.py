"""
@file: src/xxmi_launcher/gui/windows/gamebanana_browser.py
@brief: Multi-site Wuthering Waves mod browser manager and WebView2 subprocess entry point.
@exports: GameBananaBrowserManager, run_gamebanana_browser
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

_this_dir = Path(__file__).resolve().parent
_xxmi_root = _this_dir.parent.parent
if str(_xxmi_root) not in sys.path:
    sys.path.insert(0, str(_xxmi_root))

from core.mod_sites import MOD_SITE_CATALOG, ModSiteSpec, detect_site_from_url, get_site_by_id
from core.readfrog_translator import ReadFrogConfig
from gui.windows.mod_browser_bridge import ModBrowserBridge, build_browser_chrome, load_readfrog_js, start_ipc_threads
from gui.windows.mod_browser_dialogs import show_account_helper_dialog, show_readfrog_settings_dialog
from gui.windows.mod_browser_downloads import ModBrowserDownloadHandler

log = logging.getLogger("ModBrowser")
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(name)s %(levelname)s %(message)s")

_WEBVIEW_AVAILABLE = False
System = SystemDrawing = WinForms = Action = Color = CoreWebView2DownloadState = None
try:
    import webview
    import webview.platforms.edgechromium as edge
    import webview.platforms.winforms as wf
    import clr

    clr.AddReference("System.Windows.Forms")
    clr.AddReference("System.Drawing")
    clr.AddReference(edge.interop_dll_path("Microsoft.Web.WebView2.Core.dll"))

    import System
    import System.Drawing as SystemDrawing
    import System.Windows.Forms as WinForms
    from System import Action
    from System.Drawing import Color
    from Microsoft.Web.WebView2.Core import CoreWebView2DownloadState
    _WEBVIEW_AVAILABLE = True
except Exception as e:
    log.warning(f"WinForms/WebView2 unavailable: {e}")

GAMEBANANA_WUWA_URL = "https://gamebanana.com/games/20357"


class GameBananaBrowserManager:
    """Orchestrates multi-site mod browsing, login routing, download capture, and Read Frog translation."""

    def __init__(
        self, mods_dir: Path, download_dir: Path, cache_dir: Path,
        parent_pid: int = 0, initial_url: str = GAMEBANANA_WUWA_URL, initial_site_id: str = "gamebanana"
    ) -> None:
        self.mods_dir = Path(mods_dir)
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.parent_pid = parent_pid

        self.active_site: ModSiteSpec = detect_site_from_url(initial_url) or get_site_by_id(initial_site_id)
        self.home_url = initial_url or self.active_site.home_url
        self._pending_mod_url: str = self.active_site.home_url if ("login" in self.home_url or "sign_in" in self.home_url) else ""
        self.rf_config = ReadFrogConfig.load()

        self.form = self.browser_view = self.webview = self.window = None
        self.lbl_status = self.progress_bar = self.txt_url = self.cmb_site = self.btn_return = self.btn_rf_toggle = None
        self._url_bar_left = 200
        self._active_download_count = 0
        self._suppress_site_event = False

        self.dl_handler = ModBrowserDownloadHandler(
            download_dir=self.download_dir, parent_pid=parent_pid,
            update_ui=self.update_ui, emit_event=self.emit_event, on_count_delta=self._on_dl_count_delta,
        )
        self.bridge = ModBrowserBridge(self, load_readfrog_js(_xxmi_root), System)
        start_ipc_threads(self)

    def _on_dl_count_delta(self, delta: int) -> None:
        self._active_download_count = max(0, self._active_download_count + delta)

    def emit_event(self, event_data: dict) -> None:
        try:
            sys.stdout.write(json.dumps(event_data, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception:
            pass

    def setup_form_ui(self, form, browser_view) -> None:
        self.form, self.browser_view, self.webview = form, browser_view, browser_view.webview
        form.BackColor = Color.FromArgb(18, 22, 34)
        form.Text = "🌐 鸣潮模组站集成浏览器（多站点 + 陪读蛙翻译） - XXMI Launcher"
        form.Resize += self._on_form_resize

        build_browser_chrome(WinForms, SystemDrawing, self)
        self.webview.Dock = WinForms.DockStyle.Fill
        self.webview.SendToBack()
        self.webview.SourceChanged += self._on_source_changed
        self.webview.CoreWebView2InitializationCompleted += self._on_core_webview_ready

    def _on_core_webview_ready(self, sender, args) -> None:
        if hasattr(args, "IsSuccess") and not args.IsSuccess:
            return
        core = sender.CoreWebView2
        core.DownloadStarting += lambda s, e: self.dl_handler.handle_download_starting(s, e, System, CoreWebView2DownloadState)
        core.NavigationStarting += self._on_nav_starting
        core.NavigationCompleted += self.bridge.on_nav_completed
        core.WebMessageReceived += self.bridge.on_web_message

    def _on_nav_starting(self, s, e) -> None:
        uri = str(e.Uri)
        if uri.startswith(("gamebanana://", "xxmi://")):
            e.Cancel = True
            self.bridge.handle_protocol_url(uri)

    def _exec_js(self, js: str) -> None:
        if self.webview and self.webview.CoreWebView2:
            self.webview.CoreWebView2.ExecuteScriptAsync(js)

    def _exec_js_ui(self, js: str) -> None:
        self._run_on_ui(lambda: self._exec_js(js))

    def _on_form_resize(self, sender, args) -> None:
        if self.txt_url and self.form:
            self.txt_url.Width = max(120, self.form.Width - self._url_bar_left - 70)

    def _on_source_changed(self, sender, args) -> None:
        curr_url = str(sender.Source)
        detected = detect_site_from_url(curr_url)
        if detected and detected.site_id != self.active_site.site_id:
            self.active_site = detected
            self._sync_site_combo()
        if self.txt_url:
            self._run_on_ui(lambda: setattr(self.txt_url, "Text", curr_url))

    def _sync_site_combo(self) -> None:
        def _do():
            self._suppress_site_event = True
            for i, s in enumerate(MOD_SITE_CATALOG):
                if s.site_id == self.active_site.site_id and self.cmb_site:
                    self.cmb_site.SelectedIndex = i
                    break
            self._suppress_site_event = False
        self._run_on_ui(_do)

    def _on_site_combo_changed(self, sender, args) -> None:
        if self._suppress_site_event or not self.cmb_site:
            return
        idx = self.cmb_site.SelectedIndex
        if 0 <= idx < len(MOD_SITE_CATALOG):
            self._open_site(MOD_SITE_CATALOG[idx], force_home=False)

    def _open_site(self, site: ModSiteSpec, force_home: bool = False) -> None:
        self.active_site = site
        self.home_url = site.home_url
        if not force_home and site.login_required:
            self._pending_mod_url = site.home_url
        self.update_ui(f"🌐 已切换至【{site.name}】 — {site.description}")
        if self.browser_view:
            self.browser_view.load_url(site.home_url)

    def _go_login_page(self) -> None:
        curr = (self.txt_url.Text or "").strip() if self.txt_url else ""
        if curr and "login" not in curr and "sign_in" not in curr:
            self._pending_mod_url = curr
        self.update_ui(f"🔑 正在前往 {self.active_site.short_name} 登录页，登录后点击【↩ 返回模组页】即可继续。")
        if self.browser_view:
            self.browser_view.load_url(self.active_site.login_url)

    def _return_to_pending_mod(self) -> None:
        target = self._pending_mod_url or self.active_site.home_url
        self.update_ui(f"↩ 已返回模组页：{target}")
        if self.browser_view:
            self.browser_view.load_url(target)

    def _navigate_to_input(self) -> None:
        url = (self.txt_url.Text or "").strip() if self.txt_url else ""
        if url:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            self.browser_view.load_url(url)

    def _open_account_helper(self) -> None:
        show_account_helper_dialog(WinForms, SystemDrawing, self.form, self.active_site, self.browser_view, self.webview)

    def _open_readfrog_settings(self) -> None:
        show_readfrog_settings_dialog(WinForms, SystemDrawing, self.form, self.rf_config, self._apply_rf_config)

    def _rf_btn_label(self) -> str:
        if not self.rf_config.enabled:
            return "🐸 翻译: 已关闭"
        return "🐸 翻译: 双语" if self.rf_config.mode == "bilingual" else "🐸 翻译: 仅译文"

    def _refresh_rf_button(self) -> None:
        if self.btn_rf_toggle:
            self._run_on_ui(lambda: setattr(self.btn_rf_toggle, "Text", self._rf_btn_label()))

    def _toggle_readfrog(self) -> None:
        self.rf_config.enabled = not self.rf_config.enabled
        self.rf_config.save()
        self._refresh_rf_button()
        js = f"window.__ReadFrog && window.__ReadFrog.{'enable(' + json.dumps(self.rf_config.mode) + ')' if self.rf_config.enabled else 'disable()'};"
        self._exec_js(js)

    def _apply_rf_config(self, cfg: ReadFrogConfig) -> None:
        self.rf_config = cfg
        self._refresh_rf_button()
        js = f"window.__ReadFrog && window.__ReadFrog.{'setMode(' + json.dumps(cfg.mode) + '); window.__ReadFrog.enable(' + json.dumps(cfg.mode) + ')' if cfg.enabled else 'disable()'};"
        self._exec_js(js)

    def _run_on_ui(self, fn) -> None:
        if self.form and self.form.InvokeRequired:
            self.form.BeginInvoke(Action(fn))
        else:
            fn()

    def update_ui(self, status_text: Optional[str] = None, progress_pct: Optional[float] = None,
                  is_error: bool = False, is_success: bool = False) -> None:
        if not self.form or not self.lbl_status:
            return
        def _do():
            if status_text is not None:
                self.lbl_status.Text = status_text
                rgb = (248, 113, 113) if is_error else ((74, 222, 128) if is_success else (56, 189, 248))
                self.lbl_status.ForeColor = Color.FromArgb(*rgb)
            if progress_pct is not None:
                self.progress_bar.Visible = True
                self.progress_bar.Value = max(0, min(100, int(progress_pct)))
            elif not self._active_download_count:
                self.progress_bar.Visible = False
        self._run_on_ui(_do)


def run_gamebanana_browser(mods_dir=None, download_dir=None, cache_dir=None, parent_pid: int = 0, initial_url: str = GAMEBANANA_WUWA_URL):
    parser = argparse.ArgumentParser(description="Multi-site Mod Browser for XXMI Launcher")
    parser.add_argument("--mods-dir", type=str, default=str(mods_dir or ""))
    parser.add_argument("--download-dir", type=str, default=str(download_dir or ""))
    parser.add_argument("--cache-dir", type=str, default=str(cache_dir or ""))
    parser.add_argument("--initial-url", type=str, default=str(initial_url or GAMEBANANA_WUWA_URL))
    parser.add_argument("--site", type=str, default="gamebanana")
    parser.add_argument("--parent-pid", type=int, default=parent_pid)
    parser.add_argument("--gamebanana-browser", action="store_true")
    args, _ = parser.parse_known_args()

    site = get_site_by_id(args.site)
    init_url = args.initial_url or site.home_url
    if not _WEBVIEW_AVAILABLE:
        webbrowser.open(init_url)
        return

    manager = GameBananaBrowserManager(
        mods_dir=Path(args.mods_dir) if args.mods_dir else Path.cwd() / "Mods",
        download_dir=Path(args.download_dir) if args.download_dir else Path.cwd() / "Downloads",
        cache_dir=Path(args.cache_dir) if args.cache_dir else Path.cwd() / "UserData" / "GameBananaBrowser",
        parent_pid=args.parent_pid, initial_url=init_url, initial_site_id=site.site_id,
    )

    def _new_win_handler(self_view, s, e):
        try:
            e.set_Handled(True)
            uri = str(e.get_Uri())
            if uri.startswith(("gamebanana://", "xxmi://")):
                manager.bridge.handle_protocol_url(uri)
            else:
                self_view.load_url(uri)
        except Exception:
            pass

    edge.EdgeChrome.on_download_starting = lambda self, s, e: manager.dl_handler.handle_download_starting(s, e, System, CoreWebView2DownloadState)
    edge.EdgeChrome.on_new_window_request = _new_win_handler
    _orig_init = wf.BrowserView.BrowserForm.__init__
    wf.BrowserView.BrowserForm.__init__ = lambda self, w, sp: (_orig_init(self, w, sp), manager.setup_form_ui(self, self.browser))

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
    manager.window = webview.create_window("🌐 鸣潮模组站集成浏览器 - XXMI Launcher", url=init_url, width=1280, height=860, min_size=(980, 640), resizable=True)
    manager.emit_event({"event": "ready"})
    webview.start(private_mode=False, storage_path=str(manager.cache_dir))


if __name__ == "__main__":
    run_gamebanana_browser()
