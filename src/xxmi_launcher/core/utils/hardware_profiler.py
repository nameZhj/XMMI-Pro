"""
@file: src/xxmi_launcher/core/utils/hardware_profiler.py
@brief: Hardware detection and adaptive graphics profile generator for Wuthering Waves
@exports: SystemHardwareProfiler, AdaptiveModConfig, HardwareSpecs
"""
import os
import re
import ctypes
import logging
import platform
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

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
    is_ssd: bool = True
    tier: str = "Mid"  # Low, Mid, High, Ultra


@dataclass
class AdaptiveModConfig:
    # Engine.ini 自适应参数
    streaming_pool_size: int = 3072
    lod_distance_scale: int = 15
    hidden_primitive_scale: int = 12
    frames_for_full_update: int = 0
    amortize_cpu_to_gpu_copy: int = 0
    fully_load_used_textures: int = 1
    # d3dx.ini 自适应参数
    init_delay_ms: int = 500
    cache_shaders: int = 1
    enable_hunting: int = 0
    enable_logging: int = 0
    # 启动器与兼容层参数
    force_dx11: bool = True
    disable_streamline: bool = True
    use_lightweight_transparency_fix: bool = False
    extra_launch_args: list[str] = field(default_factory=list)


class SystemHardwareProfiler:
    """自动探测用户 PC 硬件配置并生成免手动干预的《鸣潮》Mod 优化配置"""

    @classmethod
    def detect_hardware(cls, game_install_path: Optional[str] = None) -> HardwareSpecs:
        specs = HardwareSpecs()
        specs.cpu_cores = os.cpu_count() or 4
        specs.cpu_threads = specs.cpu_cores

        # 1. 探测系统物理内存 (Windows ctypes)
        if platform.system() == "Windows":
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
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                specs.ram_total_mb = int(stat.ullTotalPhys // (1024 * 1024))
            except Exception as e:
                log.warning(f"Failed to query system RAM via ctypes: {e}")

            # 2. 探测主显示器分辨率
            try:
                user32 = ctypes.windll.user32
                user32.SetProcessDPIAware()
                specs.screen_width = user32.GetSystemMetrics(0)
                specs.screen_height = user32.GetSystemMetrics(1)
            except Exception:
                pass

        # 3. 探测 GPU 型号与真实显存 (优先 nvidia-smi，回退 PowerShell CIM)
        cls._detect_gpu(specs)

        # 4. 评估硬件档位
        if specs.vram_mb >= 12288 and specs.ram_total_mb >= 24576:
            specs.tier = "Ultra"
        elif specs.vram_mb >= 8192 and specs.ram_total_mb >= 15000:
            specs.tier = "High"
        elif specs.vram_mb >= 6144:
            specs.tier = "Mid"
        else:
            specs.tier = "Low"

        return specs

    @classmethod
    def _detect_gpu(cls, specs: HardwareSpecs) -> None:
        creation_flags = 0x08000000 if platform.system() == "Windows" else 0  # CREATE_NO_WINDOW

        # 尝试通过 nvidia-smi 获取精确的独立显存容量（避免 WMI 4GB 溢出截断 bug）
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                creationflags=creation_flags,
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
                    return
        except Exception:
            pass

        # 回退方案：使用 PowerShell 查询注册表 qwMemorySize (64位值，解决 WMI 32位 uint 4GB 上限问题)
        if platform.system() == "Windows":
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
                    creationflags=creation_flags,
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
                        vram_mb = int(vram_str) // (1024 * 1024)
                        if vram_mb > best_vram:
                            best_vram = vram_mb
                            specs.gpu_name = name.strip()
                            specs.vram_mb = vram_mb
                upper_name = specs.gpu_name.upper()
                if "NVIDIA" in upper_name or "GEFORCE" in upper_name or "RTX" in upper_name or "GTX" in upper_name:
                    specs.gpu_vendor = "NVIDIA"
                elif "AMD" in upper_name or "RADEON" in upper_name:
                    specs.gpu_vendor = "AMD"
                elif "INTEL" in upper_name or "ARC" in upper_name:
                    specs.gpu_vendor = "Intel"
            except Exception as e:
                log.warning(f"Fallback GPU detection failed: {e}")

    @classmethod
    def build_adaptive_config(
        cls,
        specs: HardwareSpecs,
        has_reshade: bool = False,
        has_heavy_mods: bool = False
    ) -> AdaptiveModConfig:
        cfg = AdaptiveModConfig()

        # 1. 根据显存大小动态分配 UE4 纹理流送池与隐藏图元缩放
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
        else:  # Low (<6GB VRAM)
            cfg.streaming_pool_size = 1280
            cfg.lod_distance_scale = 8
            cfg.hidden_primitive_scale = 6
            cfg.use_lightweight_transparency_fix = True

        # 2. 根据 CPU 核心数与挂载插件计算 DLL 注入延迟 (修复 WWMI 0.9.5+ 高速 CPU 启动闪退)
        base_delay = 500 if specs.cpu_threads >= 12 else 350
        if has_reshade:
            base_delay += 200
        if has_heavy_mods:
            base_delay += 100
        cfg.init_delay_ms = min(base_delay, 1200)

        # 3. 构建启动参数
        args = []
        if cfg.force_dx11:
            args.extend(["-dx11", "-d3d11"])
        if specs.gpu_vendor == "NVIDIA" and cfg.disable_streamline:
            args.append("-DisableModule=streamline")
        cfg.extra_launch_args = args

        return cfg