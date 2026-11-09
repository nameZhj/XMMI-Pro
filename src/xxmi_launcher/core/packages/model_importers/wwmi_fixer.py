"""
@file: src/xxmi_launcher/core/packages/model_importers/wwmi_fixer.py
@brief: Wuthering Waves mod diagnostic, repair, and hardware-adaptive optimizer
@exports: WWMIRepairAndOptimizer
"""

import os
import re
import stat
import shutil
import logging
import platform
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from core.utils.lossless_ini_editor import LosslessIniEditor, make_file_writable
from .hardware_profiler import SystemHardwareProfiler, AdaptiveModConfig, HardwareSpecs

log = logging.getLogger(__name__)


class WWMIRepairAndOptimizer:
    """《鸣潮》Mod 全链路诊断、修复与硬件自适应配置器"""

    def __init__(self, game_root: Path, wwmi_root: Path):
        self.game_root = Path(game_root)
        self.wwmi_root = Path(wwmi_root)
        self.mods_dir = self.wwmi_root / "Mods"

    def resolve_all_engine_ini_paths(self) -> List[Path]:
        """
        解决《鸣潮》双层 Wuthering Waves Game 嵌套目录陷阱，找出所有候选 Engine.ini 路径并同步写入。
        """
        candidates = [
            self.game_root / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
            self.game_root / "Wuthering Waves Game" / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
        ]
        valid_paths: List[Path] = []
        for path in candidates:
            # 只要 Client/Saved 存在或父级 Client 存在即视为有效安装分支
            if path.exists() or (path.parents[2].exists()):
                valid_paths.append(path)
        return valid_paths if valid_paths else [candidates[0]]

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

        # 1. 自动优化所有候选 Engine.ini
        engine_updates = {
            "SystemSettings": {
                "r.Kuro.SkeletalMesh.LODDistanceScale": str(cfg.lod_distance_scale),
                "r.Streaming.FullyLoadUsedTextures": str(cfg.fully_load_used_textures),
                "r.Streaming.HiddenPrimitiveScale": str(cfg.hidden_primitive_scale),
                "r.Streaming.PoolSize": str(cfg.streaming_pool_size),
            },
            "/Script/Engine.RendererSettings": {
                "r.Streaming.HiddenPrimitiveScale": str(cfg.hidden_primitive_scale),
                "r.Streaming.FramesForFullUpdate": str(cfg.frames_for_full_update),
                "r.Streaming.AmortizeCPUToGPUCopy": str(cfg.amortize_cpu_to_gpu_copy),
                "r.Streaming.PoolSize": str(cfg.streaming_pool_size),
            },
            "ConsoleVariables": {
                "r.Kuro.SkeletalMesh.LODDistanceScale": str(cfg.lod_distance_scale),
                "r.Streaming.FullyLoadUsedTextures": str(cfg.fully_load_used_textures),
            },
        }
        for engine_ini in self.resolve_all_engine_ini_paths():
            LosslessIniEditor.update_sections(engine_ini, engine_updates)
            logs.append(f"[Engine.ini] 已写入自适应流送与 LOD 修复参数 -> {engine_ini}")

        # 2. 自动优化 WWMI d3dx.ini
        d3dx_ini = self.wwmi_root / "d3dx.ini"
        if d3dx_ini.exists():
            d3dx_updates = {
                "Loader": {
                    "delay": str(cfg.init_delay_ms),
                },
                "Rendering": {
                    "cache_shaders": str(cfg.cache_shaders),
                },
                "Logging": {
                    "calls": str(cfg.enable_logging),
                    "input": str(cfg.enable_logging),
                    "debug": str(cfg.enable_logging),
                },
                "Hunting": {
                    "hunting": str(cfg.enable_hunting),
                },
            }
            LosslessIniEditor.update_sections(d3dx_ini, d3dx_updates)
            self._strip_legacy_shader_regex_lag(d3dx_ini, logs)
            logs.append(f"[d3dx.ini] 已设置启动延迟 delay={cfg.init_delay_ms}ms 并关闭高开销调试日志")

        # 3. 注册表禁用全屏优化（修复 DLL 注入闪烁与黑屏）
        if platform.system() == "Windows":
            self._apply_windows_fullscreen_opt_fix(logs)

        return specs, cfg, logs

    def _strip_legacy_shader_regex_lag(self, d3dx_ini: Path, logs: List[str]) -> None:
        """移除旧教程塞入 d3dx.ini 导致帧率腰斩与 F6 失效的 ShaderRegexEnableTextureOverrides 块"""
        content = d3dx_ini.read_text(encoding="utf-8", errors="ignore")
        if "[ShaderRegexEnableTextureOverrides]" in content or "if $costume_mods" in content:
            cleaned = re.sub(
                r"\[ShaderRegexEnableTextureOverrides\][\s\S]*?endif",
                "; [XMMI-Pro AutoFix] Removed legacy framerate-killing ShaderRegex block",
                content,
                flags=re.IGNORECASE,
            )
            try:
                make_file_writable(d3dx_ini)
                d3dx_ini.write_text(cleaned, encoding="utf-8")
                logs.append("[d3dx.ini] 已移除导致 50% 掉帧和 F6 快捷键失效的旧版 ShaderRegex 补丁块")
            except PermissionError as e:
                log.warning(f"PermissionError unlocking/writing {d3dx_ini}: {e}")
            except Exception as e:
                log.warning(f"Failed writing {d3dx_ini}: {e}")

    def scan_and_repair_mods(self, purge_shader_cache: bool = False) -> Dict[str, any]:
        """扫描 Mods 文件夹：清理毒瘤文件、修复语法、检测同角色 Hash 冲突、按需清理着色器缓存"""
        report = {
            "fixed_inis": [],
            "removed_legacy_files": [],
            "hash_conflicts": [],
            "cache_purged": False,
        }

        if purge_shader_cache:
            for cache_folder in ["ShaderCache", "ShaderFixes"]:
                target = self.wwmi_root / cache_folder
                if target.exists():
                    for f in target.glob("*"):
                        # 仅清理编译生成的二进制缓存与日志，保留内置核心修复文件
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
            # 跳过已禁用的文件夹（以 DISABLED 开头）
            if any(part.upper().startswith("DISABLED") for part in root_path.relative_to(self.mods_dir).parts):
                continue

            for file_name in files:
                file_path = root_path / file_name
                lower_name = file_name.lower()

                # 1. 隔离旧版 3DMigoto 强转留下的 CheckTexture.ini 和 References.ini
                if lower_name in {"checktexture.ini", "references.ini"}:
                    disabled_path = file_path.with_name(f"DISABLED_{file_name}.bak")
                    shutil.move(str(file_path), str(disabled_path))
                    report["removed_legacy_files"].append(str(file_path))
                    continue

                if lower_name.endswith(".ini") and not lower_name.startswith("disabled"):
                    self._repair_single_mod_ini(file_path, hash_registry, report)

        # 汇总 Hash 冲突（多个启用的 Mod 同时修改同一个角色组件 Hash）
        for h_val, mod_files in hash_registry.items():
            unique_folders = {p.parent for p in mod_files}
            if len(unique_folders) > 1:
                report["hash_conflicts"].append({
                    "hash": h_val,
                    "paths": [str(p) for p in mod_files]
                })

        return report

    def _repair_single_mod_ini(
        self,
        ini_path: Path,
        hash_registry: Dict[str, List[Path]],
        report: Dict[str, any]
    ) -> None:
        raw = ini_path.read_text(encoding="utf-8", errors="ignore")
        lines = raw.splitlines()
        modified = False
        new_lines: List[str] = []

        current_sec = ""
        sec_re = re.compile(r"^\s*\[([^\]]+)\]")
        hash_re = re.compile(r"^\s*hash\s*=\s*([0-9a-fA-F]{8,16})\s*$")

        for line in lines:
            m_sec = sec_re.match(line)
            if m_sec:
                current_sec = m_sec.group(1).strip()

            # 记录 TextureOverride 下的 hash 用于冲突检测
            if current_sec.lower().startswith("textureoverride"):
                m_hash = hash_re.match(line)
                if m_hash:
                    h_val = m_hash.group(1).lower()
                    hash_registry.setdefault(h_val, []).append(ini_path)

            # 修复未定义的 $costume_mods 报错
            if "if $costume_mods" in line:
                new_lines.append(f"; [AutoFixed] {line}")
                modified = True
                continue

            # 修复 Windows 路径正斜杠引发的部分贴图 Resource 加载失败
            if line.strip().lower().startswith("filename") and "/" in line:
                fixed_line = line.replace("/", "\\")
                new_lines.append(fixed_line)
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
            except PermissionError as e:
                log.warning(f"PermissionError writing mod ini {ini_path}: {e}")
            except Exception as e:
                log.warning(f"Failed writing mod ini {ini_path}: {e}")

    def _apply_windows_fullscreen_opt_fix(self, logs: List[str]) -> None:
        try:
            import winreg
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
                        logs.append(f"[系统兼容层] 已为 {exe.name} 禁用全屏优化")
        except Exception as e:
            log.warning(f"Failed to set AppCompatFlags: {e}")