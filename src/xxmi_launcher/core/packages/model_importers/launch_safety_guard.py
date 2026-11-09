"""
@file: src/xxmi_launcher/core/packages/model_importers/launch_safety_guard.py
@brief: Crash guard, proxy DLL conflict isolation, and automatic rollback monitor for Wuthering Waves
@exports: LaunchSafetyGuard
"""
import time
import shutil
import psutil
import logging
import threading
from pathlib import Path
from typing import List, Tuple, Optional

from core.utils.lossless_ini_editor import make_file_writable

log = logging.getLogger(__name__)


class LaunchSafetyGuard:
    """防崩溃、反作弊代理冲突排查、光追死锁消除与崩溃自动回滚安全守卫"""

    @staticmethod
    def sanitize_adaptive_parameters(vram_mb: int, raw_pool_size: int, raw_delay_ms: int) -> Tuple[int, int]:
        """显存池安全封顶 4096MB 且不超物理显存 45%，延迟限制在安全窗口 150-800ms"""
        safe_pool = min(raw_pool_size, max(1024, int(vram_mb * 0.45)), 4096)
        safe_delay = max(150, min(raw_delay_ms, 800))
        return safe_pool, safe_delay

    @staticmethod
    def prevent_dx11_raytracing_deadlock(game_root: Path | str) -> None:
        """关闭 DX11 下引发死锁崩溃的光线追踪设置"""
        root = Path(game_root)
        candidates = [
            root / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "GameUserSettings.ini",
            root / "Wuthering Waves Game" / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "GameUserSettings.ini",
        ]
        for gus_path in candidates:
            if not gus_path.exists():
                continue
            try:
                content = gus_path.read_text(encoding="utf-8", errors="ignore")
                modified = content.replace("bEnableRayTracing=True", "bEnableRayTracing=False").replace("RayTracing=1", "RayTracing=0")
                if modified != content:
                    make_file_writable(gus_path)
                    bak = gus_path.with_suffix(".ini.orig.bak")
                    if not bak.exists():
                        shutil.copy2(gus_path, bak)
                    gus_path.write_text(modified, encoding="utf-8")
                    log.info(f"[防崩溃守卫] 已在 {gus_path.name} 中关闭光线追踪以防死锁")
            except Exception as e:
                log.warning(f"Failed to sanitize GameUserSettings.ini: {e}")

    @staticmethod
    def filter_launch_args_for_exe(target_exe: Path | str, extra_args: List[str]) -> List[str]:
        """仅当拉起 Client-Win64-Shipping.exe 主程序时才放行自适应引擎参数"""
        if not target_exe:
            return []
        exe_name = Path(target_exe).name.lower()
        if "shipping" not in exe_name:
            log.warning(f"[参数过滤] 目标 {exe_name} 非 Shipping 主程序，拦截自适应引擎参数注入")
            return []
        return [arg.strip() for arg in extra_args if arg and arg.strip()]

    @staticmethod
    def isolate_incompatible_proxy_dlls(game_root: Path | str) -> List[str]:
        """排查并隔离游戏执行目录下的代理 DLL（如 dxgi.dll、d3dx.dll），防止 ACE 反作弊误报"""
        root = Path(game_root)
        isolated: List[str] = []
        search_dirs = [
            root / "Client" / "Binaries" / "Win64",
            root / "Wuthering Waves Game" / "Client" / "Binaries" / "Win64",
        ]
        risky_dlls = {"dxgi.dll", "d3d11.dll", "d3dx.dll", "3dmloader.dll"}
        for win64_dir in search_dirs:
            if not win64_dir.is_dir():
                continue
            for file_path in win64_dir.glob("*.dll"):
                if file_path.name.lower() in risky_dlls:
                    try:
                        disabled_name = file_path.with_name(f"DISABLED_{file_path.name}.bak")
                        make_file_writable(file_path)
                        file_path.rename(disabled_name)
                        isolated.append(str(file_path))
                        log.warning(f"[反作弊防护] 已隔离游戏内部易触发反作弊的代理 DLL: {file_path.name}")
                    except Exception as e:
                        log.error(f"Failed to isolate risky proxy DLL {file_path}: {e}")
        return isolated

    @staticmethod
    def synchronize_runtime_packages(wwmi_root: Path | str, resources_root: Optional[Path | str] = None) -> List[str]:
        """校验并同步 3DMigoto/WWMI 底层注入 DLL，确保其为最新签名主干版本"""
        wwmi_path = Path(wwmi_root)
        synced: List[str] = []
        if not resources_root:
            cand = wwmi_path.parent / "Resources" / "Packages" / "XXMI"
            resources_root = cand if cand.exists() else None
        if not resources_root or not Path(resources_root).exists():
            return synced

        res_path = Path(resources_root)
        for dll_name in ["d3d11.dll", "3dmloader.dll", "d3dcompiler_47.dll"]:
            src_dll = res_path / dll_name
            dst_dll = wwmi_path / dll_name
            if src_dll.is_file() and (not dst_dll.exists() or dst_dll.stat().st_size == 0):
                try:
                    make_file_writable(dst_dll)
                    shutil.copy2(src_dll, dst_dll)
                    synced.append(dll_name)
                    log.info(f"[依赖同步] 已从安装源补全核心注入组件: {dll_name}")
                except Exception as e:
                    log.warning(f"Failed to sync runtime DLL {dll_name}: {e}")
        return synced

    @staticmethod
    def rollback_all_configs(game_root: Path | str, wwmi_root: Path | str) -> List[str]:
        """将配置文件从 .orig.bak 基线备份还原，实现一键无损回滚"""
        restored: List[str] = []
        root = Path(game_root)
        wwmi = Path(wwmi_root)
        targets = [
            root / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
            root / "Wuthering Waves Game" / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
            root / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "GameUserSettings.ini",
            root / "Wuthering Waves Game" / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "GameUserSettings.ini",
            wwmi / "d3dx.ini",
        ]
        for target in targets:
            bak = target.with_suffix(target.suffix + ".orig.bak")
            if not bak.exists():
                continue
            try:
                make_file_writable(target)
                shutil.copy2(bak, target)
                restored.append(str(target))
                log.info(f"[自动回滚] 已成功将 {target.name} 恢复至纯净初始状态")
            except Exception as e:
                log.error(f"Rollback failed for {target}: {e}")
        return restored

    @classmethod
    def _is_process_running(cls, proc_name: str) -> bool:
        try:
            for p in psutil.process_iter(["name"]):
                try:
                    if p.info and p.info.get("name") and p.info["name"].lower() == proc_name.lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass
        return False

    @classmethod
    def monitor_and_rollback_on_crash(
        cls,
        game_root: Path | str,
        wwmi_root: Path | str,
        process_name: str = "Client-Win64-Shipping.exe",
        watch_seconds: int = 25
    ) -> bool:
        """后台守护任务：启动后监控 25 秒，若游戏异常闪退或产生 UE4 崩溃转储则自动回滚纯净配置"""
        root = Path(game_root)
        wwmi = Path(wwmi_root)
        crash_dirs = [
            root / "Client" / "Saved" / "Crashes",
            root / "Wuthering Waves Game" / "Client" / "Saved" / "Crashes",
        ]
        initial_crashes = set()
        for cd in crash_dirs:
            if cd.exists():
                try:
                    initial_crashes.update(cd.glob("*"))
                except Exception:
                    pass

        start_time = time.time()
        proc_seen = False
        while time.time() - start_time < (watch_seconds + 30):
            if cls._is_process_running(process_name):
                proc_seen = True
                break
            time.sleep(0.5)

        if not proc_seen:
            log.warning(f"[防崩守卫] 等待 {process_name} 启动超时，停止监视")
            return False

        monitor_start = time.time()
        while time.time() - monitor_start < watch_seconds:
            if not cls._is_process_running(process_name):
                log.error("[防崩守卫] 检测到鸣潮进程在启动期异常闪退！正在自动回滚纯净配置文件...")
                cls.rollback_all_configs(root, wwmi)
                return False

            for cd in crash_dirs:
                if cd.exists():
                    try:
                        current = set(cd.glob("*"))
                        if len(current - initial_crashes) > 0:
                            log.error("[防崩守卫] 检测到 Client/Saved/Crashes/ 产生新的崩溃日志！立即自动回滚纯净配置...")
                            cls.rollback_all_configs(root, wwmi)
                            return False
                    except Exception:
                        pass
            time.sleep(1.0)

        log.info("[防崩守卫] 游戏已平稳度过 25 秒启动期，系统进入稳定运行状态")
        return True

    @classmethod
    def start_crash_monitor_thread(
        cls,
        game_root: Path | str,
        wwmi_root: Path | str,
        process_name: str = "Client-Win64-Shipping.exe",
        watch_seconds: int = 25
    ) -> threading.Thread:
        """拉起后台守护线程执行监控"""
        thread = threading.Thread(
            target=cls.monitor_and_rollback_on_crash,
            args=(game_root, wwmi_root, process_name, watch_seconds),
            daemon=True,
            name="WWMI-CrashSafetyGuard"
        )
        thread.start()
        return thread
