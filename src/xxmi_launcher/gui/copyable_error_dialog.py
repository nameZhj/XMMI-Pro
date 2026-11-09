"""
@file copyable_error_dialog.py
@brief Dark-themed copyable error dialog with re-exported modal dialog helpers
@exports CopyableErrorDialog, show_copyable_error, show_warning, show_info, ask_confirm, ModernModalDialog
"""
import sys
import threading
import tkinter as tk
import customtkinter as ctk
from typing import Optional

from gui.modern_dialogs import show_warning, show_info, ask_confirm, ModernModalDialog

__all__ = [
    "CopyableErrorDialog",
    "show_copyable_error",
    "show_warning",
    "show_info",
    "ask_confirm",
    "ModernModalDialog",
]


class CopyableErrorDialog(ctk.CTkToplevel):
    """
    Modern dark-themed Error Dialog with freely selectable, copyable text,
    one-click copy button, and right-click context menu.
    """
    def __init__(self, title: str, message: str, parent=None, is_fatal: bool = False):
        if parent is None:
            super().__init__()
        else:
            super().__init__(parent)
        self.parent_window = parent

        self.title(title)
        self.geometry("640x440")
        self.minsize(520, 320)
        self.configure(fg_color="#131620")

        self.full_message = str(message).strip()
        self.is_fatal = is_fatal

        top_parent = None
        if parent is not None:
            try:
                top_parent = parent.winfo_toplevel()
            except Exception:
                top_parent = parent

        if top_parent is not None:
            try:
                self.transient(top_parent)
                self.grab_set()
            except Exception:
                pass

        # Center on screen
        self.update_idletasks()
        try:
            target = top_parent if top_parent is not None else parent
            if target is not None:
                px = target.winfo_rootx()
                py = target.winfo_rooty()
                pw = target.winfo_width()
                ph = target.winfo_height()
                x = px + (pw - 640) // 2
                y = py + (ph - 440) // 2
            else:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = max(0, (sw - 640) // 2)
                y = max(0, (sh - 440) // 2 - 20)
            self.geometry(f"640x440+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self._build_ui(title)

    def _build_ui(self, title: str):
        # 1. Header Bar
        header = ctk.CTkFrame(self, fg_color="#1a1e2b", corner_radius=10, height=48)
        header.pack(fill="x", padx=16, pady=(16, 10))
        header.pack_propagate(False)

        icon_lbl = ctk.CTkLabel(header, text="❌" if self.is_fatal else "⚠️", font=("Segoe UI Emoji", 18))
        icon_lbl.pack(side="left", padx=(14, 6))

        title_lbl = ctk.CTkLabel(
            header,
            text=title,
            font=("Microsoft YaHei", 13, "bold"),
            text_color="#f87171" if self.is_fatal else "#fbbf24",
            anchor="w"
        )
        title_lbl.pack(side="left", fill="x", expand=True, padx=4)

        hint_lbl = ctk.CTkLabel(
            header,
            text="（支持鼠标自由框选/右键/复制）",
            font=("Microsoft YaHei", 10),
            text_color="#94a3b8"
        )
        hint_lbl.pack(side="right", padx=14)

        # 2. Textbox Area (Freely selectable, scrollable)
        text_frame = ctk.CTkFrame(self, fg_color="#0e111a", corner_radius=8, border_width=1, border_color="#242b3d")
        text_frame.pack(fill="both", expand=True, padx=16, pady=4)

        self.textbox = ctk.CTkTextbox(
            text_frame,
            fg_color="transparent",
            text_color="#e2e8f0",
            font=("Consolas", 11),
            wrap="word",
            activate_scrollbars=True
        )
        self.textbox.pack(fill="both", expand=True, padx=8, pady=8)
        self.textbox.insert("1.0", self.full_message)
        self.textbox.configure(state="disabled")

        # Context Menu for right-click on textbox
        self.context_menu = tk.Menu(
            self,
            tearoff=0,
            bg="#1e2433",
            fg="#ffffff",
            activebackground="#2563eb",
            activeforeground="#ffffff",
            font=("Microsoft YaHei", 10)
        )
        self.context_menu.add_command(label="📋 复制选中文字 (Ctrl+C)", command=self._copy_selected_text)
        self.context_menu.add_command(label="📑 全选 (Ctrl+A)", command=self._select_all_text)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📦 复制全部报错内容", command=self._copy_all_text)

        # Bind events
        self.textbox.bind("<Button-3>", self._show_context_menu)
        self.bind("<Control-c>", lambda e: self._copy_selected_text())
        self.bind("<Control-C>", lambda e: self._copy_selected_text())
        self.bind("<Control-a>", lambda e: self._select_all_text())
        self.bind("<Control-A>", lambda e: self._select_all_text())
        self.bind("<Escape>", lambda e: self._on_close())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # 3. Bottom Action Bar
        bottom_bar = ctk.CTkFrame(self, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=16, pady=(10, 16))

        self.copy_all_btn = ctk.CTkButton(
            bottom_bar,
            text="📋 一键复制全部报错信息",
            font=("Microsoft YaHei", 11, "bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=36,
            corner_radius=8,
            command=self._copy_all_text
        )
        self.copy_all_btn.pack(side="left")

        self.feedback_lbl = ctk.CTkLabel(
            bottom_bar,
            text="",
            font=("Microsoft YaHei", 11, "bold"),
            text_color="#4ade80"
        )
        self.feedback_lbl.pack(side="left", padx=12)

        self.ok_btn = ctk.CTkButton(
            bottom_bar,
            text="确定并关闭",
            width=110,
            font=("Microsoft YaHei", 11),
            fg_color="#242b3d",
            hover_color="#333d54",
            border_width=1,
            border_color="#3b475f",
            text_color="#ffffff",
            height=36,
            corner_radius=8,
            command=self._on_close
        )
        self.ok_btn.pack(side="right")

    def _show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _copy_selected_text(self):
        try:
            selected = self.textbox.get("sel.first", "sel.last")
            if selected:
                self.clipboard_clear()
                self.clipboard_append(selected)
                self._show_feedback("✅ 已复制选中文字！")
                return
        except Exception:
            pass
        self._copy_all_text()

    def _select_all_text(self):
        try:
            self.textbox.tag_add("sel", "1.0", "end")
        except Exception:
            pass

    def _copy_all_text(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.full_message)
            self._show_feedback("✅ 已复制全部报错信息到剪贴板！")
        except Exception as e:
            self._show_feedback(f"复制失败: {e}")

    def _show_feedback(self, text: str):
        self.feedback_lbl.configure(text=text)
        self.after(2500, lambda: self.feedback_lbl.configure(text=""))

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        if self.parent_window is not None:
            try:
                top = getattr(self.parent_window, "winfo_toplevel", lambda: self.parent_window)()
                top.lift()
                top.focus_force()
            except Exception:
                pass


def show_copyable_error(title: str, message: str, parent=None, is_fatal: bool = False):
    """
    Shows a copyable error modal dialog. Works in standalone mode or on top of parent window.
    Thread-safe: dispatches to main thread if called from worker threads.
    """
    def _run():
        created_root = False
        root = parent
        if root is None:
            try:
                root = ctk._get_default_root()
            except Exception:
                root = None
            if root is None:
                root = ctk.CTk()
                root.withdraw()
                created_root = True

        dlg = CopyableErrorDialog(
            title=title,
            message=message,
            parent=root if not created_root else None,
            is_fatal=is_fatal
        )
        if created_root:
            root.mainloop()
        else:
            dlg.wait_window()

    if threading.current_thread() == threading.main_thread():
        _run()
    else:
        root = None
        if parent is not None and hasattr(parent, "winfo_toplevel"):
            try:
                root = parent.winfo_toplevel()
            except Exception:
                pass
        if root is None:
            try:
                root = ctk._get_default_root()
            except Exception:
                root = None
        if root and hasattr(root, "after"):
            evt = threading.Event()
            def _runner():
                try:
                    _run()
                finally:
                    evt.set()
            root.after(0, _runner)
            evt.wait()
        else:
            _run()
