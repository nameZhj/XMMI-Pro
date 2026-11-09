"""
@file: src/xxmi_launcher/core/utils/hardware_profiler.py
@brief: Hardware detection and zero-config adaptive parameter calculation for Wuthering Waves
@exports: SystemHardwareProfiler, AdaptiveModConfig, HardwareSpecs, build_adaptive_config, detect_hardware
"""
import os
import re
import ctypes
import logging
import platform
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

log = logging.getLogger(__name__)


@dataclass
class HardwareSpecs:
    cpu_cores: int = 4
    cpu_threads: int = 8
    ram_total_mb: int = 16384
    gpu_name: str = "Unknown GPU"
    gpu_vendor: str = "Unknown"  # NVIDIA, AMD, Intel
    vram_mb: int = 6144
    screen_width: int = 1920
    screen_height: int = 1080
    is_integrated_gpu: bool = False
    is_ssd: bool = True
    tier: str = "Mid"  # Low, Mid, High, Ultra


@dataclass
class AdaptiveModConfig:
    # Engine.ini parameters
    streaming_pool_size: int = 2048
    lod_distance_scale: int = 12
    hidden_primitive_scale: int = 8
    frames_for_full_update: int = 0
    amortize_cpu_to_gpu_copy: int = 0
    fully_load_used_textures: int = 1

    # d3dx.ini parameters
    init_delay_ms: int = 350
    cache_shaders: int = 1
    enable_hunting: int = 0
    enable_logging: int = 0

    # Launch args & compatibility
    force_dx11: bool = True
    disable_streamline: bool = True
    use_lightweight_transparency_fix: bool = False
    extra_launch_args: List[str] = field(default_factory=lambda: ["-dx11", "-d3d11"])
    tier: str = "Mid"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "r.Streaming.PoolSize": self.streaming_pool_size,
            "r.Kuro.SkeletalMesh.LODDistanceScale": self.lod_distance_scale,
            "r.Streaming.HiddenPrimitiveScale": self.hidden_primitive_scale,
            "delay": self.init_delay_ms,
            "launch_args": list(self.extra_launch_args),
            "tier": self.tier,
            "streaming_pool_size": self.streaming_pool_size,
            "lod_distance_scale": self.lod_distance_scale,
            "hidden_primitive_scale": self.hidden_primitive_scale,
            "init_delay_ms": self.init_delay_ms,
            "extra_launch_args": list(self.extra_launch_args),
        }

    def __getitem__(self, key: str) -> Any:
        d = self.to_dict()
        if key in d:
            return d[key]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()

    def items(self):
        return self.to_dict().items()

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()


