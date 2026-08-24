"""
Modern Dark-Themed Modal Dialogs for XMMI Pro.
Prevents parent window focus loss or falling behind other windows on close.
"""
import sys
import tkinter as tk
import customtkinter as ctk
from typing import Optional


class ModernModalDialog(ctk.CTkToplevel):
    def __init__(self, title: str, message: str, parent=None, dialog_type: str = "info"):
        super().__init__(parent)
        self.parent_window = parent

        self.title(title)
        self.geometry("460x220")
        self.resizable(False, False)
        self.configure(fg_color="#131620")

        self.result = False
        self.dialog_type = dialog_type  # "info", "warning", "confirm"

        if parent is not None:
            try:
                self.transient(parent)
                self.grab_set()
            except Exception:
                pass

        # Center on parent or screen
        self.update_idletasks()
        try:
            if parent is not None:
                px = parent.winfo_rootx()
                py = parent.winfo_rooty()
                pw = parent.winfo_width()
                ph = parent.winfo_height()
                x = px + (pw - 460) // 2
                y = py + (ph - 220) // 2
            else:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = (sw - 460) // 2
                y = (sh - 220) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        self._build_ui(title, message)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.bind("<Return>", lambda e: self._on_ok())

    def _build_ui(self, title: str, message: str):
        # 1. Header Bar
        header = ctk.CTkFrame(self, fg_color="#1a1e2b", corner_radius=8, height=44)
        header.pack(fill="x", padx=16, pady=(16, 8))
        header.pack_propagate(False)

        if self.dialog_type == "confirm":
            icon_char = "❓"
            title_color = "#60a5fa"
        elif self.dialog_type == "warning":
            icon_char = "⚠️"
            title_color = "#fbbf24"
        else:
            icon_char = "ℹ️"
            title_color = "#38bdf8"

        icon_lbl = ctk.CTkLabel(header, text=icon_char, font=("Segoe UI Emoji", 16))
        icon_lbl.pack(side="left", padx=(12, 6))

        title_lbl = ctk.CTkLabel(
            header,
            text=title,
            font=("Microsoft YaHei", 12, "bold"),
            text_color=title_color,
            anchor="w"
        )
        title_lbl.pack(side="left", fill="x", expand=True, padx=4)

        # 2. Content Message
        msg_frame = ctk.CTkFrame(self, fg_color="transparent")
        msg_frame.pack(fill="both", expand=True, padx=20, pady=(4, 10))

        msg_lbl = ctk.CTkLabel(
            msg_frame,
            text=str(message).strip(),
            font=("Microsoft YaHei", 11),
            text_color="#e2e8f0",
            anchor="center",
            justify="center",
            wraplength=410
        )
        msg_lbl.pack(expand=True)

        # 3. Action Buttons
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=16, pady=(0, 16))

        if self.dialog_type == "confirm":
            btn_no = ctk.CTkButton(
                btn_bar,
                text="取消",
                width=100,
                height=34,
                corner_radius=6,
                font=("Microsoft YaHei", 11),
                fg_color="#242b3d",
                hover_color="#333d54",
                border_width=1,
                border_color="#3b475f",
                text_color="#94a3b8",
                command=self._on_cancel
            )
            btn_no.pack(side="right", padx=(8, 0))

            btn_yes = ctk.CTkButton(
                btn_bar,
                text="确定",
                width=110,
                height=34,
                corner_radius=6,
                font=("Microsoft YaHei", 11, "bold"),
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                text_color="#ffffff",
                command=self._on_ok
            )
            btn_yes.pack(side="right")
        else:
            btn_ok = ctk.CTkButton(
                btn_bar,
                text="确定",
                width=120,
                height=34,
                corner_radius=6,
                font=("Microsoft YaHei", 11, "bold"),
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                text_color="#ffffff",
                command=self._on_ok
            )
            btn_ok.pack(side="right")

    def _on_ok(self):
        self.result = True
        self._dismiss()

    def _on_cancel(self):
        self.result = False
        self._dismiss()

    def _dismiss(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

        # Lift and refocus parent window so it NEVER falls behind
        if self.parent_window is not None:
            try:
                self.parent_window.lift()
                self.parent_window.focus_force()
            except Exception:
                pass


def show_info(title: str, message: str, parent=None):
    """Shows modern info popup without losing parent focus."""
    dlg = ModernModalDialog(title=title, message=message, parent=parent, dialog_type="info")
    dlg.wait_window()


def show_warning(title: str, message: str, parent=None):
    """Shows modern warning popup without losing parent focus."""
    dlg = ModernModalDialog(title=title, message=message, parent=parent, dialog_type="warning")
    dlg.wait_window()


def ask_confirm(title: str, message: str, parent=None) -> bool:
    """Shows modern confirmation dialog, returning True if confirmed, False otherwise."""
    dlg = ModernModalDialog(title=title, message=message, parent=parent, dialog_type="confirm")
    dlg.wait_window()
    return getattr(dlg, "result", False)
