"""
@file: src/xxmi_launcher/gui/windows/mod_browser_bridge.py
@brief: WinForms toolbar builder, Read Frog JS bridge, and site-aware mod download dispatcher.
@exports: build_browser_chrome, ModBrowserBridge
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any, Callable, Optional

from core.mod_sites import MOD_SITE_CATALOG, ModSiteSpec, build_site_download_js
from core.readfrog_translator import ReadFrogConfig, ReadFrogTranslator

log = logging.getLogger("ModBrowserBridge")
_NAV_HEIGHT = 82
_STATUS_HEIGHT = 34
_RF_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ReadFrog")


def load_readfrog_js(xxmi_root: Path) -> str:
    """Loads injected Read Frog JS script from source or frozen bundle."""
    js_path = xxmi_root / "core" / "readfrog_inject.js"
    if not js_path.exists() and getattr(sys, "_MEIPASS", None):
        js_path = Path(sys._MEIPASS) / "core" / "readfrog_inject.js"
    return js_path.read_text(encoding="utf-8") if js_path.exists() else ""


def build_browser_chrome(winforms, drawing, mgr: Any) -> None:
    """Constructs the two-row WinForms navigation bar and bottom status bar."""
    form = mgr.form
    top_panel = winforms.Panel()
    top_panel.Dock = winforms.DockStyle.Top
    top_panel.Height = _NAV_HEIGHT
    top_panel.BackColor = drawing.Color.FromArgb(24, 30, 48)

    x = 6
    def add_btn(text: str, w: int, y: int, rgb: tuple, fn: Callable[[], None], bold: bool = False):
        nonlocal x
        btn = winforms.Button()
        btn.Text, btn.Size, btn.Location = text, drawing.Size(w, 30), drawing.Point(x, y)
        btn.FlatStyle, btn.FlatAppearance.BorderSize = winforms.FlatStyle.Flat, 0
        btn.BackColor, btn.ForeColor = drawing.Color.FromArgb(*rgb), drawing.Color.White
        btn.Font = drawing.Font("Microsoft YaHei", 9, drawing.FontStyle.Bold if bold else drawing.FontStyle.Regular)
        btn.Click += lambda s, e: fn()
        top_panel.Controls.Add(btn)
        x += w + 4
        return btn

    add_btn("◀", 30, 6, (38, 48, 70), lambda: mgr.webview.CanGoBack and mgr.webview.GoBack())
    add_btn("▶", 30, 6, (38, 48, 70), lambda: mgr.webview.CanGoForward and mgr.webview.GoForward())
    add_btn("🔄", 30, 6, (38, 48, 70), lambda: mgr.webview.Reload())

    mgr.cmb_site = winforms.ComboBox()
    mgr.cmb_site.DropDownStyle = winforms.ComboBoxStyle.DropDownList
    mgr.cmb_site.Location, mgr.cmb_site.Size = drawing.Point(x + 2, 8), drawing.Size(205, 28)
    mgr.cmb_site.BackColor, mgr.cmb_site.ForeColor = drawing.Color.FromArgb(13, 18, 28), drawing.Color.White
    mgr.cmb_site.Font = drawing.Font("Microsoft YaHei", 9)
    for idx, s in enumerate(MOD_SITE_CATALOG):
        mgr.cmb_site.Items.Add(s.name)
        if s.site_id == mgr.active_site.site_id:
            mgr.cmb_site.SelectedIndex = idx
    mgr.cmb_site.SelectedIndexChanged += mgr._on_site_combo_changed
    top_panel.Controls.Add(mgr.cmb_site)
    x += 212

    add_btn("🔑 登录当前站", 94, 6, (37, 99, 235), mgr._go_login_page)
    mgr.btn_return = add_btn("↩ 返回模组页", 96, 6, (71, 85, 105), mgr._return_to_pending_mod)
    add_btn("⚙ 账号助手", 78, 6, (79, 70, 229), mgr._open_account_helper)
    add_btn("⬇ 抓取并下载此模组", 136, 6, (22, 163, 74), mgr.bridge.trigger_page_download, bold=True)
    add_btn("🐸 翻译设置", 86, 6, (13, 148, 136), mgr._open_readfrog_settings)

    x = 6
    add_btn("🏠 专区首页", 88, 44, (234, 88, 12), lambda: mgr._open_site(mgr.active_site, force_home=True), bold=True)
    mgr.btn_rf_toggle = add_btn(mgr._rf_btn_label(), 116, 44, (16, 185, 129), mgr._toggle_readfrog)
    add_btn("📁 下载目录", 84, 44, (71, 85, 105), lambda: os.startfile(str(mgr.download_dir)))

    mgr._url_bar_left = x + 2
    mgr.txt_url = winforms.TextBox()
    mgr.txt_url.Location = drawing.Point(mgr._url_bar_left, 46)
    mgr.txt_url.Size = drawing.Size(max(120, form.Width - mgr._url_bar_left - 70), 26)
    mgr.txt_url.BackColor, mgr.txt_url.ForeColor = drawing.Color.FromArgb(13, 18, 28), drawing.Color.FromArgb(226, 232, 240)
    mgr.txt_url.Font = drawing.Font("Segoe UI", 9)
    mgr.txt_url.BorderStyle = winforms.BorderStyle.FixedSingle
    mgr.txt_url.Anchor = winforms.AnchorStyles.Top | winforms.AnchorStyles.Left | winforms.AnchorStyles.Right
    mgr.txt_url.KeyDown += lambda s, e: (mgr._navigate_to_input(), setattr(e, "SuppressKeyPress", True)) if e.KeyCode == winforms.Keys.Enter else None
    top_panel.Controls.Add(mgr.txt_url)

    btn_go = winforms.Button()
    btn_go.Text, btn_go.Size, btn_go.Location = "前往", drawing.Size(54, 26), drawing.Point(form.Width - 62, 45)
    btn_go.Anchor = winforms.AnchorStyles.Top | winforms.AnchorStyles.Right
    btn_go.FlatStyle, btn_go.FlatAppearance.BorderSize = winforms.FlatStyle.Flat, 0
    btn_go.BackColor, btn_go.ForeColor = drawing.Color.FromArgb(37, 99, 235), drawing.Color.White
    btn_go.Font = drawing.Font("Microsoft YaHei", 9)
    btn_go.Click += lambda s, e: mgr._navigate_to_input()
    top_panel.Controls.Add(btn_go)

    bottom_panel = winforms.Panel()
    bottom_panel.Dock, bottom_panel.Height = winforms.DockStyle.Bottom, _STATUS_HEIGHT
    bottom_panel.BackColor = drawing.Color.FromArgb(15, 18, 28)
    mgr.lbl_status = winforms.Label()
    mgr.lbl_status.Text = f"💡 当前站点: {mgr.active_site.name} | 点击网页下载或【⬇ 抓取并下载此模组】将自动导入！"
    mgr.lbl_status.ForeColor = drawing.Color.FromArgb(148, 163, 184)
    mgr.lbl_status.Font = drawing.Font("Microsoft YaHei", 9)
    mgr.lbl_status.Location, mgr.lbl_status.AutoSize = drawing.Point(10, 8), True
    bottom_panel.Controls.Add(mgr.lbl_status)

    mgr.progress_bar = winforms.ProgressBar()
    mgr.progress_bar.Size, mgr.progress_bar.Location = drawing.Size(200, 16), drawing.Point(form.Width - 218, 9)
    mgr.progress_bar.Anchor = winforms.AnchorStyles.Top | winforms.AnchorStyles.Right
    mgr.progress_bar.Visible = False
    bottom_panel.Controls.Add(mgr.progress_bar)

    form.Controls.Add(top_panel)
    top_panel.BringToFront()
    form.Controls.Add(bottom_panel)
    bottom_panel.BringToFront()


class ModBrowserBridge:
    """Bridges WebView2 DOM translation (Read Frog), login gating, and site downloads."""

    def __init__(self, mgr: Any, rf_script: str, system_mod: Any) -> None:
        self.mgr = mgr
        self.rf_script = rf_script
        self.system_mod = system_mod

    def on_nav_completed(self, s, e) -> None:
        if not e.IsSuccess or not self.rf_script:
            return
        try:
            self.mgr.webview.CoreWebView2.ExecuteScriptAsync(self.rf_script)
            cfg = self.mgr.rf_config
            if cfg.enabled and cfg.auto_translate_foreign and self.mgr.active_site.auto_translate:
                self.mgr._exec_js(f"window.__ReadFrog && window.__ReadFrog.enable({json.dumps(cfg.mode)});")
        except Exception as ex:
            log.debug(f"ReadFrog injection warning: {ex}")

    def on_web_message(self, s, e) -> None:
        try:
            msg = json.loads(e.TryGetWebMessageAsString())
        except Exception:
            return
        mtype = msg.get("type")
        if mtype == "rf_state_changed":
            self.mgr.rf_config.enabled = bool(msg.get("enabled", True))
            self.mgr.rf_config.mode = str(msg.get("mode", "bilingual"))
            self.mgr._refresh_rf_button()
            return
        if mtype != "rf_translate_batch":
            return
        req_id, items = str(msg.get("reqId", "")), msg.get("items") or []
        if not req_id or not items:
            return

        def worker():
            translated = ReadFrogTranslator.translate_batch(items, self.mgr.rf_config)
            js = f"window.__ReadFrog && window.__ReadFrog.receiveBatch({json.dumps(req_id)}, {json.dumps(translated, ensure_ascii=False)});"
            self.mgr._exec_js_ui(js)

        _RF_EXECUTOR.submit(worker)

    def handle_protocol_url(self, uri: str) -> None:
        clean_u = uri.replace("gamebanana://", "").replace("xxmi://", "").strip("/")
        file_id = next((p for p in reversed(clean_u.split("/")) if p.isdigit()), "")
        if file_id:
            dl_url = f"https://gamebanana.com/mmdl/{file_id}"
            self.mgr.update_ui(f"⬇ 检测到一键下载链接，启动下载: {dl_url}...")
            self.mgr.browser_view.load_url(dl_url)
        else:
            self.mgr.update_ui(f"⚠ 无法解析一键下载链接: {uri}", is_error=True)

    def trigger_page_download(self) -> None:
        current_url = (self.mgr.txt_url.Text or "").strip() if self.mgr.txt_url else ""
        if self.mgr.active_site.site_id == "gamebanana":
            try:
                from core.gamebanana_service import GameBananaService
                mod_id = GameBananaService.parse_mod_id(current_url)
                if mod_id:
                    threading.Thread(target=self._api_download_gb, args=(mod_id,), daemon=True).start()
                    return
            except Exception:
                pass
        self._run_site_dom_download(current_url)

    def _api_download_gb(self, mod_id: str) -> None:
        from core.gamebanana_service import GameBananaService
        self.mgr.update_ui(f"🔍 正在解析 GameBanana Mod #{mod_id}...", progress_pct=0)
        details = GameBananaService.fetch_mod_details(mod_id)
        if details and details.files:
            f = details.files[0]
            ok, _ = GameBananaService.download_and_import(
                f.download_url, f.filename, download_dir=self.mgr.download_dir,
                progress_callback=lambda txt, pct: self.mgr.update_ui(txt, progress_pct=pct * 100),
            )
            if ok:
                self.mgr.update_ui(f"🎉 [{f.filename}] 下载并导入成功！", progress_pct=100, is_success=True)
                self.mgr.emit_event({"event": "download_complete", "filename": f.filename, "file_path": str((self.mgr.download_dir / f.filename).resolve())})
                return
        self.mgr._exec_js_ui(build_site_download_js(self.mgr.active_site))

    def _run_site_dom_download(self, current_url: str) -> None:
        site: ModSiteSpec = self.mgr.active_site
        self.mgr.update_ui(f"🔍 正在分析【{site.short_name}】当前页面下载入口...", progress_pct=0)
        task = self.mgr.webview.CoreWebView2.ExecuteScriptAsync(build_site_download_js(site))

        def on_done(t):
            res = str(t.Result or "").strip('"')
            if "NEED_LOGIN" in res:
                self.mgr._pending_mod_url = current_url or site.home_url
                self.mgr.update_ui(f"🔑 {site.short_name} 需先登录才可下载，已跳转登录页！完成后点击【↩ 返回模组页】。", is_error=True)
                self.mgr._run_on_ui(lambda: self.mgr.browser_view.load_url(site.login_url))
            elif res.startswith("resolved_external_url:"):
                ext = res.split("resolved_external_url:", 1)[1]
                self.mgr.update_ui(f"🔗 已自动解析外链/Base64 下载地址，正在跳转: {ext}")
                self.mgr._run_on_ui(lambda: self.mgr.browser_view.load_url(ext))
            elif "no_download_button_found" in res:
                self.mgr.update_ui("⚠ 未找到下载按钮，请先进入具体模组详情页或先登录。", is_error=True)

        task.ContinueWith(self.system_mod.Action[self.system_mod.Threading.Tasks.Task[str]](on_done))


def start_ipc_threads(mgr: Any) -> None:
    """Starts parent watchdog and stdin command listener threads for embedded browser subprocess."""
    def _watchdog() -> None:
        while True:
            time.sleep(2)
            try:
                os.kill(mgr.parent_pid, 0)
            except OSError:
                sys.exit(0)

    def _stdin_loop() -> None:
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                data = json.loads(line.strip())
                action = data.get("action")
                if action == "import_result":
                    ok = data.get("success", False)
                    name = Path(data.get("file_path", "")).stem or "模组"
                    msg = data.get("message", "")
                    text = f"🎉 [{name}] 已自动导入至模组管理！" if ok else f"⚠ [{name}] 导入提示: {msg}"
                    mgr.update_ui(status_text=text, is_success=ok, is_error=not ok)
                elif action == "navigate" and data.get("url") and mgr.browser_view:
                    mgr._pending_mod_url = data.get("pending_url") or mgr._pending_mod_url
                    mgr.browser_view.load_url(data["url"])
            except (json.JSONDecodeError, ValueError):
                continue
            except Exception:
                break

    if mgr.parent_pid > 0:
        threading.Thread(target=_watchdog, daemon=True, name="ParentWatchdog").start()
    threading.Thread(target=_stdin_loop, daemon=True, name="StdinListener").start()
