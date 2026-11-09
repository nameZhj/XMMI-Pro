import os
import sys
import ctypes
import io
import json
import shutil
import subprocess
import threading
import logging
from pathlib import Path
from typing import Optional, List, Dict, Callable, Tuple, Set, Any
import core.path_manager as Paths

import customtkinter as ctk
from customtkinter import (
    CTkFrame,
    CTkLabel,
    CTkButton,
    CTkEntry,
    CTkScrollableFrame,
    CTkProgressBar,
    CTkSegmentedButton,
    CTkImage,
    CTkToplevel,
    CTkCheckBox,
    CTkTextbox
)
from PIL import Image, ImageDraw
import tkinter as tk
import tkinter.filedialog as filedialog
from gui.classes.element import UIElementBase
from core.mod_service import ModService, ModItem, CharacterMenuItem, ModRepairOptions, PasswordRequiredException
from core.locale_manager import L
from core.drag_drop import hook_drag_and_drop
from gui.copyable_error_dialog import show_copyable_error
from gui.modern_dialogs import show_info, show_warning, ask_confirm

log = logging.getLogger(__name__)


def apply_dwm_window_theme(window, caption_hex: str = "#161924", border_hex: str = "#232c3d"):
    """
    Applies Windows 11/10 DWM dark mode, custom titlebar background color,
    and outer border color matching the application theme.
    """
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        child_hwnd = window.winfo_id()
        parent_hwnd = ctypes.windll.user32.GetParent(child_hwnd)
        hwnd = parent_hwnd if parent_hwnd != 0 else child_hwnd

        def _hex_to_bgr(h: str) -> int:
            h = h.lstrip('#')
            if len(h) == 6:
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                return (b << 16) | (g << 8) | r
            return 0

        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_BORDER_COLOR = 34
        DWMWA_CAPTION_COLOR = 35
        DWMWA_TEXT_COLOR = 36

        # 1. Dark Mode
        dark_mode_val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark_mode_val), ctypes.sizeof(dark_mode_val)
        )

        # 2. Titlebar Caption Color
        caption_val = ctypes.c_uint32(_hex_to_bgr(caption_hex))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption_val), ctypes.sizeof(caption_val)
        )

        # 3. Titlebar Text Color (White)
        text_val = ctypes.c_uint32(0x00FFFFFF)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_TEXT_COLOR, ctypes.byref(text_val), ctypes.sizeof(text_val)
        )

        # 4. Outermost Border Color matching theme
        border_val = ctypes.c_uint32(_hex_to_bgr(border_hex))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_BORDER_COLOR, ctypes.byref(border_val), ctypes.sizeof(border_val)
        )
    except Exception as e:
        log.debug(f"Failed to apply DWM window styling: {e}")



