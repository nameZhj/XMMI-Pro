import os
import io
import shutil
import threading
import logging
from pathlib import Path
from typing import Optional, List, Dict

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
    CTkToplevel
)
from PIL import Image, ImageDraw
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

from gui.classes.element import UIElementBase
from core.mod_service import ModService, ModItem, CharacterMenuItem
from core.locale_manager import L

log = logging.getLogger(__name__)


class ImportProgressDialog(ctk.CTkToplevel):
    """Modern modal progress dialog during mod import & archive extraction."""
    def __init__(self, parent, title="正在导入模组"):
        super().__init__(parent)
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

        # High-contrast card border & background
        if is_selected:
            bg_color = "#1d263b"
            border_color = "#60a5fa"
            border_w = 2
        elif mod_item.enabled:
            bg_color = "#182030"
            border_color = "#3b82f6"
            border_w = 2
        else:
            bg_color = "#141722"
            border_color = "#283042"
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

        self.title("模组管理 - XXMI Launcher")
        self.overrideredirect(True)
        self.geometry("1240x740")
        self.configure(fg_color="#0f1117")

        self.is_maximized = False
        self._prev_w = 1240
        self._prev_h = 740
        self._prev_x = 100
        self._prev_y = 100
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._resize_start_x = 0
        self._resize_start_y = 0
        self._resize_start_w = 1240
        self._resize_start_h = 740
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
        # 1. Top Window Title Bar (Single Clean Custom Draggable Header)
        self.title_bar = CTkFrame(self, height=48, fg_color="#161924", corner_radius=10, border_width=1, border_color="#262d3d")
        self.title_bar.pack(fill="x", padx=12, pady=(10, 6))
        self.title_bar.pack_propagate(False)

        self.title_icon = CTkLabel(
            self.title_bar,
            text="📦",
            font=("Segoe UI Emoji", 16)
        )
        self.title_icon.pack(side="left", padx=(14, 4))

        self.title_label = CTkLabel(
            self.title_bar,
            text="模组管理",
            font=("Microsoft YaHei", 15, "bold"),
            text_color="#ffffff"
        )
        self.title_label.pack(side="left", padx=4)

        self.stats_label = CTkLabel(
            self.title_bar,
            text="正在扫描模组...",
            font=("Microsoft YaHei", 11),
            text_color="#cbd5e1"
        )
        self.stats_label.pack(side="left", padx=16)

        # Window Controls Container (Minimize, Maximize/Restore, Close)
        self.window_controls = CTkFrame(self.title_bar, fg_color="transparent")
        self.window_controls.pack(side="right", padx=(0, 8))

        # Minimize Button [一]
        self.min_btn = CTkButton(
            self.window_controls,
            text="一",
            width=32,
            height=32,
            corner_radius=6,
            font=("Segoe UI", 11, "bold"),
            fg_color="transparent",
            hover_color="#273248",
            text_color="#cbd5e1",
            command=self.minimize_mod_manager
        )
        self.min_btn.pack(side="left", padx=2)

        # Maximize / Restore Button [🗖]
        self.max_btn = CTkButton(
            self.window_controls,
            text="🗖",
            width=32,
            height=32,
            corner_radius=6,
            font=("Segoe UI", 12, "bold"),
            fg_color="transparent",
            hover_color="#273248",
            text_color="#cbd5e1",
            command=self._toggle_maximize
        )
        self.max_btn.pack(side="left", padx=2)

        # Close Button [✕]
        self.close_btn = CTkButton(
            self.window_controls,
            text="✕",
            width=32,
            height=32,
            corner_radius=6,
            font=("Segoe UI", 12, "bold"),
            fg_color="transparent",
            hover_color="#dc2626",
            text_color="#f1f5f9",
            command=self.close_mod_manager
        )
        self.close_btn.pack(side="left", padx=2)

        # Titlebar Dragging & Double Click Maximize Handlers
        for widget in (self.title_bar, self.title_icon, self.title_label, self.stats_label):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)
        self.title_bar.bind("<Double-Button-1>", lambda e: self._toggle_maximize())
        self.title_label.bind("<Double-Button-1>", lambda e: self._toggle_maximize())

        # Bottom-Right Corner Resize Grip
        self.resize_grip = CTkLabel(
            self,
            text="◢",
            font=("Segoe UI", 11),
            text_color="#475569",
            cursor="size_nw_se"
        )
        self.resize_grip.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)
        self.resize_grip.bind("<Button-1>", self._start_resize)
        self.resize_grip.bind("<B1-Motion>", self._on_resize)

        # 2. Main Horizontal Container (Left Sidebar + Center Cards Panel + Right Hotkey Inspector)
        self.body_container = CTkFrame(self, fg_color="transparent")
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
            border_color="#222838"
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
            border_color="#222838"
        )
        self.inspector_panel.pack(side="right", fill="y", padx=(8, 0), pady=0)
        self.inspector_panel.pack_propagate(False)

        # Inspector Header Bar
        self.inspector_header = CTkFrame(self.inspector_panel, height=44, fg_color="#161924", corner_radius=8, border_width=1, border_color="#262d3d")
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
        # CENTER MAIN PANEL: Mod Grid & Header
        # ==========================================
        self.right_panel = CTkFrame(
            self.body_container,
            fg_color="#131620",
            corner_radius=10,
            border_width=1,
            border_color="#222838"
        )
        self.right_panel.pack(side="left", fill="both", expand=True, padx=0, pady=0)
        self.right_panel.pack_propagate(False)

        # Center Header / Actions Bar
        self.header_bar = CTkFrame(self.right_panel, height=52, fg_color="#161924", corner_radius=8, border_width=1, border_color="#262d3d")
        self.header_bar.pack(fill="x", padx=10, pady=(10, 8))
        self.header_bar.pack_propagate(False)

        # Category Title Indicator
        self.current_category_label = CTkLabel(
            self.header_bar,
            text="🌟 全部模组",
            font=("Microsoft YaHei", 14, "bold"),
            text_color="#ffffff"
        )
        self.current_category_label.pack(side="left", padx=14)

        # State Filter Segment (全部 / 已启用 / 已禁用)
        self.state_filter_seg = CTkSegmentedButton(
            self.header_bar,
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
        self.state_filter_seg.pack(side="left", padx=10)

        # Action Buttons (Import Archive, Import Folder, Open Explorer, Refresh)
        self.actions_frame = CTkFrame(self.header_bar, fg_color="transparent")
        self.actions_frame.pack(side="right", padx=8)

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

        # Mod Scrollable Cards Grid Frame
        self.scroll_frame = CTkScrollableFrame(
            self.right_panel,
            fg_color="transparent",
            corner_radius=8
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=(10, 14), pady=(0, 10))
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
                text="您可以点击右上角的【📦 导入压缩包】或【📁 导入文件夹】将 Mod 导入此分类",
                font=("Microsoft YaHei", 11),
                text_color="#64748b"
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
                        child.configure(border_color="#60a5fa", border_width=2, fg_color="#1d263b")
                    elif child.mod_item.enabled:
                        child.configure(border_color="#3b82f6", border_width=2, fg_color="#182030")
                    else:
                        child.configure(border_color="#283042", border_width=1, fg_color="#141722")

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
            messagebox.showerror("操作失败", f"切换模组状态失败: {msg}")

    def _repair_mod(self, mod_item: ModItem):
        """Repairs mod syntax, ini encodings, nested directories, trash files, and Engine.ini."""
        success, fixes = ModService.repair_mod(mod_item)
        if success:
            fixes_text = "\n".join([f"• {f}" for f in fixes])
            messagebox.showinfo(
                "模组修复完成",
                f"已对模组【{mod_item.display_name}】完成自动化检测与修复：\n\n{fixes_text}"
            )
            self.refresh_mods()
        else:
            err_text = "\n".join(fixes)
            messagebox.showerror("修复失败", f"修复模组时出错：\n{err_text}")

    def _restore_mod(self, mod_item: ModItem):
        """Restores mod to original pre-repair snapshot."""
        confirm = messagebox.askyesno(
            "确认复原",
            f"确定要将模组【{mod_item.display_name}】还原至修复前的原始文件吗？\n\n此操作将完全恢复模组的初始文件。"
        )
        if confirm:
            success, msg = ModService.restore_mod(mod_item)
            if success:
                self.refresh_mods()
                messagebox.showinfo("复原成功", msg)
            else:
                messagebox.showwarning("复原提示", msg)

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
            messagebox.showinfo("修改成功", "模组预览图已成功更新！")
        else:
            messagebox.showerror("修改失败", f"无法替换预览图: {msg}")

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
            messagebox.showerror("重命名失败", msg)

    def _delete_mod(self, mod_item: ModItem):
        confirm = messagebox.askyesno(
            "确认删除",
            f"确定要彻底删除模组【{mod_item.display_name}】吗？\n此操作不可撤销！"
        )
        if confirm:
            success, msg = ModService.delete_mod(mod_item)
            if success:
                self.refresh_mods()
            else:
                messagebox.showerror("删除失败", f"无法删除模组: {msg}")

    def _import_archive(self):
        file_paths = filedialog.askopenfilenames(
            title="选择模组压缩包",
            filetypes=[
                ("模组压缩包 (*.zip, *.7z, *.rar, *.tar.gz)", "*.zip *.7z *.rar *.tar *.gz *.tgz"),
                ("ZIP 文件 (*.zip)", "*.zip"),
                ("7Z 压缩包 (*.7z)", "*.7z"),
                ("RAR 压缩包 (*.rar)", "*.rar"),
                ("所有文件 (*.*)", "*.*")
            ]
        )
        if not file_paths:
            return

        progress_dialog = ImportProgressDialog(self, title="正在导入模组压缩包")

        def worker():
            total = len(file_paths)
            imported_count = 0
            errors = []

            for i, fp in enumerate(file_paths):
                path_obj = Path(fp)
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

                success, msg = ModService.import_mod_from_path(path_obj, progress_callback=sub_progress)
                if success:
                    imported_count += 1
                else:
                    errors.append(f"{path_obj.name}: {msg}")

            progress_dialog.update_progress("全部完成！", 1.0)
            progress_dialog.finish_close()

            def finish_ui():
                self.refresh_mods()
                if errors:
                    err_summary = "\n".join(errors[:5])
                    if len(errors) > 5:
                        err_summary += f"\n...及其他 {len(errors)-5} 个错误"
                    messagebox.showwarning(
                        "导入完成 (部分失败)",
                        f"成功导入 {imported_count}/{total} 个模组。\n\n失败详情:\n{err_summary}"
                    )
                else:
                    messagebox.showinfo("导入成功", f"已成功解压并导入 {imported_count} 个模组！")

            self.after(200, finish_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _import_folder(self):
        folder_path = filedialog.askdirectory(title="选择要导入的模组文件夹")
        if not folder_path:
            return

        path_obj = Path(folder_path)
        progress_dialog = ImportProgressDialog(self, title="正在导入模组文件夹")

        def worker():
            def sub_progress(status_text: str, fraction: float):
                progress_dialog.update_progress(status_text, fraction)

            success, msg = ModService.import_mod_from_path(path_obj, progress_callback=sub_progress)
            progress_dialog.finish_close()

            def finish_ui():
                self.refresh_mods()
                if success:
                    messagebox.showinfo("导入成功", msg)
                else:
                    messagebox.showerror("导入失败", msg)

            self.after(200, finish_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _open_mods_folder(self):
        mods_folder = ModService.get_active_mods_folder()
        if mods_folder and mods_folder.exists():
            os.startfile(str(mods_folder))
        else:
            messagebox.showwarning("提示", "未找到 Mods 目录")

    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        if self.is_maximized:
            self._toggle_maximize()
        deltax = event.x - self._drag_start_x
        deltay = event.y - self._drag_start_y
        new_x = self.winfo_x() + deltax
        new_y = self.winfo_y() + deltay
        self.geometry(f"+{new_x}+{new_y}")

    def minimize_mod_manager(self):
        """Minimizes/hides the mod manager window."""
        self.withdraw()

    def _toggle_maximize(self):
        """Toggles between maximized and restored normal window state."""
        if not self.is_maximized:
            self._prev_w = self.winfo_width()
            self._prev_h = self.winfo_height()
            self._prev_x = self.winfo_x()
            self._prev_y = self.winfo_y()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight() - 40
            self.geometry(f"{sw}x{sh}+0+0")
            self.is_maximized = True
            self.max_btn.configure(text="❐")
        else:
            prev_w = getattr(self, "_prev_w", 1240)
            prev_h = getattr(self, "_prev_h", 740)
            prev_x = getattr(self, "_prev_x", 100)
            prev_y = getattr(self, "_prev_y", 100)
            self.geometry(f"{prev_w}x{prev_h}+{prev_x}+{prev_y}")
            self.is_maximized = False
            self.max_btn.configure(text="🗖")

    def _start_resize(self, event):
        """Records initial coordinates and dimensions when user begins dragging resize grip."""
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.winfo_width()
        self._resize_start_h = self.winfo_height()

    def _on_resize(self, event):
        """Calculates and applies new geometry as user drags resize grip."""
        if self.is_maximized:
            self.is_maximized = False
            self.max_btn.configure(text="🗖")
        delta_w = event.x_root - self._resize_start_x
        delta_h = event.y_root - self._resize_start_y
        new_w = max(960, self._resize_start_w + delta_w)
        new_h = max(600, self._resize_start_h + delta_h)
        self.geometry(f"{new_w}x{new_h}")

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
        self.refresh_mods()

    def close_mod_manager(self):
        """Hides/withdraws the mod manager window."""
        self.withdraw()
        if self.on_close_callback and callable(self.on_close_callback):
            self.on_close_callback()

    def _hide(self):
        self.withdraw()

    def _show(self):
        self.open_mod_manager()

    def unsubscribe(self, *args, **kwargs):
        """Lifecycle unsubscribe."""
        pass

    def untrace_save(self, *args, **kwargs):
        """Lifecycle untrace_save."""
        pass

    def untrace_write(self, *args, **kwargs):
        """Lifecycle untrace_write."""
        pass
