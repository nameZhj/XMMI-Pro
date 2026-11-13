"""
@file: src/xxmi_launcher/gui/windows/mod_site_launcher_dialog.py
@brief: Dark modal selector dialog for Wuthering Waves mod websites with login-first and Read Frog badges.
@exports: ModSiteLauncherDialog
"""
from __future__ import annotations

from typing import Callable

from customtkinter import CTkButton, CTkFrame, CTkLabel, CTkScrollableFrame, CTkToplevel

from core.mod_sites import MOD_SITE_CATALOG, ModSiteSpec


class ModSiteLauncherDialog(CTkToplevel):
    """Presents verified Wuthering Waves mod websites with login-first and translation routing."""

    def __init__(
        self,
        parent,
        on_open_site: Callable[[ModSiteSpec, bool], None],
    ) -> None:
        super().__init__(parent)
        self.title("🌐 鸣潮模组资源导航中心（含登录引导 & 陪读蛙翻译）")
        self.geometry("760x560")
        self.resizable(False, False)
        self.configure(fg_color="#0f172a")
        self.on_open_site = on_open_site

        try:
            top = parent.winfo_toplevel() if parent is not None else None
            if top is not None:
                self.transient(top)
                self.grab_set()
        except Exception:
            pass

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda e: self._on_close())

    def _build_ui(self) -> None:
        header = CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))

        CTkLabel(
            header,
            text="🌐 鸣潮模组站点与下载方案导航",
            font=("Microsoft YaHei", 18, "bold"),
            text_color="#f8fafc",
        ).pack(anchor="w")

        CTkLabel(
            header,
            text="英文/韩文站点已集成陪读蛙（Read Frog）双语翻译插件；需登录站点可先一键跳转登录页，Cookie 本地持久保存。",
            font=("Microsoft YaHei", 11),
            text_color="#94a3b8",
        ).pack(anchor="w", pady=(4, 0))

        scroll = CTkScrollableFrame(self, fg_color="#111827", corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=20, pady=(6, 12))

        for site in MOD_SITE_CATALOG:
            self._build_site_card(scroll, site)

        footer = CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 14))
        CTkButton(
            footer,
            text="关闭",
            width=96,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            font=("Microsoft YaHei", 11),
            command=self._on_close,
        ).pack(side="right")

    def _build_site_card(self, parent, site: ModSiteSpec) -> None:
        card = CTkFrame(parent, fg_color="#1e293b", corner_radius=8)
        card.pack(fill="x", padx=6, pady=6)

        info_col = CTkFrame(card, fg_color="transparent")
        info_col.pack(side="left", fill="both", expand=True, padx=14, pady=10)

        title_row = CTkFrame(info_col, fg_color="transparent")
        title_row.pack(fill="x")

        CTkLabel(
            title_row,
            text=site.name,
            font=("Microsoft YaHei", 13, "bold"),
            text_color="#f8fafc",
        ).pack(side="left")

        if site.auto_translate:
            CTkLabel(
                title_row,
                text=" 🐸 陪读蛙翻译 ",
                font=("Microsoft YaHei", 10, "bold"),
                fg_color="#065f46",
                text_color="#a7f3d0",
                corner_radius=4,
            ).pack(side="left", padx=(8, 0))

        login_text = " 🔑 下载需先登录 " if site.login_required else " 🟢 免登直链/可选登录 "
        login_bg = "#92400e" if site.login_required else "#1e3a8a"
        login_fg = "#fde68a" if site.login_required else "#bfdbfe"
        CTkLabel(
            title_row,
            text=login_text,
            font=("Microsoft YaHei", 10, "bold"),
            fg_color=login_bg,
            text_color=login_fg,
            corner_radius=4,
        ).pack(side="left", padx=(6, 0))

        CTkLabel(
            info_col,
            text=site.description,
            font=("Microsoft YaHei", 11),
            text_color="#cbd5e1",
            justify="left",
            wraplength=455,
        ).pack(anchor="w", pady=(4, 0))

        btn_col = CTkFrame(card, fg_color="transparent")
        btn_col.pack(side="right", padx=12, pady=10)

        CTkButton(
            btn_col,
            text="🚀 进入专区",
            width=102,
            height=30,
            fg_color="#ea580c" if site.site_id == "gamebanana" else "#059669",
            hover_color="#c2410c" if site.site_id == "gamebanana" else "#047857",
            font=("Microsoft YaHei", 11, "bold"),
            command=lambda s=site: self._launch(s, login_first=False),
        ).pack(pady=(0, 6))

        CTkButton(
            btn_col,
            text="🔑 先去登录",
            width=102,
            height=28,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=("Microsoft YaHei", 10),
            command=lambda s=site: self._launch(s, login_first=True),
        ).pack()

    def _launch(self, site: ModSiteSpec, login_first: bool) -> None:
        self._on_close()
        self.on_open_site(site, login_first)

    def _on_close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
