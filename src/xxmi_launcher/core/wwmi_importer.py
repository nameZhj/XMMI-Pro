"""
@file: src/xxmi_launcher/core/wwmi_importer.py
@brief: Imports, validates, and deploys WWMI-Package into the active WWMI directory.
@exports: WWMIImporter, WWMIImportResult
"""
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
import shutil
import ssl
from typing import Callable, Optional
import urllib.request
import zipfile

import core.path_manager as Paths
from core.utils.lossless_ini_editor import make_file_writable

log = logging.getLogger(__name__)


@dataclass
class WWMIImportResult:
    success: bool
    version: str
    message: str
    installed_path: Optional[Path] = None


class WWMIImporter:
    """Manages downloading, extracting, and hot-deploying WWMI-Package."""

    VERSION_PATTERN = re.compile(
        r'^\s*global\s+\$wwmi_version\s*=\s*(\d+)\.*(\d)(\d*)',
        re.MULTILINE
    )

    @classmethod
    def get_target_dir(cls) -> Path:
        """Returns the base directory where WWMI should be deployed."""
        return Paths.App.Root / 'WWMI'

    @classmethod
    def get_installed_version(cls) -> Optional[str]:
        """Detects the currently installed WWMI version from ini file."""
        ini_file = cls.get_target_dir() / 'Core' / 'WWMI' / 'WuWa-Model-Importer.ini'
        if not ini_file.is_file():
            return None
        try:
            content = ini_file.read_text(encoding='utf-8', errors='ignore')
            m = cls.VERSION_PATTERN.search(content)
            if not m:
                return "Unknown"
            g1, g2, g3 = m.group(1), m.group(2), m.group(3) or '0'
            return f"{g1}.{g2}.{g3}"
        except Exception as exc:
            log.warning("Failed to read WWMI version: %s", exc)
            return None

    @classmethod
    def import_from_folder(
        cls,
        source_dir: Path,
        log_cb: Optional[Callable[[str], None]] = None
    ) -> WWMIImportResult:
        """Deploys WWMI from an unpacked folder."""
        def _log(msg: str) -> None:
            if log_cb:
                log_cb(msg)
            log.info(msg)

        _log(f"正在从目录导入 WWMI-Package: {source_dir}")
        core_dir = cls._locate_core_dir(source_dir)
        if not core_dir:
            msg = "导入失败: 未在目标路径中找到有效的 Core/WWMI 结构"
            _log(f"❌ {msg}")
            return WWMIImportResult(False, "", msg)

        target_dir = cls.get_target_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / 'Mods').mkdir(exist_ok=True)

        cls._copy_core_and_configs(source_dir, core_dir, target_dir, _log)
        ver = cls.get_installed_version() or "1.0.0"
        msg = f"成功导入 WWMI-Package (版本: v{ver})"
        _log(f"✅ {msg}")
        cls._notify_launcher()
        return WWMIImportResult(True, ver, msg, target_dir)

    @classmethod
    def import_from_zip(
        cls,
        zip_path: Path,
        log_cb: Optional[Callable[[str], None]] = None
    ) -> WWMIImportResult:
        """Extracts and deploys WWMI from a .zip package archive."""
        def _log(msg: str) -> None:
            if log_cb:
                log_cb(msg)
            log.info(msg)

        _log(f"正在解压并导入 WWMI 压缩包: {zip_path.name}")
        temp_dir = Paths.App.Root / '.agent_workspace' / 'cache' / 'wwmi_extract_temp'
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(temp_dir)
            result = cls.import_from_folder(temp_dir, log_cb)
            return result
        except Exception as exc:
            err = f"解包或导入 WWMI-Package 异常: {exc}"
            _log(f"❌ {err}")
            return WWMIImportResult(False, "", err)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @classmethod
    def download_and_import(
        cls,
        log_cb: Optional[Callable[[str], None]] = None,
        progress_cb: Optional[Callable[[float], None]] = None
    ) -> WWMIImportResult:
        """Downloads latest WWMI-Package online with proxy mirrors and imports it."""
        def _log(msg: str) -> None:
            if log_cb:
                log_cb(msg)
            log.info(msg)

        _log("正在检索 SpectrumQT/WWMI-Package 最新发布包与源码镜像...")
        download_urls = cls._get_download_candidate_urls(_log)
        if not download_urls:
            msg = "无法获取 WWMI-Package 下载地址"
            _log(f"❌ {msg}")
            return WWMIImportResult(False, "", msg)

        temp_zip = Paths.App.Root / '.agent_workspace' / 'cache' / 'wwmi_download.zip'
        temp_zip.parent.mkdir(parents=True, exist_ok=True)
        if temp_zip.exists():
            temp_zip.unlink(missing_ok=True)

        success = cls._download_file_with_fallbacks(download_urls, temp_zip, _log, progress_cb)
        if not success or not temp_zip.is_file():
            msg = "下载 WWMI-Package 失败，所有镜像源均连接超时或返回错误"
            _log(f"❌ {msg}")
            return WWMIImportResult(False, "", msg)

        try:
            return cls.import_from_zip(temp_zip, log_cb)
        finally:
            temp_zip.unlink(missing_ok=True)

    @classmethod
    def _locate_core_dir(cls, base: Path) -> Optional[Path]:
        """Scans for directory containing Core/WWMI/WuWa-Model-Importer.ini."""
        direct = base / 'Core' / 'WWMI' / 'WuWa-Model-Importer.ini'
        if direct.is_file():
            return base / 'Core'
        for root, _, files in os.walk(base):
            if 'WuWa-Model-Importer.ini' in files:
                p = Path(root)
                if p.name == 'WWMI' and p.parent.name == 'Core':
                    return p.parent
        return None

    @classmethod
    def _copy_core_and_configs(
        cls,
        source_root: Path,
        core_dir: Path,
        target_dir: Path,
        log_fn: Callable[[str], None]
    ) -> None:
        """Copies Core, d3dx.ini, and optional guides into target directory."""
        dest_core = target_dir / 'Core'
        if dest_core.exists():
            shutil.rmtree(dest_core, ignore_errors=True)
        shutil.copytree(core_dir, dest_core)
        log_fn(f"已同步核心文件 Core/ 至 {dest_core}")

        # Locate and copy d3dx.ini
        ini_candidates = [
            core_dir.parent / 'd3dx.ini',
            source_root / 'd3dx.ini',
            source_root / 'WWMI' / 'd3dx.ini'
        ]
        for c in ini_candidates:
            if c.is_file():
                dest_d3dx = target_dir / 'd3dx.ini'
                make_file_writable(dest_d3dx)
                try:
                    shutil.copy2(c, dest_d3dx)
                    log_fn("已同步默认配置文件 d3dx.ini")
                except PermissionError as e:
                    log_fn(f"同步 d3dx.ini 权限受限: {e}")
                break

    @classmethod
    def _get_download_candidate_urls(cls, log_fn: Callable[[str], None]) -> list[str]:
        """Gathers list of download URLs using GitHub releases and repo branch zips."""
        urls: list[str] = []
        api_url = "https://api.github.com/repos/SpectrumQT/WWMI-Package/releases/latest"
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(api_url, headers={'User-Agent': 'XMMI-Pro'})
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                data = json.loads(resp.read().decode())
                for asset in data.get('assets', []):
                    u = asset.get('browser_download_url')
                    if u and u.endswith('.zip'):
                        urls.append(u)
                        urls.append(f"https://ghproxy.net/{u}")
        except Exception as exc:
            log_fn(f"检索 GitHub API 失败 ({exc})，将回退至主干分支归档包")

        repo_zip = "https://github.com/SpectrumQT/WWMI-Package/archive/refs/heads/main.zip"
        urls.extend([
            f"https://ghproxy.net/{repo_zip}",
            repo_zip,
            "https://github.com/SpectrumQT/WWMI-Package/releases/download/v1.1.0/WWMI-PACKAGE-v1.1.0.zip",
            "https://ghproxy.net/https://github.com/SpectrumQT/WWMI-Package/releases/download/v1.1.0/WWMI-PACKAGE-v1.1.0.zip",
        ])
        return urls

    @classmethod
    def _download_file_with_fallbacks(
        cls,
        urls: list[str],
        dest_path: Path,
        log_fn: Callable[[str], None],
        prog_fn: Optional[Callable[[float], None]] = None
    ) -> bool:
        """Tries downloading from multiple candidate URLs until one succeeds."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for url in urls:
            log_fn(f"尝试从源下载: {url}")
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 XMMI-Pro/1.0'})
                with urllib.request.urlopen(req, timeout=12, context=ctx) as response:
                    if response.status != 200:
                        continue
                    total = int(response.headers.get('Content-Length', 0))
                    downloaded = 0
                    with open(dest_path, 'wb') as out_f:
                        while True:
                            chunk = response.read(64 * 1024)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0 and prog_fn:
                                prog_fn(min(1.0, downloaded / total))
                    if dest_path.stat().st_size > 1024:
                        log_fn(f"下载成功 ({dest_path.stat().st_size // 1024} KB)")
                        return True
            except Exception as exc:
                log_fn(f"源连接失败 ({exc})，切换下一个备用镜像...")
        return False

    @classmethod
    def _notify_launcher(cls) -> None:
        """Notifies launcher package manager of new WWMI installation."""
        try:
            import core.event_manager as Events
            Events.Fire(Events.PackageManager.NotifyPackageVersions(detect_installed=True))
        except Exception as exc:
            log.debug("Event notification skipped: %s", exc)
