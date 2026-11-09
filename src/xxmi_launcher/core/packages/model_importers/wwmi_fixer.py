"""
@file: src/xxmi_launcher/core/packages/model_importers/wwmi_fixer.py
@brief: Wuthering Waves mod diagnostic, repair, and hardware-adaptive optimizer
@exports: WWMIRepairAndOptimizer, LosslessIniEditor, apply_engine_ini_fixes, apply_d3dx_ini_fixes, apply_windows_compat_fixes
"""

import os
import re
import shutil
import logging
import platform
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from core.utils.lossless_ini_editor import LosslessIniEditor, make_file_writable
from core.utils.hardware_profiler import SystemHardwareProfiler, AdaptiveModConfig, HardwareSpecs

log = logging.getLogger(__name__)


def apply_engine_ini_fixes(game_root: Path | str, adaptive_cfg: Any) -> List[str]:
    """定位 Engine.ini 并写入 [SystemSettings]、[/Script/Engine.RendererSettings] 和 [ConsoleVariables] 优化参数"""
    logs: List[str] = []
    root = Path(game_root)
    candidates = [
        root / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
        root / "Wuthering Waves Game" / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
        root / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
    ]
    target_inis = [p for p in candidates if p.exists() or (len(p.parents) > 2 and p.parents[2].exists())]
    if not target_inis:
        target_inis = [candidates[0]]

    lod = str(getattr(adaptive_cfg, "lod_distance_scale", None) or (adaptive_cfg.get("r.Kuro.SkeletalMesh.LODDistanceScale") if hasattr(adaptive_cfg, "get") else None) or 20)
    pool = str(getattr(adaptive_cfg, "streaming_pool_size", None) or (adaptive_cfg.get("r.Streaming.PoolSize") if hasattr(adaptive_cfg, "get") else None) or 3584)
    hidden = str(getattr(adaptive_cfg, "hidden_primitive_scale", None) or (adaptive_cfg.get("r.Streaming.HiddenPrimitiveScale") if hasattr(adaptive_cfg, "get") else None) or 12)

    updates = {
        "SystemSettings": {
            "r.Kuro.SkeletalMesh.LODDistanceScale": lod,
            "r.Streaming.FullyLoadUsedTextures": "1",
            "r.Streaming.HiddenPrimitiveScale": hidden,
            "r.Streaming.PoolSize": pool,
        },
        "/Script/Engine.RendererSettings": {
            "r.Streaming.HiddenPrimitiveScale": hidden,
            "r.Streaming.FramesForFullUpdate": "0",
            "r.Streaming.AmortizeCPUToGPUCopy": "0",
            "r.Streaming.PoolSize": pool,
        },
        "ConsoleVariables": {
            "r.Kuro.SkeletalMesh.LODDistanceScale": lod,
            "r.Streaming.FullyLoadUsedTextures": "1",
        },
    }

    for ini_path in target_inis:
        try:
            LosslessIniEditor.update_sections(ini_path, updates, create_backup=True)
            logs.append(f"[Engine.ini] 已写入自适应流送与防破图渲染参数 -> {ini_path}")
        except Exception as e:
            logs.append(f"[Engine.ini] 写入失败 {ini_path}: {e}")
    return logs


def apply_d3dx_ini_fixes(wwmi_root: Path | str, adaptive_cfg: Any) -> List[str]:
    """更新 d3dx.ini 的 delay、cache_shaders，关闭 logging/hunting，并移除旧版 ShaderRegex 卡顿块"""
    logs: List[str] = []
    d3dx_ini = Path(wwmi_root) / "d3dx.ini"
    if not d3dx_ini.exists():
        return logs

    delay = str(getattr(adaptive_cfg, "init_delay_ms", None) or (adaptive_cfg.get("delay") if hasattr(adaptive_cfg, "get") else None) or 500)
    updates = {
        "Loader": {"delay": delay},
        "Rendering": {"cache_shaders": "1"},
        "Logging": {"calls": "0", "input": "0", "debug": "0"},
        "Hunting": {"hunting": "0"},
    }
    LosslessIniEditor.update_sections(d3dx_ini, updates, create_backup=True)
    logs.append(f"[d3dx.ini] 已配置 delay={delay}ms、cache_shaders=1 并关闭调试日志")

    # 移除旧版教程卡顿块
    try:
        content = d3dx_ini.read_text(encoding="utf-8", errors="ignore")
        if "[ShaderRegexEnableTextureOverrides]" in content or "if $costume_mods" in content:
            cleaned = re.sub(
                r"\[ShaderRegexEnableTextureOverrides\][\s\S]*?endif",
                "; [XMMI-Pro AutoFix] Removed legacy framerate-killing ShaderRegex block",
                content,
                flags=re.IGNORECASE,
            )
            make_file_writable(d3dx_ini)
            d3dx_ini.write_text(cleaned, encoding="utf-8")
            logs.append("[d3dx.ini] 已移除导致 F6 快捷键失效与 50% 掉帧的旧版 ShaderRegex 块")
    except Exception as e:
        logs.append(f"[d3dx.ini] 清理旧版正则块失败: {e}")
    return logs


