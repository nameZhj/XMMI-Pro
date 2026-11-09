"""
@file gamebanana_service.py
@brief GameBanana mod parser, direct download engine, and automatic installer
@exports GameBananaService, GameBananaModInfo, GameBananaFileInfo
"""
import os
import re
import time
import logging
import requests
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Callable

from core.mod_service import ModService
import core.path_manager as Paths

log = logging.getLogger(__name__)


@dataclass
class GameBananaFileInfo:
    file_id: str
    filename: str
    filesize: int
    download_url: str
    description: str = ""

    @property
    def filesize_mb(self) -> float:
        return self.filesize / (1024 * 1024) if self.filesize > 0 else 0.0


@dataclass
class GameBananaModInfo:
    mod_id: str
    name: str
    files: List[GameBananaFileInfo] = field(default_factory=list)


class GameBananaService:
    API_URL = "https://api.gamebanana.com/Core/Item/Data"
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }

    @classmethod
    def parse_mod_id(cls, input_str: str) -> Optional[str]:
        """Extracts numeric Mod ID from URLs or raw IDs."""
        if not input_str:
            return None
        text = str(input_str).strip()
        if text.isdigit():
            return text
        m = re.search(r'/mods/(?:download/)?(\d+)', text, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r'gamebanana://(?:Mod/)?(\d+)', text, re.IGNORECASE)
        if m:
            return m.group(1)
        return None

    @classmethod
    def fetch_mod_details(cls, mod_id: str, timeout: int = 10) -> Optional[GameBananaModInfo]:
        """Fetches mod title and list of downloadable files via GameBanana public API."""
        params = {
            "itemtype": "Mod",
            "itemid": str(mod_id),
            "fields": "name,Files().aFiles()"
        }
        try:
            resp = requests.get(cls.API_URL, params=params, headers=cls.DEFAULT_HEADERS, timeout=timeout)
            if resp.status_code != 200:
                log.warning(f"GameBanana API returned HTTP {resp.status_code} for mod {mod_id}")
                return None
            data = resp.json()
            if not isinstance(data, list) or len(data) < 2:
                return None

            mod_name = str(data[0]) if data[0] else f"GameBanana_Mod_{mod_id}"
            raw_files = data[1] if isinstance(data[1], dict) else {}

            files: List[GameBananaFileInfo] = []
            for fid, fobj in raw_files.items():
                if not isinstance(fobj, dict):
                    continue
                files.append(GameBananaFileInfo(
                    file_id=str(fobj.get("_idRow", fid)),
                    filename=str(fobj.get("_sFile", f"mod_{fid}.zip")),
                    filesize=int(fobj.get("_nFilesize", 0)),
                    download_url=str(fobj.get("_sDownloadUrl", f"https://gamebanana.com/dl/{fid}")),
                    description=str(fobj.get("_sDescription", ""))
                ))

            return GameBananaModInfo(mod_id=str(mod_id), name=mod_name, files=files)
        except Exception as e:
            log.exception(f"Failed to fetch GameBanana mod {mod_id}: {e}")
            return None

    @classmethod
    def download_file(
        cls,
        url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        chunk_size: int = 65536
    ) -> bool:
        """
        Streams a file download with resume support and real-time speed calculation.
        progress_callback(received_bytes, total_bytes, speed_mb_s, status_text)
        """
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        part_path = dest_path.with_suffix(dest_path.suffix + ".part")

        starting_bytes = part_path.stat().st_size if part_path.exists() else 0
        headers = dict(cls.DEFAULT_HEADERS)
        if starting_bytes > 0:
            headers["Range"] = f"bytes={starting_bytes}-"

        try:
            with requests.get(url, headers=headers, stream=True, timeout=15, allow_redirects=True) as resp:
                if resp.status_code not in (200, 206):
                    # Server doesn't support Range; reset starting_bytes
                    if resp.status_code == 416:  # Requested Range Not Satisfiable
                        if part_path.exists():
                            part_path.replace(dest_path)
                            return True
                    starting_bytes = 0
                    if part_path.exists():
                        part_path.unlink()

                mode = "ab" if starting_bytes > 0 and resp.status_code == 206 else "wb"
                if mode == "wb":
                    starting_bytes = 0

                content_len = resp.headers.get("Content-Length")
                total_bytes = (int(content_len) + starting_bytes) if content_len and content_len.isdigit() else 0

                received = starting_bytes
                start_time = time.time()
                last_report = start_time

                with open(part_path, mode) as fp:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if cancel_check and cancel_check():
                            log.info("Download canceled by user.")
                            return False
                        if not chunk:
                            continue
                        fp.write(chunk)
                        received += len(chunk)

                        now = time.time()
                        if now - last_report >= 0.2:
                            elapsed = max(now - start_time, 0.001)
                            speed_mb = (received - starting_bytes) / (1024 * 1024) / elapsed
                            pct = (received / total_bytes * 100) if total_bytes > 0 else 0.0
                            status = f"{received / (1024 * 1024):.1f} / {total_bytes / (1024 * 1024):.1f} MB ({speed_mb:.1f} MB/s)" if total_bytes > 0 else f"{received / (1024 * 1024):.1f} MB ({speed_mb:.1f} MB/s)"
                            if progress_callback:
                                progress_callback(received, total_bytes, speed_mb, status)
                            last_report = now

            if part_path.exists():
                if dest_path.exists():
                    dest_path.unlink()
                part_path.replace(dest_path)
            return True
        except Exception as e:
            log.exception(f"Error downloading {url}: {e}")
            return False

    @classmethod
    def download_and_import(
        cls,
        download_url: str,
        filename: str,
        download_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> Tuple[bool, str]:
        """Downloads mod archive and imports it directly into the active game mods directory."""
        if not download_dir:
            try:
                download_dir = Paths.App.Root / "Downloads"
            except Exception:
                download_dir = Path.cwd() / "Downloads"
        download_dir.mkdir(parents=True, exist_ok=True)

        target_file = (download_dir / filename).resolve()

        def on_dl_progress(rec, tot, spd, txt):
            pct = (rec / tot) if tot > 0 else 0.0
            if progress_callback:
                progress_callback(f"⬇ 正在下载: {filename} ({txt})...", pct * 0.8)

        success = cls.download_file(download_url, target_file, progress_callback=on_dl_progress, cancel_check=cancel_check)
        if not success:
            return False, f"下载文件失败: {filename}"

        if progress_callback:
            progress_callback(f"📦 下载完成，正在解压并导入模组: {filename}...", 0.85)

        imp_ok, imp_msg = ModService.import_mod_from_path(target_file)
        if progress_callback:
            progress_callback(f"🎉 导入成功: {filename}" if imp_ok else f"❌ 导入失败: {imp_msg}", 1.0)

        return imp_ok, imp_msg
