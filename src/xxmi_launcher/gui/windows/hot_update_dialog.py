"""
@file: src/xxmi_launcher/gui/windows/hot_update_dialog.py
@brief: Modern dark-themed dialog for hot updates, WWMI-Package imports, and rule synchronization.
@exports: HotUpdateDialog
"""
import datetime
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog
from typing import Optional
import customtkinter as ctk

from core.hot_update_service import HotUpdateService, HotUpdateStatus


class HotUpdateDialog(ctk.CTkToplevel):
    """Interactive dialog for hot updates, WWMI-Package importing, and rule syncing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.title("⚡ 软件热更新与规则同步中心 - XMMI-Pro")
        self.geometry("680x580")
        self.resizable(False, False)
        self.configure(fg_color="#131620")

        self._is_busy = False
        self._init_window()
        self._build_ui()
        self._refresh_status()

    def _init_window(self) -> None:
        if self.parent_window is not None:
            try:
                self.transient(self.parent_window)
                self.grab_set()
            except Exception:
                pass
        self._center_window()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_window(self) -> None:
        self.update_idletasks()
        try:
            if self.parent_window:
                px = self.parent_window.winfo_rootx()
                py = self.parent_window.winfo_rooty()
                pw = self.parent_window.winfo_width()
                ph = self.parent_window.winfo_height()
                x = px + (pw - 680) // 2
                y = py + (ph - 580) // 2
            else:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = (sw - 680) // 2
                y = (sh - 580) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _build_ui(self) -> None:
        # Header
        header = ctk.CTkFrame(self, fg_color="#1a1e2b", corner_radius=8, height=48)
        header.pack(fill="x", padx=16, pady=(14, 8))
        header.pack_propagate(False)
        ctk.CTkLabel(
            header,
            text="⚡ XMMI-Pro 软件热更新与规则同步中心",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#60a5fa"
        ).pack(side="left", padx=14)

        # Cards container
        self.cards_frame = ctk.CTkFrame(self, fg_color="#161922", corner_radius=8)
        self.cards_frame.pack(fill="x", padx=16, pady=4)
        self._build_cards()

        # Action bar
        act_frame = ctk.CTkFrame(self, fg_color="transparent")
        act_frame.pack(fill="x", padx=16, pady=(8, 4))
        self.sync_all_btn = ctk.CTkButton(
            act_frame,
            text="🚀 一键全量热更新 (规则 + WWMI-Package)",
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=32,
            font=ctk.CTkFont(weight="bold"),
            command=self._on_sync_all
        )
        self.sync_all_btn.pack(side="left", fill="x", expand=True)

        self.progress_bar = ctk.CTkProgressBar(self, height=6, fg_color="#1e2230", progress_color="#3b82f6")
        self.progress_bar.pack(fill="x", padx=16, pady=6)
        self.progress_bar.set(0.0)

        # Log frame
        log_frame = ctk.CTkFrame(self, fg_color="#10121a", corner_radius=8)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(2, 12))
        self.log_text = tk.Text(
            log_frame,
            bg="#10121a",
            fg="#d1d5db",
            insertbackground="#60a5fa",
            relief="flat",
            wrap="word",
            font=("Consolas", 10)
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        self._append_log("软件热更新中心已就绪，可随时同步规则库或导入 WWMI-Package。")

    def _build_cards(self) -> None:
        # Wuwa Card
        r1 = ctk.CTkFrame(self.cards_frame, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=6)
        self.wuwa_label = ctk.CTkLabel(r1, text="🔧 鸣潮修复规则: 加载中...", font=ctk.CTkFont(size=12))
        self.wuwa_label.pack(side="left")
        self.wuwa_btn = ctk.CTkButton(
            r1, text="⚡ 同步规则", width=90, height=26, fg_color="#059669",
            hover_color="#047857", command=self._on_sync_wuwa
        )
        self.wuwa_btn.pack(side="right")

        # WWMI Card
        r2 = ctk.CTkFrame(self.cards_frame, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=6)
        self.wwmi_label = ctk.CTkLabel(r2, text="📦 WWMI 运行包: 加载中...", font=ctk.CTkFont(size=12))
        self.wwmi_label.pack(side="left")

        self.wwmi_local_btn = ctk.CTkButton(
            r2, text="📂 本地导入", width=90, height=26, fg_color="#475569",
            hover_color="#334155", command=self._on_import_wwmi_local
        )
        self.wwmi_local_btn.pack(side="right", padx=(6, 0))

        self.wwmi_online_btn = ctk.CTkButton(
            r2, text="🌐 云端导入", width=90, height=26, fg_color="#d97706",
            hover_color="#b45309", command=self._on_sync_wwmi_online
        )
        self.wwmi_online_btn.pack(side="right")

        # Launcher Card
        r3 = ctk.CTkFrame(self.cards_frame, fg_color="transparent")
        r3.pack(fill="x", padx=12, pady=6)
        self.launcher_label = ctk.CTkLabel(r3, text="🚀 启动器上游: v2.4.9 (已整合最新提交)", font=ctk.CTkFont(size=12))
        self.launcher_label.pack(side="left")
        self.launcher_btn = ctk.CTkButton(
            r3, text="🔍 检测更新", width=90, height=26, fg_color="#6366f1",
            hover_color="#4f46e5", command=self._on_check_launcher
        )
        self.launcher_btn.pack(side="right")

    def _append_log(self, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")

    def _refresh_status(self) -> None:
        st = HotUpdateService.get_status()
        self.wuwa_label.configure(
            text=f"🔧 鸣潮修复规则: v{st.wuwa_version} (收录 {st.wuwa_character_count} 个角色与武器规则)"
        )
        wwmi_desc = f"v{st.wwmi_version}" if st.wwmi_installed else "未安装 / 需导入"
        self.wwmi_label.configure(
            text=f"📦 WWMI 运行包: {wwmi_desc} (用于鸣潮 3D Migoto 模组加载)"
        )
        self.launcher_label.configure(
            text=f"🚀 启动器核心: {st.upstream_launcher_version} (已同步 upstream 补丁)"
        )

    def _run_async(self, target, *args) -> None:
        if self._is_busy:
            self._append_log("⚠️ 任务正在执行中，请稍候...")
            return
        self._is_busy = True
        self.sync_all_btn.configure(state="disabled")

        def _worker():
            try:
                target(*args)
            finally:
                self.after(0, self._on_task_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_task_done(self) -> None:
        self._is_busy = False
        self.sync_all_btn.configure(state="normal")
        self.progress_bar.set(0.0)
        self._refresh_status()

    def _on_sync_wuwa(self) -> None:
        self._run_async(
            lambda: HotUpdateService.sync_wuwa_rules(
                force=True,
                log_cb=lambda m: self.after(0, self._append_log, m)
            )
        )

    def _on_sync_wwmi_online(self) -> None:
        def _task():
            HotUpdateService.sync_wwmi_package_online(
                log_cb=lambda m: self.after(0, self._append_log, m),
                progress_cb=lambda p: self.after(0, self.progress_bar.set, p)
            )
        self._run_async(_task)

    def _on_import_wwmi_local(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 WWMI-Package 压缩包 (.zip) 或取消以选择目录",
            filetypes=[("WWMI Package Zip", "*.zip"), ("All Files", "*.*")]
        )
        selected_path = Path(path) if path else None
        if not selected_path:
            dir_path = filedialog.askdirectory(title="选择已解压的 WWMI-Package 目录")
            if dir_path:
                selected_path = Path(dir_path)

        if not selected_path or not selected_path.exists():
            return

        self._run_async(
            lambda: HotUpdateService.import_local_wwmi_package(
                selected_path,
                log_cb=lambda m: self.after(0, self._append_log, m)
            )
        )

    def _on_check_launcher(self) -> None:
        self._run_async(
            lambda: HotUpdateService.check_upstream_launcher(
                log_cb=lambda m: self.after(0, self._append_log, m)
            )
        )

    def _on_sync_all(self) -> None:
        def _task():
            HotUpdateService.sync_all(
                log_cb=lambda m: self.after(0, self._append_log, m),
                progress_cb=lambda p: self.after(0, self.progress_bar.set, p)
            )
        self._run_async(_task)

    def _on_close(self) -> None:
        if self._is_busy:
            self._append_log("⚠️ 任务仍在后台运行，窗口已最小化关闭")
        self.destroy()
