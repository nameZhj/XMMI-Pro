"""
@file: src/xxmi_launcher/core/packages/model_importers/wwmi_fixer.py
@brief: Wuthering Waves mod diagnostic, repair, version cache purge, and hardware-adaptive optimizer
@exports: WWMIRepairAndOptimizer, LaunchSafetyGuard, apply_engine_ini_fixes, apply_d3dx_ini_fixes, apply_windows_compat_fixes, scan_and_repair_mods
"""
import os
import re
import shutil
import logging
import platform
import winreg
from pathlib import Path
from typing import List, Dict, Tuple, Any

from core.utils.lossless_ini_editor import LosslessIniEditor, make_file_writable
from core.utils.hardware_profiler import SystemHardwareProfiler, AdaptiveModConfig, HardwareSpecs
from .launch_safety_guard import LaunchSafetyGuard

log = logging.getLogger(__name__)


class WWMIRepairAndOptimizer:
    """《鸣潮》Mod 全链路诊断、版本更新缓存自愈与硬件自适应优化引擎"""

    def __init__(self, game_root: Path | str, wwmi_root: Path | str):
        self.game_root = Path(game_root)
        self.wwmi_root = Path(wwmi_root)
        self.mods_dir = self.wwmi_root / "Mods"

    def resolve_all_engine_ini_paths(self) -> List[Path]:
        candidates = [
            self.game_root / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
            self.game_root / "Wuthering Waves Game" / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
        ]
        valid = [p for p in candidates if p.exists() or (len(p.parents) > 2 and p.parents[2].exists())]
        return valid if valid else [candidates[0]]

    def check_game_version_updated(self) -> bool:
        """检测客户端 Client-Win64-Shipping.exe 是否被更新，用于自动触发着色器缓存清理"""
        candidates = [
            self.game_root / "Client" / "Binaries" / "Win64" / "Client-Win64-Shipping.exe",
            self.game_root / "Wuthering Waves Game" / "Client" / "Binaries" / "Win64" / "Client-Win64-Shipping.exe",
        ]
        shipping_exe = next((p for p in candidates if p.exists()), None)
        if not shipping_exe:
            return False
        try:
            st = shipping_exe.stat()
            current_sig = f"{st.st_mtime}:{st.st_size}"
            marker = self.wwmi_root / ".game_version_cache"
            if marker.exists() and marker.read_text(encoding="utf-8").strip() == current_sig:
                return False
            marker.write_text(current_sig, encoding="utf-8")
            return True
        except Exception as e:
            log.warning(f"Failed to check game version updated: {e}")
            return False

    def apply_hardware_adaptive_optimization(self) -> Tuple[HardwareSpecs, AdaptiveModConfig, List[str]]:
        logs: List[str] = []
        specs = SystemHardwareProfiler.detect_hardware(str(self.game_root))
        has_reshade = (self.wwmi_root / "Reshade64.dll").exists() or (self.game_root / "Reshade64.dll").exists()
        cfg = SystemHardwareProfiler.build_adaptive_config(specs, has_reshade=has_reshade)

        safe_pool, safe_delay = LaunchSafetyGuard.sanitize_adaptive_parameters(specs.vram_mb, cfg.streaming_pool_size, cfg.init_delay_ms)
        cfg.streaming_pool_size = safe_pool
        cfg.init_delay_ms = safe_delay

        LaunchSafetyGuard.prevent_dx11_raytracing_deadlock(self.game_root)
        LaunchSafetyGuard.isolate_incompatible_proxy_dlls(self.game_root)
        LaunchSafetyGuard.synchronize_runtime_packages(self.wwmi_root)

        logs.append(f"[硬件自适应] GPU: {specs.gpu_name} ({specs.vram_mb}MB) | 安全流送池: {safe_pool}MB | 延迟: {safe_delay}ms")
        engine_updates = {
            "SystemSettings": {
                "r.Streaming.UsingNewKuroStreaming": "0",
                "r.Kuro.SkeletalMesh.LODDistanceScale": "25",
                "r.Streaming.FullyLoadUsedTextures": "1",
                "r.Streaming.UseAllMips": "1",
                "r.Streaming.HiddenPrimitiveScale": "25",
                "r.Streaming.PoolSize": str(cfg.streaming_pool_size),
            },
            "/Script/Engine.RendererSettings": {
                "r.Streaming.UsingNewKuroStreaming": "0",
                "r.Streaming.HiddenPrimitiveScale": "25",
                "r.Streaming.FramesForFullUpdate": "0",
                "r.Streaming.AmortizeCPUToGPUCopy": "0",
                "r.Streaming.PoolSize": str(cfg.streaming_pool_size),
            },
            "ConsoleVariables": {
                "r.Streaming.UsingNewKuroStreaming": "0",
                "r.Kuro.SkeletalMesh.LODDistanceScale": "25",
                "r.Streaming.HiddenPrimitiveScale": "25",
                "r.Streaming.FullyLoadUsedTextures": "1",
                "r.Streaming.UseAllMips": "1",
            },
        }
        for ini_path in self.resolve_all_engine_ini_paths():
            LosslessIniEditor.update_sections(ini_path, engine_updates, create_backup=True)
            logs.append(f"[Engine.ini] 配置写入成功 -> {ini_path}")

        d3dx_ini = self.wwmi_root / "d3dx.ini"
        if d3dx_ini.exists():
            d3dx_updates = {
                "Loader": {"delay": str(cfg.init_delay_ms)},
                "Rendering": {"cache_shaders": "1"},
                "Logging": {"calls": "0", "input": "0", "debug": "0"},
                "Hunting": {"hunting": "0"},
            }
            LosslessIniEditor.update_sections(d3dx_ini, d3dx_updates, create_backup=True)
            self._strip_legacy_shader_regex(d3dx_ini)
            logs.append(f"[d3dx.ini] 优化完成 (delay={cfg.init_delay_ms}ms)")

        if platform.system() == "Windows":
            self._apply_windows_compat(logs)
        return specs, cfg, logs

    def _strip_legacy_shader_regex(self, d3dx_ini: Path) -> None:
        try:
            content = d3dx_ini.read_text(encoding="utf-8", errors="ignore")
            if "[ShaderRegexEnableTextureOverrides]" in content or "if $costume_mods" in content:
                cleaned = re.sub(r"\[ShaderRegexEnableTextureOverrides\][\s\S]*?endif", "; [AutoFixed] Removed legacy ShaderRegex", content, flags=re.IGNORECASE)
                make_file_writable(d3dx_ini)
                d3dx_ini.write_text(cleaned, encoding="utf-8")
        except Exception as e:
            log.warning(f"Failed to strip shader regex: {e}")

    def _apply_windows_compat(self, logs: List[str]) -> None:
        try:
            key_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
            exes = [
                self.game_root / "Wuthering Waves.exe",
                self.game_root / "Client" / "Binaries" / "Win64" / "Client-Win64-Shipping.exe",
                self.game_root / "Wuthering Waves Game" / "Client" / "Binaries" / "Win64" / "Client-Win64-Shipping.exe",
            ]
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                for exe in exes:
                    if exe.exists():
                        winreg.SetValueEx(key, str(exe.resolve()), 0, winreg.REG_SZ, "~ DISABLEDXMAXIMIZEDWINDOWEDMODE")
                        logs.append(f"[兼容层] 已为 {exe.name} 禁用全屏优化")
        except Exception as e:
            log.warning(f"Failed to set AppCompatFlags: {e}")

    def scan_and_repair_mods(self, purge_shader_cache: bool = False, auto_disable_conflicts: bool = False) -> Dict[str, Any]:
        """清理旧着色器缓存、隔离毒瘤文件、自动修复语法并隔离冲突 Mod"""
        report: Dict[str, Any] = {"fixed_inis": [], "removed_legacy_files": [], "hash_conflicts": [], "disabled_conflict_folders": [], "cache_purged": False}
        if purge_shader_cache:
            cache_dir = self.wwmi_root / "ShaderCache"
            if cache_dir.exists():
                for f in cache_dir.glob("*"):
                    if f.is_file() and f.suffix.lower() in {".bin", ".txt", ".log", ".cache"}:
                        try:
                            f.unlink()
                        except OSError:
                            pass
            report["cache_purged"] = True
            log.info("[缓存清理] 已清空 WWMI/ShaderCache 下陈旧的二进制编译缓存以防 UE4 Fatal Error")

        if not self.mods_dir.exists():
            return report

        hash_registry: Dict[str, List[Tuple[Path, Path]]] = {}
        for root, _, files in os.walk(self.mods_dir):
            root_path = Path(root)
            if any(part.upper().startswith("DISABLED") for part in root_path.relative_to(self.mods_dir).parts):
                continue
            for file_name in files:
                file_path = root_path / file_name
                lower_name = file_name.lower()
                if lower_name in {"checktexture.ini", "references.ini"}:
                    disabled_path = file_path.with_name(f"DISABLED_{file_name}.bak")
                    make_file_writable(file_path)
                    shutil.move(str(file_path), str(disabled_path))
                    report["removed_legacy_files"].append(str(file_path))
                    continue
                if lower_name.endswith(".ini") and not lower_name.startswith("disabled"):
                    self._repair_single_ini(file_path, root_path, hash_registry, report)

        for h_val, entries in hash_registry.items():
            unique_top_dirs = sorted(list({e[0] for e in entries}), key=lambda p: str(p).lower())
            if len(unique_top_dirs) > 1:
                conflict_item = {"hash": h_val, "mods": [str(d) for d in unique_top_dirs]}
                report["hash_conflicts"].append(conflict_item)
                if auto_disable_conflicts:
                    for duplicate_dir in unique_top_dirs[1:]:
                        if duplicate_dir.exists() and not duplicate_dir.name.startswith("DISABLED_"):
                            disabled_dir = duplicate_dir.with_name(f"DISABLED_{duplicate_dir.name}")
                            try:
                                duplicate_dir.rename(disabled_dir)
                                report["disabled_conflict_folders"].append(str(disabled_dir))
                                log.warning(f"[冲突隔离] 自动隔离同角色 Hash 冲突文件夹: {duplicate_dir.name}")
                            except Exception as e:
                                log.error(f"Failed to disable conflict dir {duplicate_dir}: {e}")
        return report

    def _repair_single_ini(self, ini_path: Path, root_path: Path, hash_registry: Dict[str, List[Tuple[Path, Path]]], report: Dict[str, Any]) -> None:
        try:
            rel = root_path.relative_to(self.mods_dir)
            top_mod_folder = self.mods_dir / rel.parts[0] if rel.parts else root_path
        except Exception:
            top_mod_folder = root_path

        raw = ini_path.read_text(encoding="utf-8", errors="ignore")
        lines = raw.splitlines()
        modified = False
        new_lines: List[str] = []
        current_sec = ""
        sec_re = re.compile(r"^\s*\[([^\]]+)\]")
        hash_re = re.compile(r"^\s*hash\s*=\s*([0-9a-fA-F]{8,16})\s*$")

        costume_re = re.compile(r"^(\s*)(?:;\s*\[AutoFixed\]\s*)?if\s+\$costume_mods\b", re.IGNORECASE)
        corrupt_strip_res = (
            re.compile(r"^\s*CheckTextureOverride\s*=\s*0\s*$", re.IGNORECASE),
            re.compile(r"^\s*\$\\WWMIv1\\vg_remap\s*=", re.IGNORECASE),
            re.compile(r"^\s*;\s*\[Auto-generated Vertex Group Remap", re.IGNORECASE),
        )

        for line in lines:
            m_sec = sec_re.match(line)
            if m_sec:
                current_sec = m_sec.group(1).strip()
            if current_sec.lower().startswith("textureoverride"):
                m_hash = hash_re.match(line)
                if m_hash:
                    h_val = m_hash.group(1).lower()
                    if h_val not in {"00000000", "ffffffff", "11111111", "00000001", "00000002"}:
                        hash_registry.setdefault(h_val, []).append((top_mod_folder, ini_path))
            m_costume = costume_re.match(line)
            if m_costume:
                new_lines.append(f"{m_costume.group(1)}if 1")
                modified = True
                continue
            if any(rx.match(line) for rx in corrupt_strip_res):
                modified = True
                continue
            if line.strip().lower().startswith("filename") and "/" in line:
                new_lines.append(line.replace("/", "\\"))
                modified = True
                continue
            new_lines.append(line)

        if modified:
            bak_path = ini_path.with_suffix(".ini.orig.bak")
            if not bak_path.exists():
                try:
                    shutil.copy2(ini_path, bak_path)
                except Exception:
                    pass
            try:
                make_file_writable(ini_path)
                ini_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                report["fixed_inis"].append(str(ini_path))
            except Exception as e:
                log.warning(f"Failed writing mod ini {ini_path}: {e}")


