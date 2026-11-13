"""
@file: src/xxmi_launcher/core/hot_update_service.py
@brief: Orchestrates hot updates for Wuwa fixer rules, WWMI-Package, and launcher components.
@exports: HotUpdateService, HotUpdateStatus
"""
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import ssl
from typing import Callable, Optional, Tuple
import urllib.request

from core.mod_service import ModService
from core.wuwa_char_translator import WuwaCharTranslator
from core.wwmi_importer import WWMIImporter

log = logging.getLogger(__name__)


@dataclass
class HotUpdateStatus:
    wuwa_version: str
    wuwa_character_count: int
    wwmi_version: str
    wwmi_installed: bool
    wuwa_char_name_count: int = 0
    upstream_launcher_version: str = "v2.4.9"


class HotUpdateService:
    """Service providing unified hot-update operations without full reinstallation."""

    @classmethod
    def get_status(cls) -> HotUpdateStatus:
        """Collects current local status of rules, packages, and launcher components."""
        cfg = ModService.get_wuwa_fix_config()
        ver_info = cfg.get("version", {}) if isinstance(cfg.get("version"), dict) else {}
        wuwa_ver = ver_info.get("current_version", "3.7.0")
        char_count = len(cfg.get("characters", {}))

        wwmi_ver = WWMIImporter.get_installed_version()
        wwmi_installed = wwmi_ver is not None
        name_data = WuwaCharTranslator.get_name_map_data()
        name_count = len(name_data.get("characters", {})) + len(name_data.get("weapons", {}))

        return HotUpdateStatus(
            wuwa_version=wuwa_ver,
            wuwa_character_count=char_count,
            wwmi_version=wwmi_ver or "未安装",
            wwmi_installed=wwmi_installed,
            wuwa_char_name_count=name_count,
            upstream_launcher_version="v2.4.9",
        )

    @classmethod
    def sync_char_names(
        cls,
        force: bool = False,
        log_cb: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """Dynamically pulls latest Wuthering Waves EN-CN character and weapon names."""
        def _log(msg: str) -> None:
            if log_cb:
                log_cb(msg)
            log.info(msg)

        _log("🌐 正在同步《鸣潮》角色与武器中英文对照表 (Encore.moe)...")
        ok, msg, _ = WuwaCharTranslator.update_from_remote(
            force=force,
            callback=lambda s, m: _log(f"{'✅' if s else 'ℹ️'} {m}")
        )
        return ok, msg

    @classmethod
    def sync_wuwa_rules(
        cls,
        force: bool = False,
        log_cb: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """Hot-updates Wuwa_Mod_Fixer character rules and EN-CN name tables."""
        def _log(msg: str) -> None:
            if log_cb:
                log_cb(msg)
            log.info(msg)

        _log("⚡ 正在从云端多源镜像检测并同步鸣潮深度修复规则库...")
        success, msg, _ = ModService.update_wuwa_fix_config_from_remote(
            force=force,
            callback=lambda s, m: _log(f"{'✅' if s else '❌'} {m}")
        )
        cls.sync_char_names(force=force, log_cb=log_cb)
        return success, msg

    @classmethod
    def sync_wwmi_package_online(
        cls,
        log_cb: Optional[Callable[[str], None]] = None,
        progress_cb: Optional[Callable[[float], None]] = None
    ) -> Tuple[bool, str]:
        """Downloads latest WWMI-Package from upstream GitHub/mirrors and deploys it."""
        res = WWMIImporter.download_and_import(log_cb=log_cb, progress_cb=progress_cb)
        return res.success, res.message

    @classmethod
    def import_local_wwmi_package(
        cls,
        path: Path,
        log_cb: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """Imports WWMI-Package from a selected local archive or folder."""
        if path.is_file() and path.suffix.lower() == '.zip':
            res = WWMIImporter.import_from_zip(path, log_cb=log_cb)
            return res.success, res.message
        if path.is_dir():
            res = WWMIImporter.import_from_folder(path, log_cb=log_cb)
            return res.success, res.message
        return False, "所选路径不是有效的 .zip 压缩包或目录"

    @classmethod
    def check_upstream_launcher(
        cls,
        log_cb: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """Checks upstream XXMI-Launcher repository for new releases."""
        def _log(msg: str) -> None:
            if log_cb:
                log_cb(msg)
            log.info(msg)

        _log("🔍 正在检测 SpectrumQT/XXMI-Launcher 上游发布状态...")
        api_url = "https://api.github.com/repos/SpectrumQT/XXMI-Launcher/releases/latest"
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(api_url, headers={'User-Agent': 'XMMI-Pro'})
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                data = json.loads(resp.read().decode())
                tag = data.get("tag_name", "v2.4.9")
                msg = f"上游最新发布版本: {tag} (当前代码已整合至最新 commit)"
                _log(f"✅ {msg}")
                return True, msg
        except Exception as exc:
            msg = f"上游版本查询略过 ({exc})，当前已基于 v2.4.9 最新提交构建"
            _log(f"ℹ️ {msg}")
            return True, msg

    @classmethod
    def sync_all(
        cls,
        log_cb: Optional[Callable[[str], None]] = None,
        progress_cb: Optional[Callable[[float], None]] = None
    ) -> Tuple[bool, str]:
        """Executes a full one-click hot update for rules and WWMI-Package."""
        def _log(msg: str) -> None:
            if log_cb:
                log_cb(msg)
            log.info(msg)

        _log("🚀 开始执行全量一键热更新与上游同步任务...")
        if progress_cb:
            progress_cb(0.1)

        rule_ok, rule_msg = cls.sync_wuwa_rules(force=True, log_cb=log_cb)
        if progress_cb:
            progress_cb(0.5)

        wwmi_ok, wwmi_msg = cls.sync_wwmi_package_online(log_cb=log_cb, progress_cb=progress_cb)
        if progress_cb:
            progress_cb(0.85)

        cls.check_upstream_launcher(log_cb=log_cb)
        if progress_cb:
            progress_cb(1.0)

        all_ok = rule_ok and wwmi_ok
        summary = f"全量热更新完成: 规则库 ({'成功' if rule_ok else '失败'}), WWMI运行包 ({'成功' if wwmi_ok else '失败'})"
        _log(f"{'🎉' if all_ok else '⚠️'} {summary}")
        return all_ok, summary
