import os
import sys
import json
import time
import argparse
import logging
import threading
from pathlib import Path

# ─── sys.path bootstrap so that 'core' imports work when running as a subprocess
_this_dir = Path(__file__).resolve().parent  # gui/windows/
_xxmi_root = _this_dir.parent.parent         # src/xxmi_launcher/
if str(_xxmi_root) not in sys.path:
    sys.path.insert(0, str(_xxmi_root))

# Configure logging for standalone or subprocess mode
log = logging.getLogger("GameBananaBrowser")
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)

try:
    import webview
    import webview.platforms.winforms as wf
    import webview.platforms.edgechromium as edge
    import clr
    clr.AddReference('System.Windows.Forms')
    clr.AddReference('System.Drawing')
    clr.AddReference(edge.interop_dll_path('Microsoft.Web.WebView2.Core.dll'))

    import System.Windows.Forms as WinForms
    from System import Action, Func, Type, Object
    from System.Drawing import Size, Color, Font, FontFamily, FontStyle, Point
    from Microsoft.Web.WebView2.Core import (
        CoreWebView2DownloadState,
        CoreWebView2DownloadStartingEventArgs,
        CoreWebView2DownloadOperation
    )
except Exception as e:
    log.exception(f"Failed to initialize WinForms/WebView2 dependencies: {e}")
    raise

GAMEBANANA_WUWA_URL = "https://gamebanana.com/games/20357"
GAMEBANANA_LOGIN_URL = "https://gamebanana.com/login"

# ─── UI Layout constants
_NAV_HEIGHT = 46       # top navigation bar height
_STATUS_HEIGHT = 34    # bottom status bar height


def sanitize_filename(name: str) -> str:
    """Sanitizes filename for Windows filesystem."""
    invalid_chars = '<>:"/\\|?*\0'
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    return name.strip() or f"mod_{int(time.time())}.zip"


