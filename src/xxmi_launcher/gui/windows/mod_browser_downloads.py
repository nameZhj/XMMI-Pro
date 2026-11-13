"""
@file: src/xxmi_launcher/gui/windows/mod_browser_downloads.py
@brief: WebView2 DownloadStarting interceptor, progress reporter, and standalone importer.
@exports: ModBrowserDownloadHandler, sanitize_filename
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

log = logging.getLogger("ModBrowserDownloads")


def sanitize_filename(name: str) -> str:
    """Sanitizes filename for Windows filesystem."""
    invalid_chars = '<>:"/\\|?*\0'
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    return name.strip() or f"mod_{int(time.time())}.zip"


class ModBrowserDownloadHandler:
    """Handles CoreWebView2 DownloadStarting interception and completion notifications."""

    def __init__(
        self,
        download_dir: Path,
        parent_pid: int,
        update_ui: Callable[..., None],
        emit_event: Callable[[dict], None],
        on_count_delta: Callable[[int], None],
    ) -> None:
        self.download_dir = Path(download_dir)
        self.parent_pid = parent_pid
        self.update_ui = update_ui
        self.emit_event = emit_event
        self.on_count_delta = on_count_delta

    def handle_download_starting(self, sender, args, system_mod, core_download_state) -> None:
        """Redirects WebView2 download silently to download_dir and tracks progress."""
        download_op = args.DownloadOperation
        clean_name = self._resolve_clean_name(args, download_op)
        target_path = self._unique_target_path(clean_name)

        args.ResultFilePath = str(target_path)
        args.Handled = True

        self.on_count_delta(1)
        self.update_ui(f"⬇ 准备下载: {clean_name}...", progress_pct=0)
        self.emit_event({
            "event": "download_start",
            "filename": clean_name,
            "target_path": str(target_path),
            "uri": str(download_op.Uri) if download_op and hasattr(download_op, "Uri") else "",
        })

        completed_flag = [False]
        self._hook_operation_events(
            download_op, target_path, clean_name, completed_flag, system_mod, core_download_state
        )

    def _resolve_clean_name(self, args, download_op) -> str:
        res_path = str(args.ResultFilePath) if args.ResultFilePath is not None else ""
        raw_name = os.path.basename(res_path) if res_path else ""
        if not raw_name or raw_name == ".":
            try:
                uri_str = str(download_op.Uri) if download_op and hasattr(download_op, "Uri") else ""
                cand = os.path.basename(uri_str.split("?")[0].split("#")[0])
                if cand and "." in cand:
                    raw_name = cand
            except Exception:
                pass
        if not raw_name or raw_name == ".":
            raw_name = f"mod_{int(time.time())}.zip"
        clean_name = sanitize_filename(raw_name)
        return clean_name if "." in clean_name else f"{clean_name}.zip"

    def _unique_target_path(self, clean_name: str) -> Path:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        target_path = (self.download_dir / clean_name).resolve()
        stem, suffix = target_path.stem, target_path.suffix
        idx = 1
        while target_path.exists():
            target_path = (self.download_dir / f"{stem} ({idx}){suffix}").resolve()
            idx += 1
        return target_path

    def _hook_operation_events(
        self, download_op, target_path: Path, clean_name: str,
        completed_flag: list, system_mod, core_download_state
    ) -> None:
        def mark_complete(completed_file: Path) -> None:
            if completed_flag[0]:
                return
            completed_flag[0] = True
            self.on_count_delta(-1)
            self.update_ui(
                f"⏳ [{clean_name}] 下载完成，正在自动导入至模组管理...",
                progress_pct=100,
                is_success=True,
            )
            self.emit_event({
                "event": "download_complete",
                "filename": clean_name,
                "file_path": str(completed_file),
            })
            if self.parent_pid <= 0:
                threading.Thread(target=self._standalone_import, args=(completed_file,), daemon=True).start()

        def on_bytes_received(sender_op, event_args) -> None:
            try:
                rec = sender_op.BytesReceived
                tot = sender_op.TotalBytesToReceive
                pct = (rec / tot * 100.0) if tot > 0 else 0
                txt = f"⬇ {clean_name}  {rec / 1048576:.1f} / {tot / 1048576:.1f} MB  ({pct:.0f}%)"
                self.update_ui(txt, progress_pct=pct)
            except Exception:
                pass

        def on_state_changed(sender_op, event_args) -> None:
            try:
                state = sender_op.State
                if state == core_download_state.Completed:
                    res_p = getattr(sender_op, "ResultFilePath", None) or str(target_path)
                    mark_complete(Path(str(res_p)))
                elif state == core_download_state.Interrupted:
                    self.on_count_delta(-1)
                    reason = str(sender_op.InterruptReason)
                    self.update_ui(f"❌ 下载中断: {clean_name} ({reason})", is_error=True)
                    self.emit_event({"event": "download_interrupted", "filename": clean_name, "reason": reason})
            except Exception as ex:
                log.exception(f"on_state_changed error: {ex}")

        try:
            download_op.BytesReceivedChanged += system_mod.EventHandler[system_mod.Object](on_bytes_received)
        except Exception:
            try:
                download_op.BytesReceivedChanged += on_bytes_received
            except Exception:
                pass

        try:
            download_op.StateChanged += system_mod.EventHandler[system_mod.Object](on_state_changed)
        except Exception:
            try:
                download_op.StateChanged += on_state_changed
            except Exception:
                pass

        self._start_fallback_poller(target_path, clean_name, completed_flag, mark_complete)

    def _start_fallback_poller(
        self, target_path: Path, clean_name: str, completed_flag: list, mark_complete: Callable[[Path], None]
    ) -> None:
        def poll() -> None:
            for _ in range(600):
                time.sleep(1.0)
                if completed_flag[0]:
                    break
                crdownload = Path(str(target_path) + ".crdownload")
                if target_path.exists() and not crdownload.exists():
                    try:
                        sz1 = target_path.stat().st_size
                        if sz1 > 0:
                            time.sleep(0.5)
                            if target_path.stat().st_size == sz1:
                                mark_complete(target_path)
                                break
                    except Exception:
                        pass

        threading.Thread(target=poll, daemon=True, name=f"DlWatch-{clean_name[:20]}").start()

    def _standalone_import(self, file_path: Path) -> None:
        try:
            import core.path_manager  # noqa: F401
            import core.config_manager  # noqa: F401
            from core.mod_service import ModService
            success, msg = ModService.import_mod_from_path(file_path)
            if success:
                self.update_ui(f"🎉 [{file_path.stem}] 导入成功！", is_success=True)
            else:
                self.update_ui(f"⚠ 导入提示: {msg}", is_error=True)
        except Exception:
            self.update_ui(f"⚠ 文件已保存至: {file_path.parent}", is_error=False)
            try:
                os.startfile(str(file_path.parent))
            except Exception:
                pass