class SystemHardwareProfiler:
    """自动探测用户 PC 硬件配置并计算零手动干预的《鸣潮》Mod 优化配置"""

    @classmethod
    def detect_hardware(cls, game_install_path: Optional[str] = None) -> HardwareSpecs:
        specs = HardwareSpecs()

        # 1. CPU 线程数
        try:
            threads = os.cpu_count() or 4
            specs.cpu_threads = threads
            specs.cpu_cores = max(threads // 2, 1) if threads > 1 else 1
        except Exception as e:
            log.warning(f"Error querying CPU threads: {e}")

        # 2. 物理内存与屏幕分辨率 (Windows ctypes)
        if platform.system() == "Windows":
            cls._detect_windows_ram_and_screen(specs)

        # 3. GPU 型号与真实显存
        cls._detect_gpu(specs)

        # 4. 评估硬件档位
        cls._evaluate_tier(specs)

        return specs

    @classmethod
    def _detect_windows_ram_and_screen(cls, specs: HardwareSpecs) -> None:
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                specs.ram_total_mb = int(stat.ullTotalPhys // (1024 * 1024))
        except Exception as e:
            log.warning(f"Failed to query system RAM via ctypes: {e}")

        try:
            user32 = ctypes.windll.user32
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            if w > 0 and h > 0:
                specs.screen_width = w
                specs.screen_height = h
        except Exception as e:
            log.warning(f"Failed to query screen metrics: {e}")

    @classmethod
    def _detect_gpu(cls, specs: HardwareSpecs) -> None:
        c_flags = 0x08000000 if platform.system() == "Windows" else 0

        # 优先方式：无窗口调用 nvidia-smi 获取独立显卡及显存
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                creationflags=c_flags,
                timeout=3,
                text=True,
                encoding="utf-8",
                errors="ignore",
                stderr=subprocess.DEVNULL
            ).strip()
            if out:
                first_line = out.splitlines()[0]
                parts = [p.strip() for p in first_line.split(",")]
                if len(parts) >= 2:
                    specs.gpu_name = parts[0]
                    specs.gpu_vendor = "NVIDIA"
                    specs.vram_mb = int(float(parts[1]))
                    specs.is_integrated_gpu = False
                    return
        except Exception:
            pass

        # 回退方式：PowerShell 查询注册表 64位 HardwareInformation.qwMemorySize
        if platform.system() == "Windows":
            cls._detect_gpu_via_registry(specs, c_flags)

    @classmethod
    def _detect_gpu_via_registry(cls, specs: HardwareSpecs, c_flags: int) -> None:
        ps_cmd = (
            "Get-ItemProperty -Path 'HKLM:\\SYSTEM\\ControlSet001\\Control\\Class\\"
            "{4d36e968-e325-11ce-bfc1-08002be10318}\\0*' -ErrorAction SilentlyContinue | "
            "ForEach-Object { "
            "$name = $_.'DriverDesc'; "
            "$vram = $_.'HardwareInformation.qwMemorySize'; "
            "if ($name -and $vram) { Write-Output \"$name|$vram\" } "
            "}"
        )
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                creationflags=c_flags,
                timeout=4,
                text=True,
                encoding="utf-8",
                errors="ignore",
                stderr=subprocess.DEVNULL
            ).strip()
            best_vram = 0
            for line in out.splitlines():
                if "|" in line:
                    name, vram_str = line.split("|", 1)
                    try:
                        vram_mb = int(vram_str) // (1024 * 1024)
                        if vram_mb > best_vram:
                            best_vram = vram_mb
                            specs.gpu_name = name.strip()
                            specs.vram_mb = vram_mb
                    except ValueError:
                        continue

            upper = specs.gpu_name.upper()
            if any(k in upper for k in ["NVIDIA", "GEFORCE", "RTX", "GTX"]):
                specs.gpu_vendor = "NVIDIA"
            elif any(k in upper for k in ["AMD", "RADEON"]):
                specs.gpu_vendor = "AMD"
            elif any(k in upper for k in ["INTEL", "ARC"]):
                specs.gpu_vendor = "Intel"

            if any(k in upper for k in ["HD GRAPHICS", "UHD GRAPHICS", "IRIS", "VEGA", "RADEON(TM) GRAPHICS"]) or specs.vram_mb < 2048:
                specs.is_integrated_gpu = True
        except Exception as e:
            log.warning(f"Fallback GPU registry detection failed: {e}")

    @classmethod
    def _evaluate_tier(cls, specs: HardwareSpecs) -> None:
        # Ultra (VRAM >= 12GB 且 RAM >= 24GB)
        if specs.vram_mb >= 12288 and specs.ram_total_mb >= 24576:
            specs.tier = "Ultra"
        # High (VRAM >= 8GB 且 RAM >= 15GB)
        elif specs.vram_mb >= 8192 and specs.ram_total_mb >= 15000:
            specs.tier = "High"
        # Mid (VRAM >= 6GB)
        elif specs.vram_mb >= 6144 and not specs.is_integrated_gpu:
            specs.tier = "Mid"
        # Low (VRAM < 6GB 或核显)
        else:
            specs.tier = "Low"

    @classmethod
    def build_adaptive_config(
        cls,
        specs: HardwareSpecs,
        has_reshade: bool = False,
        has_heavy_mods: bool = False
    ) -> AdaptiveModConfig:
        cfg = AdaptiveModConfig()
        cfg.tier = specs.tier

        # 1. 显存档位对应参数
        if specs.tier == "Ultra":
            cfg.streaming_pool_size = 5120
            cfg.lod_distance_scale = 25
            cfg.hidden_primitive_scale = 16
            cfg.use_lightweight_transparency_fix = False
        elif specs.tier == "High":
            cfg.streaming_pool_size = 3584
            cfg.lod_distance_scale = 20
            cfg.hidden_primitive_scale = 12
            cfg.use_lightweight_transparency_fix = False
        elif specs.tier == "Mid":
            cfg.streaming_pool_size = 2048
            cfg.lod_distance_scale = 12
            cfg.hidden_primitive_scale = 8
            cfg.use_lightweight_transparency_fix = True
        else:  # Low
            cfg.streaming_pool_size = 1280
            cfg.lod_distance_scale = 8
            cfg.hidden_primitive_scale = 6
            cfg.use_lightweight_transparency_fix = True

        # 2. d3dx.ini delay (高频 CPU 注入过早崩溃保护)
        base_delay = 500 if specs.cpu_threads >= 12 else 350
        if has_reshade:
            base_delay += 200
        if has_heavy_mods:
            base_delay += 100
        cfg.init_delay_ms = min(base_delay, 1200)

        # 3. 启动参数
        args = ["-dx11", "-d3d11"]
        if specs.gpu_vendor == "NVIDIA":
            args.append("-DisableModule=streamline")
        cfg.extra_launch_args = args

        return cfg


def detect_hardware(game_install_path: Optional[str] = None) -> HardwareSpecs:
    """快捷入口：探测当前 PC 硬件配置"""
    try:
        return SystemHardwareProfiler.detect_hardware(game_install_path)
    except Exception as e:
        log.warning(f"Unexpected error in detect_hardware: {e}")
        return HardwareSpecs()


def build_adaptive_config(
    specs: HardwareSpecs,
    has_reshade: bool = False,
    has_heavy_mods: bool = False
) -> AdaptiveModConfig:
    """快捷入口：根据硬件规格生成自适应配置参数字典/对象"""
    try:
        return SystemHardwareProfiler.build_adaptive_config(specs, has_reshade, has_heavy_mods)
    except Exception as e:
        log.warning(f"Unexpected error in build_adaptive_config: {e}")
        return AdaptiveModConfig()



def detect_hardware(game_install_path: Optional[str] = None) -> HardwareSpecs:
    """快捷入口：探测当前 PC 硬件配置"""
    try:
        return SystemHardwareProfiler.detect_hardware(game_install_path)
    except Exception as e:
        log.warning(f"Unexpected error in detect_hardware: {e}")
        return HardwareSpecs()


def build_adaptive_config(
    specs: HardwareSpecs,
    has_reshade: bool = False,
    has_heavy_mods: bool = False
) -> AdaptiveModConfig:
    """快捷入口：根据硬件规格生成自适应配置参数字典/对象"""
    try:
        return SystemHardwareProfiler.build_adaptive_config(specs, has_reshade, has_heavy_mods)
    except Exception as e:
        log.warning(f"Unexpected error in build_adaptive_config: {e}")
        return AdaptiveModConfig()