class GameBananaBrowserManager:
    def __init__(self, mods_dir: Path, download_dir: Path, cache_dir: Path, parent_pid: int = 0, initial_url: str = GAMEBANANA_WUWA_URL):
        self.mods_dir = Path(mods_dir)
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.parent_pid = parent_pid
        self.home_url = initial_url or GAMEBANANA_WUWA_URL

        self.form: WinForms.Form = None
        self.browser_view = None
        self.webview = None          # WebView2 control
        self.window = None           # pywebview Window

        self.lbl_status: WinForms.Label = None
        self.progress_bar: WinForms.ProgressBar = None
        self.txt_url: WinForms.TextBox = None
        self._active_download_count = 0

        # Watch parent PID if provided — exit when parent dies
        if self.parent_pid > 0:
            threading.Thread(target=self._parent_watchdog, daemon=True, name="ParentWatchdog").start()

        # Listen for messages (import results) from parent process via stdin
        threading.Thread(target=self._stdin_listener, daemon=True, name="StdinListener").start()

    # ───────────────────────── Parent watchdog ──────────────────────────────
    def _parent_watchdog(self):
        """Terminates this process when the parent launcher process exits."""
        try:
            import psutil
            while True:
                time.sleep(2)
                try:
                    proc = psutil.Process(self.parent_pid)
                    if not proc.is_running():
                        sys.exit(0)
                except psutil.NoSuchProcess:
                    sys.exit(0)
        except ImportError:
            # psutil not available — fallback: poll via os.kill(pid, 0)
            while True:
                time.sleep(2)
                try:
                    os.kill(self.parent_pid, 0)
                except OSError:
                    sys.exit(0)

    # ────────────────────────── IPC (stdin/stdout) ──────────────────────────
    def _stdin_listener(self):
        """Reads launcher commands from stdin (JSON-Lines protocol)."""
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                data = json.loads(line.strip())
                action = data.get("action")
                if action == "import_result":
                    success = data.get("success", False)
                    file_path = data.get("file_path", "")
                    name = Path(file_path).stem if file_path else "模组"
                    msg = data.get("message", "")
                    if success:
                        self.update_ui(
                            status_text=f"🎉 [{name}] 已成功自动导入至模组管理，在列表中已就绪！",
                            is_success=True
                        )
                    else:
                        self.update_ui(
                            status_text=f"⚠ [{name}] 导入提示: {msg}",
                            is_error=True
                        )
                elif action == "navigate":
                    url = data.get("url")
                    if url and self.browser_view:
                        self.browser_view.load_url(url)
            except (json.JSONDecodeError, ValueError):
                continue
            except Exception:
                break

    def emit_event(self, event_data: dict):
        """Sends a JSON-Lines event to parent process via stdout."""
        try:
            sys.stdout.write(json.dumps(event_data, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except Exception:
            pass

    # ───────────────────────── WinForms UI Setup ────────────────────────────
    def setup_form_ui(self, form: WinForms.Form, browser_view):
        """Called after BrowserForm.__init__ to inject the navigation bar and status bar."""
        self.form = form
        self.browser_view = browser_view
        self.webview = browser_view.webview

        form.BackColor = Color.FromArgb(18, 22, 34)
        form.Text = "GameBanana 模组下载中心 - XXMI Launcher"
        form.Resize += self._on_form_resize

        # ── 1. Top Navigation Bar ──────────────────────────────────────────
        top_panel = WinForms.Panel()
        top_panel.Dock = WinForms.DockStyle.Top
        top_panel.Height = _NAV_HEIGHT
        top_panel.BackColor = Color.FromArgb(24, 30, 48)

        x = 6

        def _nav_btn(text, w, color, click_fn, bold=False):
            nonlocal x
            btn = WinForms.Button()
            btn.Text = text
            btn.Size = Size(w, 30)
            btn.Location = Point(x, 8)
            btn.FlatStyle = WinForms.FlatStyle.Flat
            btn.FlatAppearance.BorderSize = 0
            btn.BackColor = color
            btn.ForeColor = Color.White
            btn.Font = Font("Microsoft YaHei", 9, FontStyle.Bold if bold else FontStyle.Regular)
            btn.Click += lambda s, e: click_fn()
            top_panel.Controls.Add(btn)
            x += w + 4
            return btn

        def _go_back():
            try:
                if self.webview.CanGoBack:
                    self.webview.GoBack()
            except Exception:
                pass

        def _go_fwd():
            try:
                if self.webview.CanGoForward:
                    self.webview.GoForward()
            except Exception:
                pass

        _nav_btn("◀", 30, Color.FromArgb(38, 48, 70), _go_back)
        _nav_btn("▶", 30, Color.FromArgb(38, 48, 70), _go_fwd)
        _nav_btn("🔄", 30, Color.FromArgb(38, 48, 70), lambda: self.webview.Reload())
        x += 4  # small gap
        _nav_btn("🏠 游戏专区", 90, Color.FromArgb(234, 88, 12),
                 lambda: self.browser_view.load_url(self.home_url), bold=True)
        _nav_btn("🔑 网页登录", 84, Color.FromArgb(37, 99, 235),
                 lambda: self.browser_view.load_url(GAMEBANANA_LOGIN_URL))
        _nav_btn("⚙ 账号助手", 84, Color.FromArgb(79, 70, 229),
                 lambda: self._open_account_helper())
        _nav_btn("📂 下载目录", 84, Color.FromArgb(51, 65, 85),
                 lambda: os.startfile(str(self.download_dir)))
        x += 4

        # Address Bar — anchored right for resize
        self.txt_url = WinForms.TextBox()
        self.txt_url.Location = Point(x, 10)
        self.txt_url.Size = Size(form.Width - x - 70, 26)
        self.txt_url.BackColor = Color.FromArgb(13, 18, 28)
        self.txt_url.ForeColor = Color.FromArgb(226, 232, 240)
        self.txt_url.Font = Font("Segoe UI", 9)
        self.txt_url.BorderStyle = WinForms.BorderStyle.FixedSingle
        self.txt_url.Anchor = (WinForms.AnchorStyles.Top | WinForms.AnchorStyles.Left |
                               WinForms.AnchorStyles.Right)
        self.txt_url.KeyDown += self._on_url_keydown
        top_panel.Controls.Add(self.txt_url)
        self._url_bar_left = x

        # Go Button — anchored right
        btn_go = WinForms.Button()
        btn_go.Text = "前往"
        btn_go.Size = Size(54, 28)
        btn_go.Location = Point(form.Width - 62, 9)
        btn_go.Anchor = WinForms.AnchorStyles.Top | WinForms.AnchorStyles.Right
        btn_go.FlatStyle = WinForms.FlatStyle.Flat
        btn_go.FlatAppearance.BorderSize = 0
        btn_go.BackColor = Color.FromArgb(37, 99, 235)
        btn_go.ForeColor = Color.White
        btn_go.Font = Font("Microsoft YaHei", 9)
        btn_go.Click += lambda s, e: self._navigate_to_input()
        top_panel.Controls.Add(btn_go)

        form.Controls.Add(top_panel)
        top_panel.BringToFront()

        # ── 2. Bottom Status Bar ──────────────────────────────────────────
        bottom_panel = WinForms.Panel()
        bottom_panel.Dock = WinForms.DockStyle.Bottom
        bottom_panel.Height = _STATUS_HEIGHT
        bottom_panel.BackColor = Color.FromArgb(15, 18, 28)

        self.lbl_status = WinForms.Label()
        self.lbl_status.Text = "💡 在网站点击模组的【Manual Download / 下载】按钮将自动下载并保存至模组管理！"
        self.lbl_status.ForeColor = Color.FromArgb(100, 116, 139)
        self.lbl_status.Font = Font("Microsoft YaHei", 9)
        self.lbl_status.Location = Point(10, 8)
        self.lbl_status.AutoSize = True
        bottom_panel.Controls.Add(self.lbl_status)

        self.progress_bar = WinForms.ProgressBar()
        self.progress_bar.Size = Size(200, 16)
        self.progress_bar.Location = Point(form.Width - 218, 9)
        self.progress_bar.Anchor = WinForms.AnchorStyles.Top | WinForms.AnchorStyles.Right
        self.progress_bar.Visible = False
        self.progress_bar.ForeColor = Color.FromArgb(56, 189, 248)
        bottom_panel.Controls.Add(self.progress_bar)

        form.Controls.Add(bottom_panel)
        bottom_panel.BringToFront()

        # Ensure the WebView2 control fills the remaining space
        self.webview.Dock = WinForms.DockStyle.Fill
        self.webview.SendToBack()

        # ── 3. Event Hooks ────────────────────────────────────────────────
        self.webview.SourceChanged += self._on_source_changed

    def _on_form_resize(self, sender, args):
        """Keep address bar width in sync when window is resized."""
        try:
            if self.txt_url and self.form:
                new_w = self.form.Width - self._url_bar_left - 70
                if new_w > 50:
                    self.txt_url.Width = new_w
        except Exception:
            pass

    def _on_source_changed(self, sender, args):
        """Update address bar URL when WebView2 navigates."""
        try:
            curr_url = str(sender.Source)
            if self.txt_url:
                def _set():
                    self.txt_url.Text = curr_url
                if self.form and self.form.InvokeRequired:
                    self.form.BeginInvoke(Action(_set))
                else:
                    _set()
        except Exception:
            pass

    def _on_url_keydown(self, sender, args):
        if args.KeyCode == WinForms.Keys.Enter:
            self._navigate_to_input()
            args.SuppressKeyPress = True

    def _navigate_to_input(self):
        url = self.txt_url.Text.strip() if self.txt_url else ""
        if not url:
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        self.browser_view.load_url(url)

    # ────────────────────── Account Helper Dialog ───────────────────────────
    def _open_account_helper(self):
        """Shows the account credential assistant dialog."""
        dlg = WinForms.Form()
        dlg.Text = "GameBanana 账号助手"
        dlg.Size = Size(490, 330)
        dlg.StartPosition = WinForms.FormStartPosition.CenterParent
        dlg.FormBorderStyle = WinForms.FormBorderStyle.FixedDialog
        dlg.MaximizeBox = False
        dlg.MinimizeBox = False
        dlg.BackColor = Color.FromArgb(24, 30, 46)
        dlg.ForeColor = Color.White

        lbl_info = WinForms.Label()
        lbl_info.Text = (
            "💡 提示：账号登录状态（Cookie）会自动持久化保存，关闭后再次打开无需重新登录。\n"
            "您可直接在网页中登录，或用下方快捷助手自动填入账号信息。"
        )
        lbl_info.Font = Font("Microsoft YaHei", 9)
        lbl_info.ForeColor = Color.FromArgb(203, 213, 225)
        lbl_info.Location = Point(18, 16)
        lbl_info.Size = Size(444, 50)
        dlg.Controls.Add(lbl_info)

        def _add_row(label_text, row_y, is_password=False):
            lbl = WinForms.Label()
            lbl.Text = label_text
            lbl.Font = Font("Microsoft YaHei", 9)
            lbl.Location = Point(18, row_y + 2)
            lbl.AutoSize = True
            dlg.Controls.Add(lbl)
            txt = WinForms.TextBox()
            txt.Location = Point(145, row_y)
            txt.Size = Size(300, 24)
            txt.BackColor = Color.FromArgb(13, 18, 30)
            txt.ForeColor = Color.White
            txt.Font = Font("Segoe UI", 9)
            txt.BorderStyle = WinForms.BorderStyle.FixedSingle
            if is_password:
                txt.PasswordChar = '●'
            dlg.Controls.Add(txt)
            return txt

        txt_user = _add_row("用户名 / 邮箱：", 80)
        txt_pwd  = _add_row("密码：", 116, is_password=True)

        # ── Autofill & Navigate Button
        btn_fill = WinForms.Button()
        btn_fill.Text = "🚀 填入并跳转登录"
        btn_fill.Size = Size(148, 32)
        btn_fill.Location = Point(145, 166)
        btn_fill.FlatStyle = WinForms.FlatStyle.Flat
        btn_fill.FlatAppearance.BorderSize = 0
        btn_fill.BackColor = Color.FromArgb(37, 99, 235)
        btn_fill.ForeColor = Color.White
        btn_fill.Font = Font("Microsoft YaHei", 9, FontStyle.Bold)

        def do_fill(s, e):
            u = txt_user.Text.strip()
            p = txt_pwd.Text.strip()
            dlg.Close()
            self.browser_view.load_url(GAMEBANANA_LOGIN_URL)
            if u or p:
                def _inject_js():
                    time.sleep(2.2)
                    try:
                        js = f"""(function(){{
                            var u=document.querySelector('input[name="username"],input[name="userid"],input[autocomplete="username"],input[type="email"]');
                            var p=document.querySelector('input[type="password"]');
                            if(u){{u.value={json.dumps(u)};u.dispatchEvent(new Event('input',{{bubbles:true}}));}}
                            if(p){{p.value={json.dumps(p)};p.dispatchEvent(new Event('input',{{bubbles:true}}));}}
                        }})();"""
                        self.webview.CoreWebView2.ExecuteScriptAsync(js)
                    except Exception:
                        pass
                threading.Thread(target=_inject_js, daemon=True).start()

        btn_fill.Click += do_fill
        dlg.Controls.Add(btn_fill)

        # ── Clear Cookies Button
        btn_clear = WinForms.Button()
        btn_clear.Text = "🧹 清除登录缓存"
        btn_clear.Size = Size(130, 32)
        btn_clear.Location = Point(302, 166)
        btn_clear.FlatStyle = WinForms.FlatStyle.Flat
        btn_clear.FlatAppearance.BorderSize = 0
        btn_clear.BackColor = Color.FromArgb(71, 85, 105)
        btn_clear.ForeColor = Color.White
        btn_clear.Font = Font("Microsoft YaHei", 9)

        def do_clear(s, e):
            try:
                self.webview.CoreWebView2.CookieManager.DeleteAllCookies()
                WinForms.MessageBox.Show(
                    dlg,
                    "已清除所有 Cookie 与登录状态，下次访问需重新登录。",
                    "提示",
                    WinForms.MessageBoxButtons.OK,
                    WinForms.MessageBoxIcon.Information
                )
                self.browser_view.load_url(GAMEBANANA_WUWA_URL)
                dlg.Close()
            except Exception as ex:
                WinForms.MessageBox.Show(
                    dlg, f"清除失败: {ex}", "错误",
                    WinForms.MessageBoxButtons.OK,
                    WinForms.MessageBoxIcon.Error
                )

        btn_clear.Click += do_clear
        dlg.Controls.Add(btn_clear)

        # ── Tip label
        lbl_tip = WinForms.Label()
        lbl_tip.Text = "⚠ 安全提示：密码仅用于自动填充，不会被上传或记录。"
        lbl_tip.ForeColor = Color.FromArgb(100, 116, 139)
        lbl_tip.Font = Font("Microsoft YaHei", 8)
        lbl_tip.Location = Point(18, 215)
        lbl_tip.Size = Size(440, 20)
        dlg.Controls.Add(lbl_tip)

        dlg.ShowDialog(self.form)

    # ──────────────────────── Thread-safe UI Updates ─────────────────────────
    def update_ui(self, status_text: str = None, progress_pct: float = None,
                  is_error: bool = False, is_success: bool = False):
        """Updates status bar label and progress bar from any thread."""
        if not self.form or not self.lbl_status:
            return

        def _do():
            try:
                if status_text is not None:
                    self.lbl_status.Text = status_text
                    if is_error:
                        self.lbl_status.ForeColor = Color.FromArgb(248, 113, 113)
                    elif is_success:
                        self.lbl_status.ForeColor = Color.FromArgb(74, 222, 128)
                    else:
                        self.lbl_status.ForeColor = Color.FromArgb(56, 189, 248)

                if progress_pct is not None:
                    self.progress_bar.Visible = True
                    self.progress_bar.Value = max(0, min(100, int(progress_pct)))
                elif not self._active_download_count:
                    self.progress_bar.Visible = False
            except Exception:
                pass

        if self.form.InvokeRequired:
            self.form.BeginInvoke(Action(_do))
        else:
            _do()

    # ─────────────────────── Download Interception ───────────────────────────
    def handle_download_starting(self, sender, args):
        """
        Intercepts every CoreWebView2 DownloadStarting event:
        - Redirects saved file path to our download_dir.
        - Suppresses the system Save As dialog.
        - Hooks progress and state-change callbacks.
        - Emits JSON-Lines events to the parent launcher process.
        """
        download_op: CoreWebView2DownloadOperation = args.DownloadOperation
        raw_name = os.path.basename(args.ResultFilePath) or "mod.zip"
        clean_name = sanitize_filename(raw_name)

        # Unique destination path
        target_path = self.download_dir / clean_name
        stem, suffix = target_path.stem, target_path.suffix
        idx = 1
        while target_path.exists():
            target_path = self.download_dir / f"{stem} ({idx}){suffix}"
            idx += 1

        args.ResultFilePath = str(target_path)
        args.Handled = True           # suppress SaveFileDialog

        self._active_download_count += 1
        self.update_ui(f"⬇ 准备下载: {clean_name}...", progress_pct=0)
        self.emit_event({
            "event": "download_start",
            "filename": clean_name,
            "target_path": str(target_path),
            "uri": str(download_op.Uri)
        })

        def on_bytes_received(sender_op, event_args):
            try:
                rec = sender_op.BytesReceived
                tot = sender_op.TotalBytesToReceive
                pct = (rec / tot * 100.0) if tot > 0 else 0
                mb_r = rec / (1024 * 1024)
                mb_t = tot / (1024 * 1024)
                txt = f"⬇ {clean_name}  {mb_r:.1f} / {mb_t:.1f} MB  ({pct:.0f}%)"
                self.update_ui(txt, progress_pct=pct)
            except Exception:
                pass

        def on_state_changed(sender_op, event_args):
            try:
                state = sender_op.State
                if state == CoreWebView2DownloadState.Completed:
                    self._active_download_count = max(0, self._active_download_count - 1)
                    self.update_ui(
                        f"⏳ [{clean_name}] 下载完成，正在导入至模组管理...",
                        progress_pct=100
                    )
                    self.emit_event({
                        "event": "download_complete",
                        "filename": clean_name,
                        "file_path": str(target_path)
                    })
                    # When running WITHOUT a parent launcher (standalone mode):
                    if self.parent_pid <= 0:
                        threading.Thread(
                            target=self._standalone_import,
                            args=(target_path,),
                            daemon=True
                        ).start()

                elif state == CoreWebView2DownloadState.Interrupted:
                    self._active_download_count = max(0, self._active_download_count - 1)
                    reason = str(sender_op.InterruptReason)
                    self.update_ui(f"❌ 下载中断: {clean_name} ({reason})", is_error=True)
                    self.emit_event({
                        "event": "download_interrupted",
                        "filename": clean_name,
                        "reason": reason
                    })
            except Exception as ex:
                log.exception(f"on_state_changed error: {ex}")

        download_op.BytesReceivedChanged += on_bytes_received
        download_op.StateChanged += on_state_changed

    def _standalone_import(self, file_path: Path):
        """
        Imports the downloaded mod directly (standalone mode — no parent launcher).
        Requires Paths to be initialized first; if not, shows a file manager fallback.
        """
        try:
            import core.path_manager as _Paths
            import core.config_manager  # triggers Config init side-effects
            from core.mod_service import ModService
            success, msg = ModService.import_mod_from_path(file_path)
            if success:
                self.update_ui(
                    f"🎉 [{file_path.stem}] 导入成功！",
                    is_success=True
                )
            else:
                self.update_ui(f"⚠ 导入提示: {msg}", is_error=True)
        except Exception as e:
            # Fallback: open download folder so user can import manually
            self.update_ui(
                f"⚠ 自动导入不可用（需要在启动器中使用），文件已保存至: {file_path.parent}",
                is_error=False
            )
            try:
                os.startfile(str(file_path.parent))
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════════════════════════
def run_gamebanana_browser(
    mods_dir: Path = None,
    download_dir: Path = None,
    cache_dir: Path = None,
    parent_pid: int = 0,
    initial_url: str = GAMEBANANA_WUWA_URL
):
    """
    Entry point for the GameBanana Mod Browser window.

    Called either:
    - Directly by the launcher main process (via _open_gamebanana_browser subprocess spawn).
    - From app.py with --gamebanana-browser CLI flag (for frozen/Pyinstaller builds).
    - Standalone via: python gamebanana_browser.py [--mods-dir ...] [--download-dir ...]
    """
    parser = argparse.ArgumentParser(description="GameBanana Mod Browser for XXMI Launcher")
    parser.add_argument("--mods-dir",       type=str, default=str(mods_dir or ""))
    parser.add_argument("--download-dir",   type=str, default=str(download_dir or ""))
    parser.add_argument("--cache-dir",      type=str, default=str(cache_dir or ""))
    parser.add_argument("--initial-url",    type=str, default=str(initial_url or GAMEBANANA_WUWA_URL))
    parser.add_argument("--parent-pid",     type=int, default=parent_pid)
    parser.add_argument("--gamebanana-browser", action="store_true")  # consumed by app.py
    args, _unknown = parser.parse_known_args()

    m_dir = Path(args.mods_dir)    if args.mods_dir    else Path.cwd() / "Mods"
    d_dir = Path(args.download_dir) if args.download_dir else Path.cwd() / "Downloads"
    c_dir = Path(args.cache_dir)   if args.cache_dir   else Path.cwd() / "UserData" / "GameBananaBrowser"
    init_url = args.initial_url if args.initial_url else GAMEBANANA_WUWA_URL
    p_pid = args.parent_pid

    manager = GameBananaBrowserManager(
        mods_dir=m_dir,
        download_dir=d_dir,
        cache_dir=c_dir,
        parent_pid=p_pid,
        initial_url=init_url
    )

    # ── Patch 1: Intercept all downloads ──────────────────────────────────
    _orig_download = edge.EdgeChrome.on_download_starting

    def _patched_download(self, sender, event_args):
        try:
            manager.handle_download_starting(sender, event_args)
        except Exception as ex:
            log.exception(f"Download handler exception: {ex}")
            _orig_download(self, sender, event_args)

    edge.EdgeChrome.on_download_starting = _patched_download

    # ── Patch 2: Keep all navigation inside the WebView (no external browser) ─
    def _patched_new_window(self, sender, event_args):
        try:
            event_args.set_Handled(True)
            uri = str(event_args.get_Uri())
            self.load_url(uri)
        except Exception:
            pass

    edge.EdgeChrome.on_new_window_request = _patched_new_window

    # ── Patch 3: Inject navigation toolbar + status bar into BrowserForm ─────
    _orig_form_init = wf.BrowserView.BrowserForm.__init__

    def _patched_form_init(self, window, storage_path):
        _orig_form_init(self, window, storage_path)
        try:
            manager.setup_form_ui(self, self.browser)
        except Exception as ex:
            log.exception(f"Form UI setup failed: {ex}")

    wf.BrowserView.BrowserForm.__init__ = _patched_form_init

    # ── Configure & start WebView2 ────────────────────────────────────────
    webview.settings['ALLOW_DOWNLOADS'] = True
    webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False

    window = webview.create_window(
        title="GameBanana 模组下载中心 - XXMI Launcher",
        url=init_url,
        width=1280,
        height=860,
        min_size=(960, 620),
        resizable=True
    )
    manager.window = window

    # Signal readiness BEFORE blocking webview.start()
    manager.emit_event({"event": "ready"})

    webview.start(
        private_mode=False,
        storage_path=str(c_dir)
    )


if __name__ == "__main__":
    run_gamebanana_browser()