def apply_windows_compat_fixes(game_root: Path | str) -> List[str]:
    """在注册表 AppCompatFlags 中写入禁用全屏优化（解决注入黑屏与闪烁）"""
    logs: List[str] = []
    if platform.system() != "Windows":
        return logs
    try:
        import winreg
        root = Path(game_root)
        exes = [
            root / "Wuthering Waves.exe",
            root / "Client" / "Binaries" / "Win64" / "Client-Win64-Shipping.exe",
            root / "Wuthering Waves Game" / "Client" / "Binaries" / "Win64" / "Client-Win64-Shipping.exe",
        ]
        key_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            for exe in exes:
                if exe.exists():
                    winreg.SetValueEx(key, str(exe.resolve()), 0, winreg.REG_SZ, "~ DISABLEDXMAXIMIZEDWINDOWEDMODE")
                    logs.append(f"[系统兼容层] 已为 {exe.name} 禁用全屏优化")
    except Exception as e:
        log.warning(f"Failed to set AppCompatFlags: {e}")
    return logs


class WWMIRepairAndOptimizer:
    """《鸣潮》Mod 全链路诊断、修复与硬件自适应配置器"""

    def __init__(self, game_root: Path | str, wwmi_root: Path | str):
        self.game_root = Path(game_root)
        self.wwmi_root = Path(wwmi_root)
        self.mods_dir = self.wwmi_root / "Mods"

    def apply_hardware_adaptive_optimization(self) -> Tuple[HardwareSpecs, AdaptiveModConfig, List[str]]:
        """一键探测硬件配置并写入 Engine.ini、d3dx.ini 与系统注册表兼容层"""
        logs: List[str] = []
        specs = SystemHardwareProfiler.detect_hardware(str(self.game_root))
        has_reshade = (self.wwmi_root / "Reshade64.dll").exists() or (self.game_root / "Reshade64.dll").exists()
        cfg = SystemHardwareProfiler.build_adaptive_config(specs, has_reshade=has_reshade)

        logs.append(
            f"[硬件探测] GPU: {specs.gpu_name} ({specs.vram_mb}MB VRAM) | "
            f"CPU: {specs.cpu_threads}线程 | RAM: {specs.ram_total_mb}MB -> 评定档位: {specs.tier}"
        )
        logs.extend(apply_engine_ini_fixes(self.game_root, cfg))
        logs.extend(apply_d3dx_ini_fixes(self.wwmi_root, cfg))
        logs.extend(apply_windows_compat_fixes(self.game_root))
        return specs, cfg, logs

    def scan_and_repair_mods(self, purge_shader_cache: bool = False) -> Dict[str, any]:
        """扫描 Mods 文件夹：清理毒瘤文件、修复语法、检测同角色 Hash 冲突、按需清理着色器缓存"""
        report = {"fixed_inis": [], "removed_legacy_files": [], "hash_conflicts": [], "cache_purged": False}
        if purge_shader_cache:
            for folder in ["ShaderCache", "ShaderFixes"]:
                target = self.wwmi_root / folder
                if target.exists():
                    for f in target.glob("*"):
                        if f.suffix.lower() in {".bin", ".txt", ".log"} and f.is_file():
                            try:
                                f.unlink()
                            except OSError:
                                pass
            report["cache_purged"] = True

        if not self.mods_dir.exists():
            return report

        hash_registry: Dict[str, List[Path]] = {}
        for root, _, files in os.walk(self.mods_dir):
            root_path = Path(root)
            if any(part.upper().startswith("DISABLED") for part in root_path.relative_to(self.mods_dir).parts):
                continue
            for file_name in files:
                file_path = root_path / file_name
                lower_name = file_name.lower()
                if lower_name in {"checktexture.ini", "references.ini"}:
                    disabled_path = file_path.with_name(f"DISABLED_{file_name}.bak")
                    shutil.move(str(file_path), str(disabled_path))
                    report["removed_legacy_files"].append(str(file_path))
                    continue
                if lower_name.endswith(".ini") and not lower_name.startswith("disabled"):
                    self._repair_single_mod_ini(file_path, hash_registry, report)

        for h_val, mod_files in hash_registry.items():
            if len({p.parent for p in mod_files}) > 1:
                report["hash_conflicts"].append({"hash": h_val, "paths": [str(p) for p in mod_files]})
        return report

    def _repair_single_mod_ini(self, ini_path: Path, hash_registry: Dict[str, List[Path]], report: Dict[str, any]) -> None:
        raw = ini_path.read_text(encoding="utf-8", errors="ignore")
        lines, modified, new_lines = raw.splitlines(), False, []
        current_sec, sec_re, hash_re = "", re.compile(r"^\s*\[([^\]]+)\]"), re.compile(r"^\s*hash\s*=\s*([0-9a-fA-F]{8,16})\s*$")

        for line in lines:
            m_sec = sec_re.match(line)
            if m_sec:
                current_sec = m_sec.group(1).strip()
            if current_sec.lower().startswith("textureoverride"):
                m_hash = hash_re.match(line)
                if m_hash:
                    hash_registry.setdefault(m_hash.group(1).lower(), []).append(ini_path)
            if "if $costume_mods" in line:
                new_lines.append(f"; [AutoFixed] {line}")
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