def apply_engine_ini_fixes(game_root: Path | str, adaptive_cfg: Any) -> List[str]:
    opt = WWMIRepairAndOptimizer(game_root, Path(game_root).parent / "WWMI")
    return opt.apply_hardware_adaptive_optimization()[2]

def apply_d3dx_ini_fixes(wwmi_root: Path | str, adaptive_cfg: Any) -> List[str]:
    d3dx_ini = Path(wwmi_root) / "d3dx.ini"
    if not d3dx_ini.exists():
        return []
    delay = str(getattr(adaptive_cfg, "init_delay_ms", 500))
    updates = {"Loader": {"delay": delay}, "Rendering": {"cache_shaders": "1"}}
    LosslessIniEditor.update_sections(d3dx_ini, updates, create_backup=True)
    return [f"[d3dx.ini] delay={delay}"]

def apply_windows_compat_fixes(game_root: Path | str) -> List[str]:
    opt = WWMIRepairAndOptimizer(game_root, Path(game_root).parent / "WWMI")
    logs: List[str] = []
    opt._apply_windows_compat(logs)
    return logs

def scan_and_repair_mods(wwmi_root: Path | str, purge_shader_cache: bool = False, auto_disable_conflicts: bool = False) -> Dict[str, Any]:
    opt = WWMIRepairAndOptimizer(Path(wwmi_root).parent, wwmi_root)
    return opt.scan_and_repair_mods(purge_shader_cache=purge_shader_cache, auto_disable_conflicts=auto_disable_conflicts)