class PasswordPromptDialog(ctk.CTkToplevel):
    """
    Sleek modal dialog prompting the user for an archive decryption password.
    Clearly specifies which archive filename requires the password.
    """
    def __init__(self, parent, archive_name: str, on_submit: Callable[[str], None], on_cancel: Callable[[], None]):
        super().__init__(parent)
        self.parent_window = parent
        self.title("模组解压密码确认")
        self.geometry("490x300")
        self.resizable(False, False)
        self.configure(fg_color="#161924")

        self.archive_name = archive_name
        self.on_submit_cb = on_submit
        self.on_cancel_cb = on_cancel
        self.submitted = False

        self.transient(parent)
        self.grab_set()

        # Center dialog on parent window
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + (pw - 490) // 2
            y = py + (ph - 300) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

        # Main Container
        container = CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=22, pady=18)

        # Header Badge with Key Icon & Target Filename
        header_frame = CTkFrame(container, fg_color="#1e2433", corner_radius=8, border_width=1, border_color="#334155")
        header_frame.pack(fill="x", pady=(0, 12))

        icon_lbl = CTkLabel(header_frame, text="🔐", font=("Segoe UI Emoji", 20))
        icon_lbl.pack(side="left", padx=(12, 6), pady=8)

        title_lbl = CTkLabel(
            header_frame,
            text=f"加密压缩包: {archive_name}",
            font=("Microsoft YaHei", 12, "bold"),
            text_color="#60a5fa",
            anchor="w",
            wraplength=380,
            justify="left"
        )
        title_lbl.pack(side="left", fill="x", expand=True, padx=(4, 12), pady=8)

        # Message
        msg_lbl = CTkLabel(
            container,
            text="此压缩包设置了解压密码保护。\n系统已自动尝试默认密码 \"huihui\" 失败，请输入该压缩包的正确密码：",
            font=("Microsoft YaHei", 11),
            text_color="#cbd5e1",
            justify="left",
            anchor="w"
        )
        msg_lbl.pack(fill="x", pady=(0, 10))

        # Input Entry Row with show toggle
        entry_frame = CTkFrame(container, fg_color="transparent")
        entry_frame.pack(fill="x", pady=(0, 16))

        self.show_pwd = False
        self.pwd_entry = CTkEntry(
            entry_frame,
            placeholder_text="请输入解压密码...",
            font=("Consolas", 12),
            height=38,
            corner_radius=8,
            fg_color="#1a1e2b",
            border_color="#3b82f6",
            text_color="#ffffff",
            placeholder_text_color="#64748b",
            show="*"
        )
        self.pwd_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.pwd_entry.focus_set()

        self.toggle_btn = CTkButton(
            entry_frame,
            text="👁️",
            width=42,
            height=38,
            corner_radius=8,
            font=("Segoe UI Emoji", 13),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#ffffff",
            command=self._toggle_show_pwd
        )
        self.toggle_btn.pack(side="right")

        # Action Buttons Row
        btn_row = CTkFrame(container, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4, 0))

        self.btn_skip = CTkButton(
            btn_row,
            text="跳过此包",
            width=110,
            height=36,
            corner_radius=8,
            font=("Microsoft YaHei", 11),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#94a3b8",
            command=self._on_cancel
        )
        self.btn_skip.pack(side="left")

        self.btn_ok = CTkButton(
            btn_row,
            text="确定解压",
            width=130,
            height=36,
            corner_radius=8,
            font=("Microsoft YaHei", 11, "bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            command=self._on_submit
        )
        self.btn_ok.pack(side="right")

        # Keybindings
        self.bind("<Return>", lambda e: self._on_submit())
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _toggle_show_pwd(self):
        self.show_pwd = not self.show_pwd
        self.pwd_entry.configure(show="" if self.show_pwd else "*")
        self.toggle_btn.configure(fg_color="#3b82f6" if self.show_pwd else "#242b3d")

    def _on_submit(self):
        pwd = self.pwd_entry.get().strip()
        if not pwd:
            return
        self.submitted = True
        try:
            self.grab_release()
            self.destroy()
        except Exception:
            pass
        if self.parent_window is not None:
            try:
                self.parent_window.lift()
                self.parent_window.focus_force()
            except Exception:
                pass
        if self.on_submit_cb:
            self.on_submit_cb(pwd)

    def _on_cancel(self):
        if not self.submitted:
            try:
                self.grab_release()
                self.destroy()
            except Exception:
                pass
            if self.parent_window is not None:
                try:
                    self.parent_window.lift()
                    self.parent_window.focus_force()
                except Exception:
                    pass
            if self.on_cancel_cb:
                self.on_cancel_cb()


class ImportProgressDialog(ctk.CTkToplevel):
    """Modern modal progress dialog during mod import & archive extraction."""
    def __init__(self, parent, title="正在导入模组"):
        super().__init__(parent)
        self.parent_window = parent
        self.title(title)
        self.geometry("450x190")
        self.resizable(False, False)
        self.configure(fg_color="#161924")

        self.transient(parent)
        self.grab_set()

        # Center on parent window
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + (pw - 450) // 2
            y = py + (ph - 190) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

        self.label = CTkLabel(
            self,
            text="正在准备导入...",
            font=("Microsoft YaHei", 12),
            text_color="#ffffff",
            anchor="w"
        )
        self.label.pack(fill="x", padx=24, pady=(24, 10))

        self.progress_bar = CTkProgressBar(
            self,
            width=400,
            height=14,
            corner_radius=6,
            progress_color="#2563eb",
            fg_color="#242b3d"
        )
        self.progress_bar.pack(padx=24, pady=10)
        self.progress_bar.set(0.0)

        self.status_lbl = CTkLabel(
            self,
            text="请稍候...",
            font=("Microsoft YaHei", 10),
            text_color="#94a3b8",
            anchor="w"
        )
        self.status_lbl.pack(fill="x", padx=24, pady=(4, 16))

    def update_progress(self, text: str, progress: float):
        try:
            self.label.configure(text=text)
            self.progress_bar.set(progress)
            self.status_lbl.configure(text=f"进度: {int(progress * 100)}%")
            self.update()
        except Exception:
            pass

    def finish_close(self):
        try:
            self.grab_release()
            self.destroy()
        except Exception:
            pass
        if self.parent_window is not None:
            try:
                self.parent_window.lift()
                self.parent_window.focus_force()
            except Exception:
                pass


class ModRepairDialog(ctk.CTkToplevel):
    """
    Comprehensive interactive Mod Repair & Fix Options modal dialog.
    Supports single mod deep repair and batch library deep repair.
    """
    def __init__(
        self,
        parent,
        target_mod: Optional[ModItem] = None,
        all_mods: Optional[List[ModItem]] = None,
        on_finished_callback: Optional[callable] = None
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.target_mod = target_mod
        self.all_mods = all_mods if all_mods is not None else []
        self.on_finished = on_finished_callback
        self.is_batch = (target_mod is None)

        title_text = "🔧 全库模组深度修复与适配" if self.is_batch else f"🔧 模组深度修复 - {target_mod.display_name}"
        self.title(title_text)
        self.geometry("640x720")
        self.minsize(580, 600)
        self.configure(fg_color="#121622")

        self.transient(parent)
        self.grab_set()

        # Center on parent window
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + (pw - 640) // 2
            y = py + (ph - 720) // 2
            self.geometry(f"+{max(10, x)}+{max(10, y)}")
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        # 1. Header Card
        header_frame = CTkFrame(self, fg_color="#181f2f", corner_radius=10, border_width=1, border_color="#2b384e")
        header_frame.pack(fill="x", padx=16, pady=(16, 8))

        top_row = CTkFrame(header_frame, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(12, 4))

        icon_lbl = CTkLabel(top_row, text="🔧", font=("Segoe UI Emoji", 20))
        icon_lbl.pack(side="left", padx=(0, 8))

        title_lbl = CTkLabel(
            top_row,
            text="鸣潮模组版本适配与深度修复引擎",
            font=("Microsoft YaHei", 14, "bold"),
            text_color="#ffffff"
        )
        title_lbl.pack(side="left")

        desc_lbl = CTkLabel(
            header_frame,
            text="基于 Wuwa_Mod_Fixer 规则库 (覆盖 115+ 角色与武器)，深度修复更新失效、模型破皮拉扯、远景变黑与贴图错位",
            font=("Microsoft YaHei", 10),
            text_color="#94a3b8",
            anchor="w",
            justify="left",
            wraplength=580
        )
        desc_lbl.pack(fill="x", padx=14, pady=(0, 6))

        # Target badge & Rule Library Status
        target_badge = CTkFrame(header_frame, fg_color="#0f172a", corner_radius=6, border_width=1, border_color="#1e293b")
        target_badge.pack(fill="x", padx=14, pady=(0, 10))

        if self.is_batch:
            target_str = f"🎯 当前模式: 全库批量深度修复 (共 {len(self.all_mods)} 个模组)"
        else:
            target_str = f"🎯 目标模组: 【{self.target_mod.display_name}】 ({self.target_mod.character_name})"

        badge_top = CTkFrame(target_badge, fg_color="transparent")
        badge_top.pack(fill="x", padx=10, pady=5)

        target_lbl = CTkLabel(
            badge_top,
            text=target_str,
            font=("Microsoft YaHei", 11, "bold"),
            text_color="#60a5fa",
            anchor="w"
        )
        target_lbl.pack(side="left")

        self.btn_update_rules = CTkButton(
            badge_top,
            text="🔄 检查规则更新",
            width=90,
            height=22,
            corner_radius=4,
            font=("Microsoft YaHei", 10),
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#38bdf8",
            command=self._on_check_rules_update
        )
        self.btn_update_rules.pack(side="right")

        ver_info = ModService.get_wuwa_fix_version_info()
        self.rule_ver_str = tk.StringVar(value=f"⚡ 规则库: v{ver_info['version']} ({ver_info['character_count']} 角色/武器)")
        self.rule_lbl = CTkLabel(
            badge_top,
            textvariable=self.rule_ver_str,
            font=("Microsoft YaHei", 10),
            text_color="#94a3b8"
        )
        self.rule_lbl.pack(side="right", padx=(0, 8))

        # 2. Options Preset Toolbar
        preset_bar = CTkFrame(self, fg_color="transparent")
        preset_bar.pack(fill="x", padx=16, pady=(4, 6))

        opt_title = CTkLabel(
            preset_bar,
            text="⚙️ 修复选项配置",
            font=("Microsoft YaHei", 12, "bold"),
            text_color="#e2e8f0"
        )
        opt_title.pack(side="left")

        btn_none = CTkButton(
            preset_bar,
            text="全不选",
            width=55,
            height=24,
            corner_radius=4,
            font=("Microsoft YaHei", 10),
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#cbd5e1",
            command=self._select_none_options
        )
        btn_none.pack(side="right", padx=2)

        btn_all = CTkButton(
            preset_bar,
            text="全选",
            width=50,
            height=24,
            corner_radius=4,
            font=("Microsoft YaHei", 10),
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#cbd5e1",
            command=self._select_all_options
        )
        btn_all.pack(side="right", padx=2)

        btn_rec = CTkButton(
            preset_bar,
            text="⚡ 推荐配置",
            width=70,
            height=24,
            corner_radius=4,
            font=("Microsoft YaHei", 10, "bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            command=self._select_recommended_options
        )
        btn_rec.pack(side="right", padx=2)

        # 3. Options Scrollable Container
        self.options_scroll = CTkScrollableFrame(self, fg_color="#161b28", corner_radius=8, border_width=1, border_color="#283246", height=230)
        self.options_scroll.pack(fill="both", expand=True, padx=16, pady=2)

        # Option Variables
        self.var_fix_hashes = tk.BooleanVar(value=True)
        self.var_fix_vertex_groups = tk.BooleanVar(value=True)
        self.var_fix_derive_textures = tk.BooleanVar(value=True)
        self.var_fix_rules = tk.BooleanVar(value=True)
        self.var_fix_resource_override = tk.BooleanVar(value=True)
        self.var_fix_stable_texture = tk.BooleanVar(value=True)
        self.var_fix_rendering_33 = tk.BooleanVar(value=True)
        self.var_fix_rover_special = tk.BooleanVar(value=False)
        self.var_inject_engine_ini = tk.BooleanVar(value=False)
        self.var_clean_trash_files = tk.BooleanVar(value=True)
        self.var_normalize_ini = tk.BooleanVar(value=True)
        self.var_create_backup = tk.BooleanVar(value=True)

        options_meta = [
            (self.var_fix_hashes, "游戏版本更新 Hash 替换", "匹配 119+ 角色与武器在版本更新后的主 Hash 与贴图 Hash"),
            (self.var_fix_vertex_groups, "骨骼与顶点组重映射 (vg_remap)", "重映射顶点组与骨骼权重，修复白芷、长离等因骨骼变动导致拉扯破皮"),
            (self.var_fix_derive_textures, "衍生贴图与 LOD 远景防黑补全", "自动补全 LOD/Wet/Charged/Injured 衍生重载，解决远距离变黑变色"),
            (self.var_fix_rules, "索引规则与 Shapekey 修复", "修正 match_first_index、match_index_count、面部表情与顶点偏移"),
            (self.var_fix_resource_override, "追加资源重载检查", "追加 CheckTextureOverride 检查，防止多材质重载相互冲突"),
            (self.var_fix_stable_texture, "状态贴图稳定模式", "稳定处理爱弥斯 (Aemeath)、椿 (Camellya)、千咲 (Chisa) 等角色的特殊状态贴图"),
            (self.var_fix_rendering_33, "Rendering 3.3 管线修复", "清理 TexCoord 缓冲中的旧版 COLOR1 顶点掩码，彻底解决 3.3 管线更新后的模型黑屏与掩码异常"),
            (self.var_fix_rover_special, "主角材质与风主眼部专属修复", "漂泊者 Materialmap 材质自动适配生成，以及风主满充能眼部修复"),
            (self.var_inject_engine_ini, "Engine.ini 渲染与防破图注入", "向游戏 Engine.ini 写入高精模型渲染 LODDistanceScale 与贴图流式优化"),
            (self.var_clean_trash_files, "清理冗余与临时干扰文件", "清除 CheckTexture.ini, References.ini, .DS_Store, Thumbs.db 等干扰文件"),
            (self.var_normalize_ini, "规范化 .ini 编码与路径格式", "转换所有 .ini 为标准 UTF-8 编码并将文件路径反斜杠标准化"),
            (self.var_create_backup, "修复前自动创建安全回滚备份", "自动备份原始文件，随时支持一键无损撤销与复原")
        ]

        for var, title, subtext in options_meta:
            opt_row = CTkFrame(self.options_scroll, fg_color="transparent")
            opt_row.pack(fill="x", padx=6, pady=4)

            chk = CTkCheckBox(
                opt_row,
                text=title,
                variable=var,
                font=("Microsoft YaHei", 11, "bold"),
                text_color="#f8fafc",
                checkmark_color="#ffffff",
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                border_color="#475569",
                border_width=2,
                corner_radius=4,
                width=24,
                height=24
            )
            chk.pack(anchor="w")

            desc = CTkLabel(
                opt_row,
                text=subtext,
                font=("Microsoft YaHei", 9),
                text_color="#94a3b8",
                anchor="w",
                justify="left"
            )
            desc.pack(anchor="w", padx=(28, 0), pady=(0, 2))

        # 4. Progress & Log Console Output
        self.progress_frame = CTkFrame(self, fg_color="#10131d", corner_radius=8, border_width=1, border_color="#1e2434")
        self.progress_frame.pack(fill="x", padx=16, pady=(6, 8))

        self.progress_bar = CTkProgressBar(
            self.progress_frame,
            height=6,
            corner_radius=3,
            progress_color="#2563eb",
            fg_color="#1e293b"
        )
        self.progress_bar.pack(fill="x", padx=10, pady=(8, 4))
        self.progress_bar.set(0.0)

        self.log_textbox = CTkTextbox(
            self.progress_frame,
            height=100,
            font=("Consolas", 10),
            fg_color="#090c13",
            text_color="#cbd5e1",
            corner_radius=6,
            border_width=1,
            border_color="#1a2233"
        )
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        self.log_textbox.insert("end", "💡 准备就绪。请确认勾选的修复选项后点击下方【开始修复】按钮...\n")
        self.log_textbox.configure(state="disabled")

        # 5. Bottom Action Bar
        bottom_bar = CTkFrame(self, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=16, pady=(0, 16))

        self.btn_start = CTkButton(
            bottom_bar,
            text="🚀 开始修复",
            height=36,
            corner_radius=6,
            font=("Microsoft YaHei", 12, "bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            command=self._start_repair
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 4))

        has_bk = (not self.is_batch and self.target_mod and ModService.has_backup(self.target_mod))
        self.btn_restore = CTkButton(
            bottom_bar,
            text="⏪ 一键回滚备份",
            height=36,
            corner_radius=6,
            font=("Microsoft YaHei", 11),
            fg_color="#334155" if has_bk else "#1e293b",
            hover_color="#475569" if has_bk else "#1e293b",
            text_color="#f1f5f9" if has_bk else "#64748b",
            state="normal" if has_bk else "disabled",
            command=self._rollback_backup
        )
        if not self.is_batch:
            self.btn_restore.pack(side="left", padx=4)

        self.btn_close = CTkButton(
            bottom_bar,
            text="关闭",
            width=80,
            height=36,
            corner_radius=6,
            font=("Microsoft YaHei", 11),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#f1f5f9",
            command=self._on_close
        )
        self.btn_close.pack(side="right", padx=(4, 0))

    def _select_recommended_options(self):
        self.var_fix_hashes.set(True)
        self.var_fix_vertex_groups.set(True)
        self.var_fix_derive_textures.set(True)
        self.var_fix_rules.set(True)
        self.var_fix_resource_override.set(True)
        self.var_fix_stable_texture.set(True)
        self.var_fix_rendering_33.set(True)
        self.var_fix_rover_special.set(False)
        self.var_inject_engine_ini.set(False)
        self.var_clean_trash_files.set(True)
        self.var_normalize_ini.set(True)
        self.var_create_backup.set(True)

    def _select_all_options(self):
        for v in [
            self.var_fix_hashes, self.var_fix_vertex_groups, self.var_fix_derive_textures,
            self.var_fix_rules, self.var_fix_resource_override, self.var_fix_stable_texture,
            self.var_fix_rendering_33, self.var_fix_rover_special, self.var_inject_engine_ini,
            self.var_clean_trash_files, self.var_normalize_ini, self.var_create_backup
        ]:
            v.set(True)

    def _select_none_options(self):
        for v in [
            self.var_fix_hashes, self.var_fix_vertex_groups, self.var_fix_derive_textures,
            self.var_fix_rules, self.var_fix_resource_override, self.var_fix_stable_texture,
            self.var_fix_rendering_33, self.var_fix_rover_special, self.var_inject_engine_ini,
            self.var_clean_trash_files, self.var_normalize_ini, self.var_create_backup
        ]:
            v.set(False)

    def _on_check_rules_update(self):
        self.btn_update_rules.configure(state="disabled", text="⏳ 检查中...")
        self._append_log("🔄 正在连接 Moonholder/Wuwa_Mod_Fixer 云端规则库检查更新...")

        def _worker():
            success, msg, _ = ModService.update_wuwa_fix_config_from_remote(force=False)
            def _ui_callback():
                try:
                    self.btn_update_rules.configure(state="normal", text="🔄 检查规则更新")
                    ver_info = ModService.get_wuwa_fix_version_info()
                    self.rule_ver_str.set(f"⚡ 规则库: v{ver_info['version']} ({ver_info['character_count']} 角色/武器)")
                    if success:
                        self._append_log(f"✅ {msg}")
                    else:
                        self._append_log(f"⚠️ {msg}")
                except Exception:
                    pass
            self.after(0, _ui_callback)

        threading.Thread(target=_worker, daemon=True).start()

    def _append_log(self, text: str):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", text + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def _start_repair(self):
        opts = ModRepairOptions(
            fix_hashes=self.var_fix_hashes.get(),
            fix_vertex_groups=self.var_fix_vertex_groups.get(),
            fix_derive_textures=self.var_fix_derive_textures.get(),
            fix_rules=self.var_fix_rules.get(),
            fix_resource_override=self.var_fix_resource_override.get(),
            fix_stable_texture=self.var_fix_stable_texture.get(),
            fix_rendering_33=self.var_fix_rendering_33.get(),
            fix_rover_special=self.var_fix_rover_special.get(),
            inject_engine_ini=self.var_inject_engine_ini.get(),
            clean_trash_files=self.var_clean_trash_files.get(),
            normalize_ini=self.var_normalize_ini.get(),
            create_backup=self.var_create_backup.get()
        )

        self.btn_start.configure(state="disabled", text="⏳ 正在深度修复中...")
        if not self.is_batch:
            self.btn_restore.configure(state="disabled")

        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

        threading.Thread(target=self._run_repair_worker, args=(opts,), daemon=True).start()

    def _run_repair_worker(self, opts: ModRepairOptions):
        try:
            if not self.is_batch and self.target_mod:
                self.after(0, lambda: self._append_log(f"🚀 开始深度修复模组: 【{self.target_mod.display_name}】..."))
                self.after(0, lambda: self.progress_bar.set(0.3))
                success, fixes = ModService.repair_mod(self.target_mod, options=opts)
                self.after(0, lambda: self.progress_bar.set(1.0))
                for f in fixes:
                    self.after(0, lambda msg=f: self._append_log(f"  • {msg}"))

                if success:
                    self.after(0, lambda: self._append_log("\n✨ 模组修复成功并已同步至游戏！"))
                else:
                    self.after(0, lambda: self._append_log("\n❌ 模组修复失败，请查看上方日志。"))
            else:
                total = len(self.all_mods)
                self.after(0, lambda: self._append_log(f"🚀 开始全库批量深度修复 (共 {total} 个模组)..."))
                for idx, m in enumerate(self.all_mods, 1):
                    progress = idx / max(1, total)
                    self.after(0, lambda p=progress: self.progress_bar.set(p))
                    self.after(0, lambda i=idx, n=m.display_name: self._append_log(f"[{i}/{total}] 正在处理: {n}..."))
                    success, fixes = ModService.repair_mod(m, options=opts)
                    for f in fixes:
                        self.after(0, lambda msg=f: self._append_log(f"    - {msg}"))

                self.after(0, lambda: self._append_log("\n🎉 全库批量模组深度修复完成！"))

            if self.on_finished:
                self.after(0, self.on_finished)
        except Exception as e:
            self.after(0, lambda err=str(e): self._append_log(f"\n❌ 修复过程出现异常: {err}"))
        finally:
            self.after(0, self._on_repair_finished)

    def _on_repair_finished(self):
        self.btn_start.configure(state="normal", text="🚀 开始修复")
        if not self.is_batch and self.target_mod:
            has_bk = ModService.has_backup(self.target_mod)
            self.btn_restore.configure(
                state="normal" if has_bk else "disabled",
                fg_color="#334155" if has_bk else "#1e293b",
                hover_color="#475569" if has_bk else "#1e293b",
                text_color="#f1f5f9" if has_bk else "#64748b"
            )

    def _rollback_backup(self):
        if self.is_batch or not self.target_mod:
            return
        confirm = ask_confirm(
            "确认回滚复原",
            f"确定要将模组【{self.target_mod.display_name}】还原至修复前的原始文件吗？\n\n此操作将完全恢复模组的初始文件。",
            parent=self
        )
        if not confirm:
            return

        success, msg = ModService.restore_mod(self.target_mod)
        if success:
            self._append_log(f"\n⏪ {msg}")
            if self.on_finished:
                self.on_finished()
            show_info("复原成功", msg, parent=self)
        else:
            self._append_log(f"\n⚠️ {msg}")
            show_warning("复原提示", msg, parent=self)

    def _on_close(self):
        try:
            self.grab_release()
            self.destroy()
        except Exception:
            pass
        if self.parent_window is not None:
            try:
                self.parent_window.lift()
                self.parent_window.focus_force()
            except Exception:
                pass


class ModernActionDropdown(tk.Toplevel):
    """
    Sleek, high-contrast, modern popup action dropdown menu
    with fixed icons, perfect typography alignment, and click-outside dismissal.
    """
    def __init__(self, parent, x: int, y: int, items: list):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#161924")

        self.container = CTkFrame(
            self,
            fg_color="#161924",
            corner_radius=8,
            border_width=1,
            border_color="#334155"
        )
        self.container.pack(fill="both", expand=True, padx=1, pady=1)

        for item in items:
            if item.get("is_separator"):
                sep = CTkFrame(self.container, height=1, fg_color="#283246")
                sep.pack(fill="x", padx=6, pady=3)
                continue

            icon = item.get("icon", "•")
            label = item.get("label", "")
            action = item.get("action", None)
            is_danger = item.get("danger", False)

            hover_bg = "#7f1d1d" if is_danger else "#2563eb"
            text_col = "#fca5a5" if is_danger else "#f1f5f9"
            icon_col = "#ef4444" if is_danger else "#93c5fd"

            btn_frame = CTkFrame(self.container, height=32, fg_color="transparent", corner_radius=6)
            btn_frame.pack(fill="x", padx=4, pady=1)
            btn_frame.pack_propagate(False)

            icon_lbl = CTkLabel(
                btn_frame,
                text=icon,
                font=("Segoe UI Emoji", 13),
                text_color=icon_col,
                width=26,
                anchor="center"
            )
            icon_lbl.pack(side="left", padx=(6, 2))

            text_lbl = CTkLabel(
                btn_frame,
                text=label,
                font=("Microsoft YaHei", 11),
                text_color=text_col,
                anchor="w"
            )
            text_lbl.pack(side="left", fill="x", expand=True, padx=(2, 8))

            handler = lambda e, a=action: self._trigger_and_close(a)
            btn_frame.bind("<Button-1>", handler)
            icon_lbl.bind("<Button-1>", handler)
            text_lbl.bind("<Button-1>", handler)

            def _on_enter(e, f=btn_frame, tc=text_col, ic=icon_col, hbg=hover_bg):
                f.configure(fg_color=hbg)

            def _on_leave(e, f=btn_frame):
                f.configure(fg_color="transparent")

            btn_frame.bind("<Enter>", _on_enter)
            btn_frame.bind("<Leave>", _on_leave)
            icon_lbl.bind("<Enter>", _on_enter)
            icon_lbl.bind("<Leave>", _on_leave)
            text_lbl.bind("<Enter>", _on_enter)
            text_lbl.bind("<Leave>", _on_leave)

        self.update_idletasks()
        req_w = 175
        req_h = self.container.winfo_reqheight() + 2
        self.geometry(f"{req_w}x{req_h}+{x}+{y}")

        # Click-outside dismissal
        self.after(50, self._bind_click_outside)

    def _bind_click_outside(self):
        try:
            self.bind_all("<Button-1>", self._check_click_outside, add="+")
            self.bind("<Escape>", lambda e: self._close())
        except Exception:
            pass

    def _check_click_outside(self, event):
        try:
            if not self.winfo_exists():
                return
            x, y = self.winfo_pointerxy()
            rx = self.winfo_rootx()
            ry = self.winfo_rooty()
            rw = self.winfo_width()
            rh = self.winfo_height()
            if not (rx <= x <= rx + rw and ry <= y <= ry + rh):
                self._close()
        except Exception:
            self._close()

    def _close(self):
        try:
            self.unbind_all("<Button-1>")
            self.destroy()
        except Exception:
            pass

    def _trigger_and_close(self, action):
        self._close()
        if action and callable(action):
            action()


class ModCard(CTkFrame):
    """Clean, modern, high-contrast Mod Card widget with selection support and contain-fit thumbnail."""
    def __init__(self, master, mod_item: ModItem, on_toggle_callback, on_delete_callback,
                 on_repair_callback, on_restore_callback, on_change_thumb_callback, on_rename_callback,
                 on_select_callback=None, is_selected: bool = False, image_cache: dict = None):
        self.mod_item = mod_item
        self.on_toggle = on_toggle_callback
        self.on_delete = on_delete_callback
        self.on_repair = on_repair_callback
        self.on_restore = on_restore_callback
        self.on_change_thumb = on_change_thumb_callback
        self.on_rename = on_rename_callback
        self.on_select = on_select_callback
        self.is_selected = is_selected
        self.image_cache = image_cache if image_cache is not None else {}

        # High-contrast subtle card border & background
        if is_selected:
            bg_color = "#1d263b"
            border_color = "#3b82f6"
            border_w = 2
        elif mod_item.enabled:
            bg_color = "#182030"
            border_color = "#2a364f"
            border_w = 1
        else:
            bg_color = "#141722"
            border_color = "#1e2434"
            border_w = 1

        super().__init__(
            master,
            width=254,
            height=252,
            corner_radius=10,
            fg_color=bg_color,
            border_width=border_w,
            border_color=border_color
        )
        self.pack_propagate(False)

        # 1. Thumbnail Container (Contain Aspect Fit - longest side fully displayed, centered)
        thumbnail_img = ModCard.get_thumbnail_image(self.image_cache, mod_item, target_w=242, target_h=135)
        self.img_label = CTkLabel(
            self,
            text="",
            image=thumbnail_img,
            width=242,
            height=135,
            corner_radius=8
        )
        self.img_label.pack(fill="x", padx=6, pady=(6, 4))

        # 2. Mod Title (High Contrast)
        display_title = mod_item.display_name
        if len(display_title) > 20:
            short_title = display_title[:18] + "..."
        else:
            short_title = display_title

        text_color = "#ffffff" if (is_selected or mod_item.enabled) else "#e2e8f0"
        self.name_label = CTkLabel(
            self,
            text=short_title,
            font=("Microsoft YaHei", 12, "bold"),
            text_color=text_color,
            anchor="w"
        )
        self.name_label.pack(fill="x", padx=10, pady=(2, 1))

        # 3. File Info & Size Stats (High Contrast)
        size_mb = mod_item.size_bytes / (1024 * 1024)
        size_str = f"{size_mb:.1f} MB" if size_mb >= 0.1 else f"{mod_item.size_bytes / 1024:.1f} KB"
        info_text = f"{mod_item.file_count} 个文件 · {size_str}"
        info_color = "#cbd5e1" if mod_item.enabled else "#94a3b8"
        self.info_label = CTkLabel(
            self,
            text=info_text,
            font=("Microsoft YaHei", 10),
            text_color=info_color,
            anchor="w"
        )
        self.info_label.pack(fill="x", padx=10, pady=(0, 4))

        # 4. Bottom Controls Frame
        self.controls_frame = CTkFrame(self, fg_color="transparent")
        self.controls_frame.pack(fill="x", padx=8, pady=(2, 6))

        # Toggle Status Button
        if mod_item.enabled:
            toggle_text = "✓ 已启用"
            toggle_fg = "#10b981"
            toggle_hover = "#059669"
            toggle_border = 0
            toggle_border_color = "#10b981"
            toggle_text_color = "#ffffff"
        else:
            toggle_text = "已禁用"
            toggle_fg = "#242b3d"
            toggle_hover = "#333d54"
            toggle_border = 1
            toggle_border_color = "#3b475f"
            toggle_text_color = "#f1f5f9"

        self.toggle_btn = CTkButton(
            self.controls_frame,
            text=toggle_text,
            width=88,
            height=28,
            corner_radius=6,
            font=("Microsoft YaHei", 11, "bold" if mod_item.enabled else "normal"),
            fg_color=toggle_fg,
            hover_color=toggle_hover,
            border_width=toggle_border,
            border_color=toggle_border_color,
            text_color=toggle_text_color,
            command=self._handle_toggle
        )
        self.toggle_btn.pack(side="left", padx=(0, 4))

        # Open Folder Button
        self.folder_btn = CTkButton(
            self.controls_frame,
            text="📂 目录",
            width=62,
            height=28,
            corner_radius=6,
            font=("Microsoft YaHei", 11),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#f1f5f9",
            command=self._open_folder
        )
        self.folder_btn.pack(side="left", padx=(0, 4))

        # More Actions 3-dots [⋮] Button (clearly visible with proper spacing)
        self.more_btn = CTkButton(
            self.controls_frame,
            text="⋮",
            width=32,
            height=28,
            corner_radius=6,
            font=("Segoe UI", 14, "bold"),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#ffffff",
            command=self._show_more_menu
        )
        self.more_btn.pack(side="right", padx=(2, 0))

        # Bind click events for selecting card
        select_handler = lambda e: self._handle_select()
        self.bind("<Button-1>", select_handler)
        self.img_label.bind("<Button-1>", select_handler)
        self.name_label.bind("<Button-1>", select_handler)
        self.info_label.bind("<Button-1>", select_handler)

    def _handle_select(self):
        if self.on_select and callable(self.on_select):
            self.on_select(self.mod_item)

    def _show_more_menu(self):
        """Displays modern styled CustomTkinter popup dropdown."""
        items = [
            {"icon": "🔧", "label": "修复模组", "action": lambda: self.on_repair(self.mod_item)},
            {"icon": "⏮️", "label": "复原模组 (还原备份)", "action": lambda: self.on_restore(self.mod_item)},
            {"icon": "🖼️", "label": "修改预览图", "action": lambda: self.on_change_thumb(self.mod_item)},
            {"icon": "✏️", "label": "重命名模组", "action": lambda: self.on_rename(self.mod_item)},
            {"is_separator": True},
            {"icon": "🗑️", "label": "删除模组", "action": lambda: self.on_delete(self.mod_item), "danger": True},
        ]
        x = self.more_btn.winfo_rootx() - 152
        y = self.more_btn.winfo_rooty() + self.more_btn.winfo_height() + 4
        ModernActionDropdown(self, x=x, y=y, items=items)

    @staticmethod
    def get_thumbnail_image(image_cache: dict, mod_item: ModItem, target_w: int = 238, target_h: int = 135) -> CTkImage:
        """
        Loads the thumbnail in Contain mode (aspect fit) without cropping.
        The longest side is scaled to fit fully within target_w x target_h.
        """
        cache_key = f"{mod_item.thumbnail_path}_{target_w}x{target_h}" if mod_item.thumbnail_path else f"placeholder_{mod_item.name}_{target_w}x{target_h}"
        if image_cache is not None and cache_key in image_cache:
            return image_cache[cache_key]

        if mod_item.thumbnail_path and mod_item.thumbnail_path.exists():
            try:
                with open(mod_item.thumbnail_path, 'rb') as f:
                    img_bytes = io.BytesIO(f.read())
                with Image.open(img_bytes) as raw_img:
                    raw_w, raw_h = raw_img.size
                    if raw_w <= 0 or raw_h <= 0:
                        raw_w, raw_h = target_w, target_h

                    # Scale to fit completely inside target_w x target_h (contain mode - longest side fit)
                    scale = min(target_w / raw_w, target_h / raw_h)
                    fit_w = max(1, int(raw_w * scale))
                    fit_h = max(1, int(raw_h * scale))

                    resized = raw_img.convert("RGBA").resize((fit_w, fit_h), Image.Resampling.LANCZOS)

                    # Create elegant dark letterbox/pillarbox canvas
                    canvas = Image.new("RGBA", (target_w, target_h), (18, 22, 32, 255))
                    offset_x = (target_w - fit_w) // 2
                    offset_y = (target_h - fit_h) // 2
                    canvas.paste(resized, (offset_x, offset_y), resized)

                    ctk_img = CTkImage(light_image=canvas, dark_image=canvas, size=(target_w, target_h))
                    if image_cache is not None:
                        image_cache[cache_key] = ctk_img
                    return ctk_img
            except Exception as e:
                log.debug(f"Failed to load thumbnail for {mod_item.name}: {e}")

        # Stylish dark gradient placeholder
        placeholder = Image.new("RGBA", (target_w, target_h), (20, 24, 34, 255))
        draw = ImageDraw.Draw(placeholder)
        draw.rectangle([2, 2, target_w - 3, target_h - 3], outline=(42, 50, 68, 255), width=1)
        ctk_img = CTkImage(light_image=placeholder, dark_image=placeholder, size=(target_w, target_h))
        if image_cache is not None:
            image_cache[cache_key] = ctk_img
        return ctk_img

    def _handle_toggle(self):
        self.on_toggle(self.mod_item)

    def _open_folder(self):
        try:
            if self.mod_item.path.exists():
                os.startfile(str(self.mod_item.path))
        except Exception as e:
            log.exception(f"Failed to open folder: {e}")

    def _handle_delete(self):
        self.on_delete(self.mod_item)


class ModManagerFrame(CTkToplevel, UIElementBase):
    """
    Visual Mod Manager Window (CTkToplevel) with:
    - Freely movable via custom dark titlebar dragging or native window handling.
    - Freely resizable with minimum bounds (960x600) and responsive grid columns.
    - Minimizable to Windows taskbar.
    - Maximizable / Restorable (via maximize button or titlebar double-click).
    - Three-column layout (Categories sidebar + Cards grid + Hotkey details inspector).
    """
    def __init__(self, master=None, canvas=None, on_close=None, **kwargs):
        UIElementBase.__init__(self, **kwargs)
        CTkToplevel.__init__(self, master=master)

        self.canvas = canvas
        self.on_close_callback = on_close if callable(on_close) else None
        self.image_cache: Dict[str, CTkImage] = {}

        self.title("模组管理 - XMMI Pro")
        self.geometry("1240x740")
        self.minsize(980, 600)
        self.configure(fg_color="#0f1117")
        self.protocol("WM_DELETE_WINDOW", self.close_mod_manager)

        self._current_cols = 3
        self._initial_centered = False

        self.current_mods: List[ModItem] = []
        self.character_menu_items: List[CharacterMenuItem] = []
        self.selected_character_id: str = "all"
        self.selected_mod_item: Optional[ModItem] = None
        self.search_text: str = ""
        self.filter_state: str = "all"

        self.sidebar_buttons: Dict[str, CTkButton] = {}

        self.scroll_frame = None
        self.character_scroll_frame = None

        # Start hidden initially until explicitly opened
        self.withdraw()
        self._build_ui()

    def _build_ui(self):
        # 0. Outermost Container Frame with Subtle Soft Border
        self.window_border_frame = CTkFrame(
            self,
            fg_color="#0f1117",
            corner_radius=0,
            border_width=1,
            border_color="#232c3d"
        )
        self.window_border_frame.pack(fill="both", expand=True)

        # 1. Single Unified Top Toolbar (Merges title, active category indicator, filters, and actions)
        self.top_bar = CTkFrame(self.window_border_frame, height=54, fg_color="#161924", corner_radius=10, border_width=1, border_color="#232c3d")
        self.top_bar.pack(fill="x", padx=12, pady=(10, 8))
        self.top_bar.pack_propagate(False)

        # Left side: Category & Stats
        self.title_icon = CTkLabel(
            self.top_bar,
            text="📦",
            font=("Segoe UI Emoji", 16)
        )
        self.title_icon.pack(side="left", padx=(14, 4))

        self.current_category_label = CTkLabel(
            self.top_bar,
            text="🌟 全部模组",
            font=("Microsoft YaHei", 14, "bold"),
            text_color="#ffffff"
        )
        self.current_category_label.pack(side="left", padx=(2, 10))

        self.stats_label = CTkLabel(
            self.top_bar,
            text="正在扫描模组...",
            font=("Microsoft YaHei", 11),
            text_color="#94a3b8"
        )
        self.stats_label.pack(side="left", padx=4)

        # Right side: Filter & Action Buttons Container
        self.actions_frame = CTkFrame(self.top_bar, fg_color="transparent")
        self.actions_frame.pack(side="right", padx=10)

        # State Filter Segment
        self.state_filter_seg = CTkSegmentedButton(
            self.actions_frame,
            values=["全部", "已启用", "已禁用"],
            font=("Microsoft YaHei", 11, "bold"),
            selected_color="#2563eb",
            selected_hover_color="#1d4ed8",
            unselected_color="#1e2538",
            unselected_hover_color="#2b354d",
            text_color="#ffffff",
            command=self._on_filter_state_change
        )
        self.state_filter_seg.set("全部")
        self.state_filter_seg.pack(side="left", padx=(0, 10))

        self.gamebanana_btn = CTkButton(
            self.actions_frame,
            text="🍌 GameBanana 下载",
            width=132,
            height=32,
            corner_radius=6,
            font=("Microsoft YaHei", 11, "bold"),
            fg_color="#ea580c",
            hover_color="#c2410c",
            text_color="#ffffff",
            command=self._open_gamebanana_browser
        )
        self.gamebanana_btn.pack(side="left", padx=2)

        self.import_zip_btn = CTkButton(
            self.actions_frame,
            text="📦 导入压缩包",
            width=96,
            height=32,
            corner_radius=6,
            font=("Microsoft YaHei", 11, "bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            text_color="#ffffff",
            command=self._import_archive
        )
        self.import_zip_btn.pack(side="left", padx=2)

        self.import_folder_btn = CTkButton(
            self.actions_frame,
            text="📁 导入文件夹",
            width=96,
            height=32,
            corner_radius=6,
            font=("Microsoft YaHei", 11),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#f1f5f9",
            command=self._import_folder
        )
        self.import_folder_btn.pack(side="left", padx=2)

        self.open_dir_btn = CTkButton(
            self.actions_frame,
            text="📂 目录",
            width=70,
            height=32,
            corner_radius=6,
            font=("Microsoft YaHei", 11),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#f1f5f9",
            command=self._open_mods_folder
        )
        self.open_dir_btn.pack(side="left", padx=2)

        self.repair_all_btn = CTkButton(
            self.actions_frame,
            text="🔧 深度修复",
            width=88,
            height=32,
            corner_radius=6,
            font=("Microsoft YaHei", 11),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#f1f5f9",
            command=lambda: self._open_repair_dialog(None)
        )
        self.repair_all_btn.pack(side="left", padx=2)

        self.hot_update_btn = CTkButton(
            self.actions_frame,
            text="⚡ 热更新与同步",
            width=110,
            height=32,
            corner_radius=6,
            font=("Microsoft YaHei", 11, "bold"),
            fg_color="#0d9488",
            hover_color="#0f766e",
            text_color="#ffffff",
            command=self._open_hot_update_dialog
        )
        self.hot_update_btn.pack(side="left", padx=2)

        self.refresh_btn = CTkButton(
            self.actions_frame,
            text="🔄 刷新",
            width=65,
            height=32,
            corner_radius=6,
            font=("Microsoft YaHei", 11),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#f1f5f9",
            command=self.refresh_mods
        )
        self.refresh_btn.pack(side="left", padx=2)

        # 2. Main Horizontal Container (Left Sidebar + Center Cards Panel + Right Hotkey Inspector)
        self.body_container = CTkFrame(self.window_border_frame, fg_color="transparent")
        self.body_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.body_container.pack_propagate(False)

        # ==========================================
        # LEFT SIDEBAR: Character Category Menu
        # ==========================================
        self.left_sidebar = CTkFrame(
            self.body_container,
            width=210,
            fg_color="#131620",
            corner_radius=10,
            border_width=1,
            border_color="#232c3d"
        )
        self.left_sidebar.pack(side="left", fill="y", padx=(0, 8), pady=0)
        self.left_sidebar.pack_propagate(False)

        # Search Box inside Sidebar Header
        self.search_container = CTkFrame(self.left_sidebar, fg_color="transparent")
        self.search_container.pack(fill="x", padx=10, pady=(10, 6))

        self.search_entry = CTkEntry(
            self.search_container,
            placeholder_text="🔍 检索角色/拼音/英文...",
            height=34,
            corner_radius=8,
            font=("Microsoft YaHei", 11),
            fg_color="#1a1e2b",
            border_color="#334155",
            text_color="#ffffff",
            placeholder_text_color="#94a3b8"
        )
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", self._on_search_change)

        # Sidebar Title
        self.sidebar_title_label = CTkLabel(
            self.left_sidebar,
            text="角色二级分类",
            font=("Microsoft YaHei", 11, "bold"),
            text_color="#94a3b8",
            anchor="w"
        )
        self.sidebar_title_label.pack(fill="x", padx=14, pady=(4, 4))

        # Scrollable Character List Frame
        self.character_scroll_frame = CTkScrollableFrame(
            self.left_sidebar,
            fg_color="transparent",
            corner_radius=6
        )
        self.character_scroll_frame.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        # ==========================================
        # RIGHT INSPECTOR PANEL: Mod Hotkeys & Details
        # ==========================================
        self.inspector_panel = CTkFrame(
            self.body_container,
            width=310,
            fg_color="#131620",
            corner_radius=10,
            border_width=1,
            border_color="#232c3d"
        )
        self.inspector_panel.pack(side="right", fill="y", padx=(8, 0), pady=0)
        self.inspector_panel.pack_propagate(False)

        # Inspector Header Bar
        self.inspector_header = CTkFrame(self.inspector_panel, height=44, fg_color="#161924", corner_radius=8, border_width=1, border_color="#232c3d")
        self.inspector_header.pack(fill="x", padx=8, pady=(8, 6))
        self.inspector_header.pack_propagate(False)

        self.inspector_title = CTkLabel(
            self.inspector_header,
            text="🎮 快捷键与模组详情",
            font=("Microsoft YaHei", 12, "bold"),
            text_color="#ffffff"
        )
        self.inspector_title.pack(side="left", padx=10)

        # Scrollable Body of Inspector
        self.inspector_scroll = CTkScrollableFrame(
            self.inspector_panel,
            fg_color="transparent",
            corner_radius=6
        )
        self.inspector_scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        # ==========================================
        # CENTER MAIN PANEL: Mod Grid
        # ==========================================
        self.right_panel = CTkFrame(
            self.body_container,
            fg_color="#131620",
            corner_radius=10,
            border_width=1,
            border_color="#232c3d"
        )
        self.right_panel.pack(side="left", fill="both", expand=True, padx=0, pady=0)
        self.right_panel.pack_propagate(False)

        # Mod Scrollable Cards Grid Frame
        self.scroll_frame = CTkScrollableFrame(
            self.right_panel,
            fg_color="transparent",
            corner_radius=8
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=(10, 10), pady=(10, 10))
        for i in range(12):
            self.scroll_frame.grid_columnconfigure(i, weight=1 if i < 3 else 0, uniform="mod_col" if i < 3 else "")

        # Dynamic Grid Column Responsive Handler on Window Resize
        self.right_panel.bind("<Configure>", self._on_panel_resize)

    def _on_panel_resize(self, event=None):
        """Dynamically adjusts the number of card columns based on available panel width."""
        if not self.scroll_frame:
            return
        panel_w = self.right_panel.winfo_width()
        if panel_w < 100:
            return
        # ModCard width is 254px + 16px padding = 270px + scrollbar clearance
        new_cols = max(2, (panel_w - 30) // 270)
        if new_cols != self._current_cols:
            self._current_cols = new_cols
            for i in range(12):
                self.scroll_frame.grid_columnconfigure(i, weight=1 if i < new_cols else 0, uniform="mod_col" if i < new_cols else "")
            self._render_cards()

    def _on_search_change(self, event=None):
        self.search_text = self.search_entry.get().strip()
        self._render_character_menu()
        self._render_cards()

    def _on_filter_state_change(self, value):
        mapping = {"全部": "all", "已启用": "enabled", "已禁用": "disabled"}
        self.filter_state = mapping.get(value, "all")
        self._render_cards()

    def _select_character(self, character_id: str):
        self.selected_character_id = character_id
        self._render_character_menu()
        self._render_cards()

    def refresh_mods(self):
        """Re-scans mods from disk, updates character categories and grid."""
        self.current_mods = ModService.scan_mods(auto_resolve=True)
        self._render_character_menu()
        self._render_cards()

    def _render_character_menu(self):
        """Renders the left secondary character category list with counts and active selection."""
        if self.character_scroll_frame is None:
            return

        for widget in self.character_scroll_frame.winfo_children():
            widget.destroy()

        self.character_menu_items = ModService.get_character_menu_items(
            self.current_mods,
            search_query=self.search_text
        )

        # Ensure valid selection
        valid_ids = [item.character_id for item in self.character_menu_items]
        if self.selected_character_id not in valid_ids:
            self.selected_character_id = "all"

        self.sidebar_buttons.clear()

        for item in self.character_menu_items:
            is_active = (item.character_id == self.selected_character_id)

            bg_col = "#2563eb" if is_active else "#181c28"
            border_col = "#60a5fa" if is_active else "#273043"
            text_col = "#ffffff" if is_active else "#f1f5f9"
            badge_bg = "#1d4ed8" if is_active else "#242b3d"
            badge_text_col = "#ffffff" if is_active else "#93c5fd"

            btn_frame = CTkFrame(
                self.character_scroll_frame,
                height=42,
                corner_radius=8,
                fg_color=bg_col,
                border_width=1,
                border_color=border_col
            )
            btn_frame.pack(fill="x", pady=3, padx=2)
            btn_frame.pack_propagate(False)

            # Title label
            title_text = item.display_title
            if len(title_text) > 16:
                title_text = title_text[:14] + ".."

            name_lbl = CTkLabel(
                btn_frame,
                text=title_text,
                font=("Microsoft YaHei", 11, "bold" if is_active else "normal"),
                text_color=text_col,
                anchor="w"
            )
            name_lbl.pack(side="left", padx=(12, 4), pady=4)

            # Count badge
            badge_text = f"{item.enabled_count}/{item.total_count}" if item.total_count > 0 else "0"
            badge_lbl = CTkLabel(
                btn_frame,
                text=badge_text,
                font=("Microsoft YaHei", 10, "bold"),
                text_color=badge_text_col,
                fg_color=badge_bg,
                corner_radius=6,
                padx=7,
                pady=2
            )
            badge_lbl.pack(side="right", padx=(4, 10), pady=4)

            # Event Handlers
            cid = item.character_id
            click_handler = lambda e, c=cid: self._select_character(c)
            btn_frame.bind("<Button-1>", click_handler)
            name_lbl.bind("<Button-1>", click_handler)
            badge_lbl.bind("<Button-1>", click_handler)

            # Hover feedback for inactive items
            if not is_active:
                def _on_enter(e, f=btn_frame):
                    f.configure(fg_color="#22283a", border_color="#3b82f6")
                def _on_leave(e, f=btn_frame):
                    f.configure(fg_color="#181c28", border_color="#273043")

                btn_frame.bind("<Enter>", _on_enter)
                btn_frame.bind("<Leave>", _on_leave)
                name_lbl.bind("<Enter>", _on_enter)
                name_lbl.bind("<Leave>", _on_leave)
                badge_lbl.bind("<Enter>", _on_enter)
                badge_lbl.bind("<Leave>", _on_leave)

    def _render_cards(self):
        """Renders the mod cards in grid matching the selected character category and filters."""
        if self.scroll_frame is None:
            return

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Update Category Header Title
        sel_item = next((it for it in self.character_menu_items if it.character_id == self.selected_character_id), None)
        if sel_item:
            self.current_category_label.configure(text=f"{sel_item.display_title}")
        else:
            self.current_category_label.configure(text="🌟 全部模组")

        filtered_mods = []
        for m in self.current_mods:
            # Search query filter (CN, EN, Pinyin, GUID, Mod Name)
            if self.search_text:
                q = self.search_text.lower()
                matched = (
                    q in m.display_name.lower() or
                    q in m.name.lower() or
                    q in m.character_name.lower() or
                    q in m.character_en.lower() or
                    any(q in g for g in m.object_guids)
                )
                if not matched:
                    continue

            # Character category filter
            if self.selected_character_id != "all" and m.character_id != self.selected_character_id:
                continue

            # State filter
            if self.filter_state == "enabled" and not m.enabled:
                continue
            if self.filter_state == "disabled" and m.enabled:
                continue

            filtered_mods.append(m)

        # Update stats
        total_count = len(self.current_mods)
        enabled_count = sum(1 for m in self.current_mods if m.enabled)
        showing_count = len(filtered_mods)
        self.stats_label.configure(text=f"共 {total_count} 个模组 · 已启用 {enabled_count} 个 (当前显示 {showing_count} 个)")

        # Empty State
        if not filtered_mods:
            empty_frame = CTkFrame(self.scroll_frame, fg_color="transparent")
            empty_frame.grid(row=0, column=0, columnspan=4, pady=80, sticky="nsew")

            empty_icon = CTkLabel(
                empty_frame,
                text="📂",
                font=("Segoe UI Emoji", 44)
            )
            empty_icon.pack(pady=(10, 4))

            empty_label = CTkLabel(
                empty_frame,
                text="当前分类下暂无模组",
                font=("Microsoft YaHei", 14, "bold"),
                text_color="#94a3b8"
            )
            empty_label.pack(pady=4)

            hint_label = CTkLabel(
                empty_frame,
                text="💡 支持直接批量拖拽各种格式压缩包（.zip / .7z / .rar / .tar 等）或文件夹到此处导入\n也可以点击右上角【📦 导入压缩包】或【📁 导入文件夹】",
                font=("Microsoft YaHei", 11),
                text_color="#94a3b8",
                justify="center"
            )
            hint_label.pack(pady=(2, 16))
            return

        # Explicitly sort: Enabled mods first, then disabled mods, then alphabetically
        filtered_mods.sort(key=lambda m: (not m.enabled, m.display_name.lower()))

        # Update selected mod item reference
        if self.selected_mod_item is not None:
            # Re-link selected mod item to fresh instance from filtered list if exists
            matched_sel = next((m for m in filtered_mods if m.path.resolve() == self.selected_mod_item.path.resolve()), None)
            self.selected_mod_item = matched_sel if matched_sel else (filtered_mods[0] if filtered_mods else None)
        else:
            self.selected_mod_item = filtered_mods[0] if filtered_mods else None

        # Render Cards in Dynamic Responsive Column Grid
        columns = self._current_cols
        for idx, mod_item in enumerate(filtered_mods):
            row = idx // columns
            col = idx % columns

            is_sel = (self.selected_mod_item is not None and mod_item.path.resolve() == self.selected_mod_item.path.resolve())

            card = ModCard(
                self.scroll_frame,
                mod_item=mod_item,
                on_toggle_callback=self._toggle_mod,
                on_delete_callback=self._delete_mod,
                on_repair_callback=self._repair_mod,
                on_restore_callback=self._restore_mod,
                on_change_thumb_callback=self._change_thumbnail,
                on_rename_callback=self._rename_mod,
                on_select_callback=self._select_mod_item,
                is_selected=is_sel,
                image_cache=self.image_cache
            )
            card.grid(row=row, column=col, padx=6, pady=6, sticky="n")

        self._render_inspector_panel()

    def _select_mod_item(self, mod_item: ModItem):
        """Selects a mod card and updates the right inspector panel with its hotkeys and details."""
        self.selected_mod_item = mod_item
        self._render_inspector_panel()

        # Update visual highlight on existing card widgets
        if self.scroll_frame:
            for child in self.scroll_frame.winfo_children():
                if isinstance(child, ModCard):
                    is_sel = (child.mod_item.path.resolve() == mod_item.path.resolve())
                    child.is_selected = is_sel
                    if is_sel:
                        child.configure(border_color="#3b82f6", border_width=2, fg_color="#1d263b")
                    elif child.mod_item.enabled:
                        child.configure(border_color="#2a364f", border_width=1, fg_color="#182030")
                    else:
                        child.configure(border_color="#1e2434", border_width=1, fg_color="#141722")

    def _render_inspector_panel(self):
        """Renders the right inspector sidebar with selected mod thumbnail, hotkeys, and quick actions."""
        if self.inspector_scroll is None:
            return

        for widget in self.inspector_scroll.winfo_children():
            widget.destroy()

        if self.selected_mod_item is None:
            empty_panel = CTkFrame(self.inspector_scroll, fg_color="transparent")
            empty_panel.pack(fill="both", expand=True, pady=60)

            CTkLabel(
                empty_panel,
                text="🎮",
                font=("Segoe UI Emoji", 36)
            ).pack(pady=(10, 6))

            CTkLabel(
                empty_panel,
                text="未选中模组",
                font=("Microsoft YaHei", 13, "bold"),
                text_color="#94a3b8"
            ).pack(pady=2)

            CTkLabel(
                empty_panel,
                text="在左侧列表中点击选择任意模组\n即可查看其快捷键指令与操作详情",
                font=("Microsoft YaHei", 10),
                text_color="#64748b",
                justify="center"
            ).pack(pady=4)
            return

        mod = self.selected_mod_item

        # 1. Contain-fit Large Preview Thumbnail
        preview_img = ModCard.get_thumbnail_image(self.image_cache, mod_item=mod, target_w=280, target_h=145)
        thumb_lbl = CTkLabel(
            self.inspector_scroll,
            text="",
            image=preview_img,
            width=280,
            height=145,
            corner_radius=8
        )
        thumb_lbl.pack(fill="x", padx=4, pady=(4, 6))

        # 2. Mod Title
        title_lbl = CTkLabel(
            self.inspector_scroll,
            text=mod.display_name,
            font=("Microsoft YaHei", 13, "bold"),
            text_color="#ffffff",
            anchor="w",
            wraplength=275,
            justify="left"
        )
        title_lbl.pack(fill="x", padx=6, pady=(2, 4))

        # 3. Badges Row (Character Tag + Status Tag)
        tags_frame = CTkFrame(self.inspector_scroll, fg_color="transparent")
        tags_frame.pack(fill="x", padx=4, pady=(2, 4))

        # Character Tag
        char_tag = CTkLabel(
            tags_frame,
            text=f"👤 {mod.character_name}",
            font=("Microsoft YaHei", 10, "bold"),
            text_color="#93c5fd",
            fg_color="#1e293b",
            corner_radius=6,
            padx=8,
            pady=2
        )
        char_tag.pack(side="left", padx=(0, 6))

        # Status Tag
        status_text = "✓ 已启用" if mod.enabled else "已禁用"
        status_bg = "#065f46" if mod.enabled else "#242b3d"
        status_color = "#34d399" if mod.enabled else "#94a3b8"
        status_tag = CTkLabel(
            tags_frame,
            text=status_text,
            font=("Microsoft YaHei", 10, "bold"),
            text_color=status_color,
            fg_color=status_bg,
            corner_radius=6,
            padx=8,
            pady=2
        )
        status_tag.pack(side="left")

        # 4. File Stats
        size_mb = mod.size_bytes / (1024 * 1024)
        size_str = f"{size_mb:.1f} MB" if size_mb >= 0.1 else f"{mod.size_bytes / 1024:.1f} KB"
        stats_lbl = CTkLabel(
            self.inspector_scroll,
            text=f"📁 {mod.file_count} 个文件 · 💾 {size_str}",
            font=("Microsoft YaHei", 10),
            text_color="#94a3b8",
            anchor="w"
        )
        stats_lbl.pack(fill="x", padx=6, pady=(0, 6))

        # Divider
        CTkFrame(self.inspector_scroll, height=1, fg_color="#242b3d").pack(fill="x", padx=4, pady=6)

        # 5. Hotkeys Header
        hk_count = len(mod.hotkeys)
        hk_header_frame = CTkFrame(self.inspector_scroll, fg_color="transparent")
        hk_header_frame.pack(fill="x", padx=4, pady=(2, 6))

        CTkLabel(
            hk_header_frame,
            text="⌨️ 模组快捷键指令",
            font=("Microsoft YaHei", 12, "bold"),
            text_color="#ffffff"
        ).pack(side="left")

        CTkLabel(
            hk_header_frame,
            text=f"{hk_count} 项",
            font=("Microsoft YaHei", 10, "bold"),
            text_color="#93c5fd",
            fg_color="#1e293b",
            corner_radius=6,
            padx=7,
            pady=1
        ).pack(side="right")

        # 6. Hotkeys List
        if mod.hotkeys:
            for hk in mod.hotkeys:
                hk_card = CTkFrame(
                    self.inspector_scroll,
                    fg_color="#181c28",
                    corner_radius=8,
                    border_width=1,
                    border_color="#283246"
                )
                hk_card.pack(fill="x", padx=4, pady=3)

                # Top Row: Key Chip + Type Badge
                top_row = CTkFrame(hk_card, fg_color="transparent")
                top_row.pack(fill="x", padx=8, pady=(6, 2))

                key_chip = CTkLabel(
                    top_row,
                    text=f" {hk.key_display} ",
                    font=("Consolas", 11, "bold"),
                    fg_color="#2563eb",
                    text_color="#ffffff",
                    corner_radius=4,
                    padx=6,
                    pady=2
                )
                key_chip.pack(side="left")

                type_chip = CTkLabel(
                    top_row,
                    text=hk.action_type,
                    font=("Microsoft YaHei", 9),
                    fg_color="#22283a",
                    text_color="#93c5fd",
                    corner_radius=4,
                    padx=5,
                    pady=1
                )
                type_chip.pack(side="right")

                # Action Title
                action_lbl = CTkLabel(
                    hk_card,
                    text=hk.action_name,
                    font=("Microsoft YaHei", 11, "bold"),
                    text_color="#f1f5f9",
                    anchor="w"
                )
                action_lbl.pack(fill="x", padx=8, pady=(2, 1))

                # Subtext (File / Variables / Values)
                sub_parts = [hk.ini_file]
                if hk.values:
                    sub_parts.append(f"值: {hk.values}")
                sub_text = " · ".join(sub_parts)

                detail_lbl = CTkLabel(
                    hk_card,
                    text=sub_text,
                    font=("Microsoft YaHei", 9),
                    text_color="#94a3b8",
                    anchor="w"
                )
                detail_lbl.pack(fill="x", padx=8, pady=(0, 6))
        else:
            no_hk_frame = CTkFrame(
                self.inspector_scroll,
                fg_color="#181c28",
                corner_radius=8,
                border_width=1,
                border_color="#283246"
            )
            no_hk_frame.pack(fill="x", padx=4, pady=4)

            CTkLabel(
                no_hk_frame,
                text="ℹ️ 该模组未配置独立快捷键\n（启用后由游戏全局自动加载生效）",
                font=("Microsoft YaHei", 10),
                text_color="#94a3b8",
                justify="center"
            ).pack(padx=8, pady=12)

        # Divider
        CTkFrame(self.inspector_scroll, height=1, fg_color="#262d3d").pack(fill="x", padx=4, pady=8)

        # 7. Quick Actions Toolbox
        actions_box = CTkFrame(self.inspector_scroll, fg_color="transparent")
        actions_box.pack(fill="x", padx=4, pady=(0, 10))

        # Main Toggle Button
        toggle_label = "✓ 启用此模组" if not mod.enabled else "✕ 禁用此模组"
        toggle_fg = "#2563eb" if not mod.enabled else "#334155"
        toggle_hover = "#1d4ed8" if not mod.enabled else "#475569"
        btn_toggle = CTkButton(
            actions_box,
            text=toggle_label,
            height=32,
            corner_radius=6,
            font=("Microsoft YaHei", 11, "bold"),
            fg_color=toggle_fg,
            hover_color=toggle_hover,
            command=lambda m=mod: self._toggle_mod(m)
        )
        btn_toggle.pack(fill="x", pady=(0, 4))

        # Secondary Actions Row (Open Folder + Repair Mod)
        sub_actions_row = CTkFrame(actions_box, fg_color="transparent")
        sub_actions_row.pack(fill="x", pady=2)

        btn_open = CTkButton(
            sub_actions_row,
            text="📂 打开目录",
            height=30,
            corner_radius=6,
            font=("Microsoft YaHei", 10),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#f1f5f9",
            command=lambda m=mod: os.startfile(str(m.path)) if m.path.exists() else None
        )
        btn_open.pack(side="left", fill="x", expand=True, padx=(0, 3))

        btn_repair = CTkButton(
            sub_actions_row,
            text="🔧 修复模组",
            height=30,
            corner_radius=6,
            font=("Microsoft YaHei", 10),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#f1f5f9",
            command=lambda m=mod: self._repair_mod(m)
        )
        btn_repair.pack(side="right", fill="x", expand=True, padx=(3, 0))

    def _toggle_mod(self, mod_item: ModItem):
        """Silently switches active mod within character category without dialogs."""
        success, new_item, msg, auto_disabled = ModService.toggle_mod(mod_item, auto_resolve_conflicts=True)
        if success:
            if self.selected_mod_item and self.selected_mod_item.path.resolve() == mod_item.path.resolve() and new_item:
                self.selected_mod_item = new_item
            self.refresh_mods()
        else:
            show_copyable_error("操作失败", f"切换模组状态失败:\n{msg}", parent=self.winfo_toplevel())

    def _repair_mod(self, mod_item: ModItem):
        """Opens interactive Mod Repair & Fix Options modal dialog for the selected mod."""
        self._open_repair_dialog(mod_item)

    def _open_repair_dialog(self, mod_item: Optional[ModItem] = None):
        """Opens interactive Mod Repair Dialog for either a single mod or full library batch."""
        all_mods_list = self.current_mods if self.current_mods else ModService.scan_mods()
        dialog = ModRepairDialog(
            parent=self.winfo_toplevel(),
            target_mod=mod_item,
            all_mods=all_mods_list,
            on_finished_callback=self.refresh_mods
        )

    def _open_hot_update_dialog(self):
        """Opens interactive Hot Update and Upstream Sync modal dialog."""
        from gui.windows.hot_update_dialog import HotUpdateDialog
        dialog = HotUpdateDialog(parent=self.winfo_toplevel())
        dialog.focus()

    def _restore_mod(self, mod_item: ModItem):
        """Restores mod to original pre-repair snapshot."""
        confirm = ask_confirm(
            "确认复原",
            f"确定要将模组【{mod_item.display_name}】还原至修复前的原始文件吗？\n\n此操作将完全恢复模组的初始文件。",
            parent=self.winfo_toplevel()
        )
        if confirm:
            success, msg = ModService.restore_mod(mod_item)
            if success:
                self.refresh_mods()
                show_info("复原成功", msg, parent=self.winfo_toplevel())
            else:
                show_warning("复原提示", msg, parent=self.winfo_toplevel())

    def _change_thumbnail(self, mod_item: ModItem):
        """Allows user to select and replace custom preview thumbnail."""
        file_path = filedialog.askopenfilename(
            title=f"选择【{mod_item.display_name}】的新预览图",
            filetypes=[
                ("图片文件 (*.png, *.jpg, *.jpeg, *.webp, *.bmp)", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                ("所有文件 (*.*)", "*.*")
            ]
        )
        if not file_path:
            return

        success, msg = ModService.set_custom_thumbnail(mod_item, Path(file_path))
        if success:
            # Clear cached CTkImage for this mod to force instant update
            if mod_item.thumbnail_path:
                self.image_cache.pop(str(mod_item.thumbnail_path), None)
            self.image_cache.pop(str(mod_item.path / "preview.png"), None)
            self.image_cache.pop(f"placeholder_{mod_item.name}", None)
            self.refresh_mods()
            show_info("修改成功", "模组预览图已成功更新！", parent=self.winfo_toplevel())
        else:
            show_copyable_error("修改失败", f"无法替换预览图:\n{msg}", parent=self.winfo_toplevel())

    def _rename_mod(self, mod_item: ModItem):
        """Renames mod with user input prompt."""
        dialog = ctk.CTkInputDialog(
            text=f"请输入模组【{mod_item.display_name}】的新名称：",
            title="重命名模组"
        )
        new_name = dialog.get_input()
        if new_name is None:
            return
        new_name = new_name.strip()
        if not new_name:
            return

        success, msg, new_item = ModService.rename_mod(mod_item, new_name)
        if success:
            self.refresh_mods()
        else:
            show_copyable_error("重命名失败", f"无法重命名模组:\n{msg}", parent=self.winfo_toplevel())

    def _delete_mod(self, mod_item: ModItem):
        confirm = ask_confirm(
            "确认删除",
            f"确定要彻底删除模组【{mod_item.display_name}】吗？\n此操作不可撤销！",
            parent=self.winfo_toplevel()
        )
        if confirm:
            success, msg = ModService.delete_mod(mod_item)
            if success:
                self.refresh_mods()
            else:
                show_copyable_error("删除失败", f"无法删除模组:\n{msg}", parent=self.winfo_toplevel())

    def _setup_drag_and_drop(self):
        """Attaches native drag-and-drop hook to the window."""
        if getattr(self, "_dnd_hooked", False):
            return
        try:
            self.update_idletasks()
            hook_drag_and_drop(self, self._handle_dropped_paths)
            self._dnd_hooked = True
            log.info("Drag and drop successfully attached to ModManagerFrame.")
        except Exception as e:
            log.warning(f"Failed to setup drag and drop: {e}")

    def _handle_dropped_paths(self, file_paths: List[str]):
        """Handles batch files/folders dropped directly onto the Mod Manager window."""
        valid_paths = []
        valid_exts = {'.zip', '.7z', '.rar', '.tar', '.gz', '.tgz', '.bz2', '.tbz2', '.xz', '.txz', '.zst'}
        for fp in file_paths:
            p = Path(fp)
            if p.exists():
                if p.is_dir():
                    valid_paths.append(p)
                elif p.is_file():
                    if p.suffix.lower() in valid_exts or '.tar.' in p.name.lower() or p.name.lower().endswith('.tar.zst'):
                        valid_paths.append(p)

        if not valid_paths:
            show_info("拖拽导入提示", "未检测到有效的模组压缩包（.zip / .7z / .rar / .tar 等）或文件夹。", parent=self.winfo_toplevel())
            return

        regular_paths = []
        for p in valid_paths:
            if self._is_wwmi_package_candidate(p):
                confirm = ask_confirm(
                    "导入 WWMI-Package 运行包",
                    f"检测到拖入的文件可能为 WWMI-Package 核心加载包：\n【{p.name}】\n\n是否立即将其部署至鸣潮 WWMI 运行环境？",
                    parent=self.winfo_toplevel()
                )
                if confirm:
                    from core.wwmi_importer import WWMIImporter
                    res = WWMIImporter.import_from_zip(p) if p.is_file() else WWMIImporter.import_from_folder(p)
                    if res.success:
                        show_info("导入成功", f"WWMI-Package 导入成功 (版本: v{res.version})", parent=self.winfo_toplevel())
                    else:
                        show_warning("导入提示", res.message, parent=self.winfo_toplevel())
                    continue
            regular_paths.append(p)

        if regular_paths:
            self._process_batch_import(regular_paths)

    @staticmethod
    def _is_wwmi_package_candidate(p: Path) -> bool:
        """Determines if a dropped path is a WWMI-Package archive or directory."""
        if "wwmi" not in p.name.lower():
            return False
        if p.is_dir():
            return (p / "Core" / "WWMI" / "WuWa-Model-Importer.ini").exists() or (p / "WWMI" / "Core").exists()
        if p.suffix.lower() == ".zip":
            try:
                import zipfile
                with zipfile.ZipFile(p, "r") as zf:
                    for name in zf.namelist()[:30]:
                        if "WuWa-Model-Importer.ini" in name or "Core/WWMI" in name:
                            return True
            except Exception:
                pass
        return False

    def _process_batch_import(self, paths: List[Path]):
        """Unified background batch importer for dropped files or selected archives/folders."""
        if not paths:
            return

        progress_dialog = ImportProgressDialog(self.winfo_toplevel(), title="正在批量导入模组")

        def request_password(archive_path: Path, archive_name: str) -> Optional[str]:
            """Thread-safe interactive password prompt modal dialog on the GUI thread."""
            result = {"pwd": None}
            event = threading.Event()

            def show():
                try:
                    PasswordPromptDialog(
                        parent=self.winfo_toplevel(),
                        archive_name=archive_name,
                        on_submit=lambda pwd: _finish(pwd),
                        on_cancel=lambda: _finish(None)
                    )
                except Exception as e:
                    log.error(f"Error opening PasswordPromptDialog: {e}")
                    _finish(None)

            def _finish(pwd):
                result["pwd"] = pwd
                event.set()

            self.after(0, show)
            event.wait()
            return result["pwd"]

        def worker():
            total = len(paths)
            imported_count = 0
            errors = []

            for i, p in enumerate(paths):
                path_obj = Path(p)
                progress_dialog.update_progress(
                    f"正在处理 ({i+1}/{total}): {path_obj.name}",
                    (i / total) + 0.05
                )

                def sub_progress(status_text: str, step_fraction: float):
                    current_overall = (i + step_fraction) / total
                    progress_dialog.update_progress(
                        f"[{i+1}/{total}] {status_text}",
                        current_overall
                    )

                success, msg = ModService.import_mod_from_path(
                    path_obj,
                    password_callback=request_password,
                    progress_callback=sub_progress
                )
                if success:
                    imported_count += 1
                else:
                    errors.append(f"{path_obj.name}: {msg}")

            progress_dialog.update_progress("全部完成！", 1.0)
            progress_dialog.finish_close()

            def finish_ui():
                self.refresh_mods()
                if errors:
                    err_summary = "\n".join(f"• {e}" for e in errors)
                    show_copyable_error(
                        "导入完成 (部分文件失败)",
                        f"成功导入 {imported_count}/{total} 个模组。\n\n失败详情（可自由框选复制）：\n{err_summary}",
                        parent=self.winfo_toplevel()
                    )
                else:
                    show_info(
                        "导入成功",
                        f"🎉 成功导入全部 {imported_count} 个模组并已就绪！",
                        parent=self.winfo_toplevel()
                    )

            self.after(200, finish_ui)

        threading.Thread(target=worker, daemon=True, name="BatchModImporter").start()

    def _import_archive(self):
        file_paths = filedialog.askopenfilenames(
            title="选择模组压缩包",
            filetypes=[
                ("所有支持的压缩包 (*.zip, *.7z, *.rar, *.tar, *.gz, *.zst...)", "*.zip *.7z *.rar *.tar *.gz *.tgz *.bz2 *.tbz2 *.xz *.txz *.zst"),
                ("ZIP 文件 (*.zip)", "*.zip"),
                ("7Z 压缩包 (*.7z)", "*.7z"),
                ("RAR 压缩包 (*.rar)", "*.rar"),
                ("所有文件 (*.*)", "*.*")
            ]
        )
        if file_paths:
            self._process_batch_import([Path(p) for p in file_paths])

    def _import_folder(self):
        folder_path = filedialog.askdirectory(title="选择要导入的模组文件夹")
        if folder_path:
            self._process_batch_import([Path(folder_path)])

    def _open_mods_folder(self):
        mods_folder = ModService.get_active_mods_folder()
        if mods_folder and mods_folder.exists():
            os.startfile(str(mods_folder))
        else:
            show_warning("提示", "未找到 Mods 目录", parent=self.winfo_toplevel())

    def _open_gamebanana_browser(self):
        """Opens the integrated GameBanana Mod Download Center window."""
        mods_folder = ModService.get_active_mods_folder()
        if not mods_folder or not mods_folder.exists():
            show_warning(
                "无法打开模组下载站",
                "未找到当前游戏的 Mods 目录！请先确保在启动器中正确配置了游戏路径与模组加载器。",
                parent=self.winfo_toplevel()
            )
            return

        # Check if browser process is already alive
        if hasattr(self, '_gamebanana_proc') and self._gamebanana_proc and self._gamebanana_proc.poll() is None:
            try:
                import win32gui, win32con
                def enum_handler(hwnd, extra):
                    if win32gui.IsWindowVisible(hwnd) and "GameBanana" in win32gui.GetWindowText(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                win32gui.EnumWindows(enum_handler, None)
            except Exception:
                pass
            return

        try:
            app_root = Paths.App.Root
        except Exception:
            app_root = Path.cwd()

        download_dir = app_root / "Downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        cache_dir = app_root / "UserData" / "GameBananaBrowser"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Determine initial GameBanana URL according to active game importer
        try:
            from core.config_manager import Config
            active_importer = getattr(Config.Launcher, "active_importer", "WWMI")
        except Exception:
            active_importer = "WWMI"

        gamebanana_urls = {
            'WWMI': 'https://gamebanana.com/games/20357',  # 鸣潮
            'ZZMI': 'https://gamebanana.com/games/18951',  # 绝区零
            'SRMI': 'https://gamebanana.com/games/18261',  # 崩铁
            'GIMI': 'https://gamebanana.com/games/8552',   # 原神
            'HIMI': 'https://gamebanana.com/games/15446',  # 崩坏3
        }
        initial_url = gamebanana_urls.get(active_importer, "https://gamebanana.com/games/20357")

        cmd = [sys.executable]

        if getattr(sys, 'frozen', False):
            cmd.extend([
                '--gamebanana-browser',
                '--mods-dir', str(mods_folder),
                '--download-dir', str(download_dir),
                '--cache-dir', str(cache_dir),
                '--initial-url', str(initial_url),
                '--parent-pid', str(os.getpid())
            ])
        else:
            browser_script = Path(__file__).resolve().parent.parent.parent / "gamebanana_browser.py"
            if not browser_script.exists():
                browser_script = app_root / "src" / "xxmi_launcher" / "gui" / "windows" / "gamebanana_browser.py"

            cmd.extend([
                str(browser_script),
                '--mods-dir', str(mods_folder),
                '--download-dir', str(download_dir),
                '--cache-dir', str(cache_dir),
                '--initial-url', str(initial_url),
                '--parent-pid', str(os.getpid())
            ])

        try:
            self._gamebanana_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1
            )
        except Exception as e:
            show_copyable_error(
                "启动下载中心失败",
                f"启动 GameBanana 模组下载中心遇到异常：\n{e}",
                parent=self.winfo_toplevel()
            )
            return

        # Start background listener thread to handle auto-importing completed downloads
        def listener():
            try:
                for line in self._gamebanana_proc.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        event = data.get("event")
                        if event == "download_complete":
                            file_path = data.get("file_path")
                            if file_path and Path(file_path).exists():
                                self._handle_gamebanana_downloaded_mod(Path(file_path))
                    except Exception as err:
                        log.debug(f"JSON event parse error: {err}")
            except Exception as e:
                log.debug(f"GameBanana listener loop error: {e}")

        def stderr_drain():
            try:
                for line in self._gamebanana_proc.stderr:
                    log.debug(f"[GameBananaBrowser] {line.strip()}")
            except Exception:
                pass

        threading.Thread(target=listener, daemon=True, name="GameBananaListener").start()
        threading.Thread(target=stderr_drain, daemon=True, name="GameBananaStderrDrain").start()

    def _handle_gamebanana_downloaded_mod(self, file_path: Path):
        """Automatically imports a mod downloaded via GameBanana browser and refreshes the UI."""
        def request_password(archive_path: Path, archive_name: str) -> Optional[str]:
            result = {"pwd": None}
            event = threading.Event()

            def show():
                try:
                    PasswordPromptDialog(
                        parent=self.winfo_toplevel(),
                        archive_name=archive_name,
                        on_submit=lambda pwd: _finish(pwd),
                        on_cancel=lambda: _finish(None)
                    )
                except Exception as e:
                    log.error(f"Error opening PasswordPromptDialog: {e}")
                    _finish(None)

            def _finish(pwd):
                result["pwd"] = pwd
                event.set()

            self.after(0, show)
            event.wait()
            return result["pwd"]

        def worker():
            success, msg = ModService.import_mod_from_path(
                file_path,
                password_callback=request_password
            )

            # Reply to browser process
            if hasattr(self, '_gamebanana_proc') and self._gamebanana_proc and self._gamebanana_proc.poll() is None:
                try:
                    reply = json.dumps({
                        "action": "import_result",
                        "success": success,
                        "file_path": str(file_path),
                        "message": msg
                    }, ensure_ascii=False) + "\n"
                    self._gamebanana_proc.stdin.write(reply)
                    self._gamebanana_proc.stdin.flush()
                except Exception:
                    pass

            def finish():
                self.refresh_mods()
                if success:
                    show_info(
                        "模组自动下载并安装成功",
                        f"🎉 成功从 GameBanana 下载并安装模组：\n\n【{file_path.stem}】\n\n模组已就绪并在列表中显示！",
                        parent=self.winfo_toplevel()
                    )
                else:
                    show_copyable_error(
                        "模组导入失败",
                        f"模组文件已下载，但在解压导入时失败：\n\n{msg}",
                        parent=self.winfo_toplevel()
                    )

            self.after(100, finish)

        threading.Thread(target=worker, daemon=True, name="GameBananaModImporter").start()

    def _center_window(self):
        """Centers the window on the active monitor screen."""
        try:
            self.update_idletasks()
            w = 1240
            h = 740
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2 - 20)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def open_mod_manager(self):
        """Opens, restores, and focuses the mod manager window."""
        if not self._initial_centered:
            self._center_window()
            self._initial_centered = True
        self.deiconify()
        if self.state() == 'iconic':
            self.state('normal')
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(150, lambda: self.attributes("-topmost", False))
        self.after(50, lambda: apply_dwm_window_theme(self, caption_hex="#161924", border_hex="#232c3d"))
        self._setup_drag_and_drop()
        self.refresh_mods()

    def close_mod_manager(self):
        """Hides/withdraws the mod manager window."""
        self.withdraw()
        if self.on_close_callback and callable(self.on_close_callback):
            self.on_close_callback()

    def _hide(self):
        """Do not automatically withdraw the top-level window when parent launcher frame hides."""
        pass

    def _show(self):
        pass

    def unsubscribe(self, *args, **kwargs):
        """Lifecycle unsubscribe."""
        pass

    def untrace_save(self, *args, **kwargs):
        """Lifecycle untrace_save."""
        pass

    def untrace_write(self, *args, **kwargs):
        """Lifecycle untrace_write."""
        pass

