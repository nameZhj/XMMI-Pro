"""
@file gamebanana_download_dialog.py
@brief Modern dark-themed dialog for GameBanana URL parsing, file selection, and direct installation
@exports GameBananaDownloadDialog
"""
import os
import threading
from pathlib import Path
from typing import Optional, List

from customtkinter import CTkToplevel, CTkFrame, CTkLabel, CTkEntry, CTkButton, CTkProgressBar, CTkOptionMenu

from core.gamebanana_service import GameBananaService, GameBananaModInfo, GameBananaFileInfo
from gui.modern_dialogs import show_warning, show_info


class GameBananaDownloadDialog(CTkToplevel):
    def __init__(self, parent, on_import_success=None, initial_url: str = ""):
        super().__init__(parent)
        self.title("🍌 GameBanana 模组在线解析与下载")
        self.geometry("640x460")
        self.resizable(False, False)
        self.configure(fg_color="#0f172a")

        self.on_import_success = on_import_success
        self.mod_info: Optional[GameBananaModInfo] = None
        self.cancel_download = False
        self.is_downloading = False

        self.transient(parent)
        self.grab_set()

        self._build_ui()

        if initial_url:
            self.entry_url.insert(0, initial_url)
            self.after(200, self._start_parse)
        else:
            self._try_auto_paste()

    def _build_ui(self):
        # 1. Header
        header = CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 10))

        CTkLabel(
            header,
            text="🍌 GameBanana 模组解析与一键下载",
            font=("Microsoft YaHei", 18, "bold"),
            text_color="#f8fafc"
        ).pack(anchor="w")

        CTkLabel(
            header,
            text="支持粘贴 Mod 详情页、下载页链接或数字 ID，自动高速下载、解压并就绪！",
            font=("Microsoft YaHei", 11),
            text_color="#94a3b8"
        ).pack(anchor="w", pady=(4, 0))

        # 2. Input Bar
        input_frame = CTkFrame(self, fg_color="#1e293b", corner_radius=10)
        input_frame.pack(fill="x", padx=20, pady=8)

        self.entry_url = CTkEntry(
            input_frame,
            placeholder_text="https://gamebanana.com/mods/530000 或输入模组 ID",
            font=("Consolas", 12),
            fg_color="#0f172a",
            border_color="#334155",
            text_color="#f8fafc",
            height=36
        )
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=10)

        CTkButton(
            input_frame,
            text="📋 粘贴",
            width=64,
            height=36,
            fg_color="#334155",
            hover_color="#475569",
            font=("Microsoft YaHei", 11),
            command=self._paste_clipboard
        ).pack(side="left", padx=4, pady=10)

        self.btn_parse = CTkButton(
            input_frame,
            text="🔍 解析模组",
            width=96,
            height=36,
            fg_color="#ea580c",
            hover_color="#c2410c",
            font=("Microsoft YaHei", 12, "bold"),
            command=self._start_parse
        )
        self.btn_parse.pack(side="left", padx=(4, 12), pady=10)

        # 3. Parsed Content Card
        self.card_frame = CTkFrame(self, fg_color="#1e293b", corner_radius=10)
        self.card_frame.pack(fill="both", expand=True, padx=20, pady=8)

        self.lbl_mod_title = CTkLabel(
            self.card_frame,
            text="等待解析模组链接...",
            font=("Microsoft YaHei", 14, "bold"),
            text_color="#e2e8f0"
        )
        self.lbl_mod_title.pack(anchor="w", padx=16, pady=(14, 6))

        self.lbl_file_desc = CTkLabel(
            self.card_frame,
            text="请在上方输入链接后点击【解析模组】。",
            font=("Microsoft YaHei", 11),
            text_color="#94a3b8"
        )
        self.lbl_file_desc.pack(anchor="w", padx=16, pady=(0, 10))

        self.file_menu = CTkOptionMenu(
            self.card_frame,
            values=["（未解析到文件）"],
            font=("Microsoft YaHei", 11),
            fg_color="#0f172a",
            button_color="#334155",
            height=34
        )
        self.file_menu.pack(fill="x", padx=16, pady=6)
        self.file_menu.configure(state="disabled")

        # 4. Progress & Actions
        self.lbl_status = CTkLabel(
            self.card_frame,
            text="",
            font=("Microsoft YaHei", 11),
            text_color="#38bdf8"
        )
        self.lbl_status.pack(anchor="w", padx=16, pady=(10, 4))

        self.progress_bar = CTkProgressBar(self.card_frame, height=10, fg_color="#0f172a", progress_color="#22c55e")
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 12))
        self.progress_bar.set(0)

        bottom_bar = CTkFrame(self, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=20, pady=(8, 16))

        self.btn_cancel = CTkButton(
            bottom_bar,
            text="关闭",
            width=90,
            height=36,
            fg_color="#334155",
            hover_color="#475569",
            font=("Microsoft YaHei", 11),
            command=self._on_close
        )
        self.btn_cancel.pack(side="right", padx=(8, 0))

        self.btn_download = CTkButton(
            bottom_bar,
            text="⬇ 立即下载并安装",
            width=160,
            height=36,
            fg_color="#16a34a",
            hover_color="#15803d",
            font=("Microsoft YaHei", 12, "bold"),
            command=self._start_download
        )
        self.btn_download.pack(side="right")
        self.btn_download.configure(state="disabled")

    def _paste_clipboard(self):
        try:
            cb = self.clipboard_get().strip()
            if cb:
                self.entry_url.delete(0, "end")
                self.entry_url.insert(0, cb)
        except Exception:
            pass

    def _try_auto_paste(self):
        try:
            cb = self.clipboard_get().strip()
            if "gamebanana.com" in cb.lower():
                self.entry_url.delete(0, "end")
                self.entry_url.insert(0, cb)
        except Exception:
            pass

    def _start_parse(self):
        raw = self.entry_url.get().strip()
        mod_id = GameBananaService.parse_mod_id(raw)
        if not mod_id:
            show_warning("输入提示", "未识别到有效的 GameBanana Mod ID 或链接！\n格式如：https://gamebanana.com/mods/530000", parent=self)
            return

        self.btn_parse.configure(state="disabled")
        self.lbl_status.configure(text=f"🔍 正在从 GameBanana API 解析 Mod #{mod_id}...")
        self.lbl_mod_title.configure(text=f"Mod #{mod_id} 解析中...")

        def worker():
            info = GameBananaService.fetch_mod_details(mod_id)
            self.after(0, lambda: self._on_parse_done(info, mod_id))

        threading.Thread(target=worker, daemon=True, name="GBParser").start()

    def _on_parse_done(self, info: Optional[GameBananaModInfo], mod_id: str):
        self.btn_parse.configure(state="normal")
        if not info or not info.files:
            self.lbl_mod_title.configure(text=f"❌ 解析失败 (Mod #{mod_id})")
            self.lbl_status.configure(text="未获取到该模组的可下载文件，可能是网络超时或该模组不存在。")
            return

        self.mod_info = info
        self.lbl_mod_title.configure(text=f"📦 {info.name}")
        self.lbl_file_desc.configure(text=f"共包含 {len(info.files)} 个可用文件，请选择要下载的文件：")

        menu_items = [f"{f.filename} ({f.filesize_mb:.1f} MB)" for f in info.files]
        self.file_menu.configure(values=menu_items, state="normal")
        self.file_menu.set(menu_items[0])
        self.btn_download.configure(state="normal")
        self.lbl_status.configure(text=f"✅ 解析成功！点击【立即下载并安装】将自动安装至 Mods 列表。")

    def _start_download(self):
        if not self.mod_info or not self.mod_info.files:
            return

        selected_idx = self.file_menu.cget("values").index(self.file_menu.get()) if self.file_menu.get() in self.file_menu.cget("values") else 0
        file_info = self.mod_info.files[selected_idx]

        self.is_downloading = True
        self.cancel_download = False
        self.btn_download.configure(state="disabled")
        self.btn_parse.configure(state="disabled")
        self.file_menu.configure(state="disabled")
        self.btn_cancel.configure(text="取消下载")

        def on_progress(status_text: str, progress_val: float):
            self.after(0, lambda: self._update_progress(status_text, progress_val))

        def worker():
            ok, msg = GameBananaService.download_and_import(
                download_url=file_info.download_url,
                filename=file_info.filename,
                progress_callback=on_progress,
                cancel_check=lambda: self.cancel_download
            )
            self.after(0, lambda: self._on_download_complete(ok, msg, file_info.filename))

        threading.Thread(target=worker, daemon=True, name="GBDownloader").start()

    def _update_progress(self, text: str, pct: float):
        self.lbl_status.configure(text=text)
        self.progress_bar.set(max(0.0, min(1.0, pct)))

    def _on_download_complete(self, success: bool, msg: str, filename: str):
        self.is_downloading = False
        self.btn_cancel.configure(text="完成并关闭")
        if success:
            self.lbl_status.configure(text=f"🎉 模组【{filename}】下载并安装成功！已在列表显示。")
            self.progress_bar.set(1.0)
            if self.on_import_success:
                self.on_import_success()
        else:
            self.lbl_status.configure(text=f"❌ 安装失败：{msg}")
            self.btn_download.configure(state="normal")

    def _on_close(self):
        if self.is_downloading:
            self.cancel_download = True
        self.destroy()
