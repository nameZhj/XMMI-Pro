"""
@file: src/xxmi_launcher/gui/windows/pre_launch_advisor_dialog.py
@brief: Dark modal pre-launch hardware inspection and Wuthering Waves graphics settings dialog
@exports: PreLaunchAdvisorDialog, show_pre_launch_advisor
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import customtkinter as ctk

from core.utils.wuwa_graphics_advisor import HardwareGraphicsReport, WuwaGraphicsAdvisor
from gui.modern_dialogs import _safe_dispatch


class PreLaunchAdvisorDialog(ctk.CTkToplevel):
    """Modal pre-launch popup displaying detected CPU/GPU and real WuWa in-game settings."""

    def __init__(self, report: HardwareGraphicsReport, game_path: Optional[Path] = None, parent=None) -> None:
        super().__init__(parent)
        self.report = report
        self.game_path = game_path
        self.parent_window = parent
        self.action: str = "cancel"
        self.show_again_var = ctk.BooleanVar(value=WuwaGraphicsAdvisor.should_show_advisor())

        self.title("启动前硬件检测与《鸣潮》图像最佳设置建议")
        self.geometry("740x610")
        self.resizable(False, False)
        self.configure(fg_color="#0f131d")

        self._attach_to_parent(parent)
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _attach_to_parent(self, parent) -> None:
        top = parent
        if parent is not None and hasattr(parent, "winfo_toplevel"):
            try:
                top = parent.winfo_toplevel()
            except Exception:
                top = parent
        if top is not None:
            try:
                self.transient(top)
                self.grab_set()
            except Exception:
                pass
        self.update_idletasks()
        try:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            if top is not None:
                x = top.winfo_rootx() + (top.winfo_width() - 740) // 2
                y = top.winfo_rooty() + (top.winfo_height() - 610) // 2
            else:
                x, y = (sw - 740) // 2, (sh - 610) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _build_ui(self) -> None:
        self._build_header()
        scroll = ctk.CTkScrollableFrame(self, fg_color="#141926", corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=16, pady=(6, 10))
        self._build_section_title(scroll, "🎯 模组正常显示必改设置（游戏内：设置 -> 图像）", "#fbbf24")
        for item in self.report.critical_settings:
            self._build_row(scroll, item, highlight=True)
        self._build_pkg_tip(scroll)
        self._build_section_title(scroll, "🖥️ 基于当前 CPU & GPU 的【设置 -> 图像】流畅高画质建议", "#38bdf8")
        for item in self.report.hardware_settings:
            self._build_row(scroll, item, highlight=False)
        self._build_footer()

    def _build_header(self) -> None:
        card = ctk.CTkFrame(self, fg_color="#1a2133", corner_radius=10, border_width=1, border_color="#2a354d")
        card.pack(fill="x", padx=16, pady=(14, 6))
        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(
            top_row, text="硬件性能评估报告", font=("Microsoft YaHei", 14, "bold"), text_color="#f8fafc"
        ).pack(side="left")
        ctk.CTkLabel(
            top_row,
            text=f" {self.report.tier_label} ",
            font=("Microsoft YaHei", 11, "bold"),
            fg_color="#1d4ed8",
            text_color="#ffffff",
            corner_radius=6,
        ).pack(side="right")

        specs = self.report.specs
        info = (
            f"CPU: {self.report.cpu_name}  ({specs.cpu_cores}核 / {specs.cpu_threads}线程)\n"
            f"GPU: {specs.gpu_name}  |  显存: {self.report.vram_gb} GB  |  系统内存: {self.report.system_ram_gb} GB"
        )
        ctk.CTkLabel(
            card, text=info, font=("Microsoft YaHei", 11), text_color="#cbd5e1", justify="left", anchor="w"
        ).pack(fill="x", padx=14, pady=(0, 10))

    @staticmethod
    def _build_section_title(parent, text: str, color: str) -> None:
        ctk.CTkLabel(
            parent, text=text, font=("Microsoft YaHei", 12, "bold"), text_color=color, anchor="w"
        ).pack(fill="x", padx=8, pady=(10, 4))

    @staticmethod
    def _build_pkg_tip(parent) -> None:
        tip = "💡 3.8 版本说明：请确认【设置 -> 图像 -> 客户端资源质量】或 XXMI 包体资源设置为 HD，避免部分模组材质不匹配。"
        ctk.CTkLabel(
            parent, text=tip, font=("Microsoft YaHei", 10), text_color="#94a3b8", anchor="w", wraplength=660
        ).pack(fill="x", padx=10, pady=(2, 6))

    @staticmethod
    def _build_row(parent, item, highlight: bool) -> None:
        bg = "#1e2638" if highlight else "#192030"
        row = ctk.CTkFrame(parent, fg_color=bg, corner_radius=8)
        row.pack(fill="x", padx=6, pady=3)
        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(top, text=item.name, font=("Microsoft YaHei", 11, "bold"), text_color="#f1f5f9").pack(side="left")

        if item.is_compliant is True:
            badge_txt, badge_clr = f"✅ {item.current_status}", "#16a34a"
        elif item.is_compliant is False:
            badge_txt, badge_clr = f"⚠️ {item.current_status}", "#d97706"
        else:
            badge_txt, badge_clr = item.current_status, "#475569"

        ctk.CTkLabel(
            top, text=f" 推荐: {item.recommended} ", font=("Microsoft YaHei", 10, "bold"),
            fg_color="#0f766e" if highlight else "#1e40af", text_color="#ffffff", corner_radius=5
        ).pack(side="right", padx=(6, 0))
        ctk.CTkLabel(
            top, text=f" {badge_txt} ", font=("Microsoft YaHei", 10), fg_color=badge_clr,
            text_color="#ffffff", corner_radius=5
        ).pack(side="right")

        desc = f"[{item.menu_path}]  {item.reason}"
        ctk.CTkLabel(
            row, text=desc, font=("Microsoft YaHei", 10), text_color="#94a3b8", anchor="w", wraplength=660
        ).pack(fill="x", padx=10, pady=(0, 6))

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(2, 14))
        ctk.CTkCheckBox(
            footer,
            text="每次启动前检查硬件与推荐设置",
            variable=self.show_again_var,
            font=("Microsoft YaHei", 11),
            text_color="#cbd5e1",
        ).pack(side="left")

        ctk.CTkButton(
            footer, text="⚡ 应用必改项并启动", width=155, height=34, corner_radius=6,
            font=("Microsoft YaHei", 11, "bold"), fg_color="#2563eb", hover_color="#1d4ed8",
            command=self._on_apply_and_launch,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            footer, text="直接启动", width=96, height=34, corner_radius=6,
            font=("Microsoft YaHei", 11), fg_color="#0f766e", hover_color="#0d9488",
            command=self._on_launch,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            footer, text="取消", width=76, height=34, corner_radius=6,
            font=("Microsoft YaHei", 11), fg_color="#242b3d", hover_color="#333d54",
            text_color="#94a3b8", command=self._on_cancel,
        ).pack(side="right")

    def _persist_pref_and_close(self, action: str) -> None:
        WuwaGraphicsAdvisor.set_show_advisor(bool(self.show_again_var.get()))
        self.action = action
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        if self.parent_window is not None and hasattr(self.parent_window, "winfo_toplevel"):
            try:
                top = self.parent_window.winfo_toplevel()
                top.lift()
                top.focus_force()
            except Exception:
                pass

    def _on_apply_and_launch(self) -> None:
        WuwaGraphicsAdvisor.apply_critical_mod_settings(self.game_path)
        self._persist_pref_and_close("apply_and_launch")

    def _on_launch(self) -> None:
        self._persist_pref_and_close("launch")

    def _on_cancel(self) -> None:
        self._persist_pref_and_close("cancel")


def show_pre_launch_advisor(game_path: Optional[Path] = None, parent=None) -> str:
    """Thread-safely inspects hardware, shows the real-settings advisor modal, and returns user action."""
    report = WuwaGraphicsAdvisor.analyze_and_recommend(game_path)

    def _call() -> str:
        root = parent
        if root is None:
            try:
                root = ctk._get_default_root()
            except Exception:
                root = None
        if root is None:
            return "launch"
        dlg = PreLaunchAdvisorDialog(report=report, game_path=game_path, parent=root)
        dlg.wait_window()
        return getattr(dlg, "action", "cancel")

    return str(_safe_dispatch(_call, parent=parent))
