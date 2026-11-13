"""
@file: src/xxmi_launcher/core/utils/wuwa_graphics_advisor.py
@brief: CPU/GPU inspection and real Wuthering Waves in-game graphics advisor for mod stability
@exports: GraphicsSettingRecommendation, HardwareGraphicsReport, WuwaGraphicsAdvisor
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import platform
import sqlite3
from typing import Dict, List, Optional, Tuple
import winreg

from core.utils.hardware_profiler import HardwareSpecs, detect_hardware

log = logging.getLogger(__name__)


@dataclass
class GraphicsSettingRecommendation:
    name: str
    menu_path: str
    recommended: str
    current_status: str
    is_compliant: Optional[bool]
    reason: str


@dataclass
class HardwareGraphicsReport:
    specs: HardwareSpecs
    cpu_name: str
    vram_gb: float
    system_ram_gb: int
    tier_label: str
    db_path: Optional[Path]
    critical_settings: List[GraphicsSettingRecommendation] = field(default_factory=list)
    hardware_settings: List[GraphicsSettingRecommendation] = field(default_factory=list)


class WuwaGraphicsAdvisor:
    """Inspects CPU/GPU specs and LocalStorage.db to recommend real Wuthering Waves graphics settings."""

    _TIER_LABELS: Dict[str, str] = {
        "Ultra": "旗舰配置 (Ultra)",
        "High": "高配流畅 (High)",
        "Mid": "主流均衡 (Mid)",
        "Low": "入门轻量 (Low)",
    }

    @staticmethod
    def _config_file() -> Path:
        cfg_dir = Path.home() / ".xxmi_launcher"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        return cfg_dir / "pre_launch_advisor.json"

    @classmethod
    def should_show_advisor(cls) -> bool:
        """Returns True unless user opted out of the pre-launch hardware advisor dialog."""
        cfg_file = cls._config_file()
        if not cfg_file.exists():
            return True
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            return bool(data.get("show_before_launch", True))
        except Exception:
            return True

    @classmethod
    def set_show_advisor(cls, enabled: bool) -> None:
        """Persists whether to display the pre-launch advisor before starting the game."""
        try:
            cls._config_file().write_text(
                json.dumps({"show_before_launch": bool(enabled)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            log.debug("Failed to save advisor preference: %s", exc)

    @staticmethod
    def find_local_storage_db(game_path: Optional[Path]) -> Optional[Path]:
        """Locates Wuthering Waves Client/Saved/LocalStorage/LocalStorage.db if present."""
        if not game_path:
            return None
        root = Path(game_path)
        candidates = [
            root / "Client" / "Saved" / "LocalStorage" / "LocalStorage.db",
            root / "Wuthering Waves Game" / "Client" / "Saved" / "LocalStorage" / "LocalStorage.db",
        ]
        for cand in candidates:
            if cand.is_file():
                return cand
        return None

    @staticmethod
    def _detect_cpu_name() -> str:
        """Reads Windows CPU brand string via registry with platform fallback."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            with key:
                val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                if str(val).strip():
                    return str(val).strip()
        except Exception:
            pass
        return platform.processor() or "Unknown CPU"

    @staticmethod
    def _read_db_settings(db_path: Optional[Path]) -> Dict[str, str]:
        """Reads real in-game settings keys from LocalStorage.db safely and closes handle."""
        values: Dict[str, str] = {}
        if not db_path or not db_path.is_file():
            return values
        keys = ("ImageDetail", "SkinDamageMode", "RayTracing", "CustomFrameRate")
        try:
            with closing(sqlite3.connect(db_path, timeout=3.0)) as conn:
                cur = conn.cursor()
                for key in keys:
                    row = cur.execute("SELECT value FROM LocalStorage WHERE key = ?", (key,)).fetchone()
                    if row and len(row) == 1:
                        values[key] = str(row[0]).strip().strip('"')
        except Exception as exc:
            log.debug("Unable to read LocalStorage.db (%s): %s", db_path, exc)
        return values

    @classmethod
    def _build_critical_settings(cls, db_vals: Dict[str, str]) -> List[GraphicsSettingRecommendation]:
        """Builds the real Wuthering Waves in-game settings strictly required for mod rendering."""
        img_detail = db_vals.get("ImageDetail")
        img_ok = (img_detail == "3") if img_detail is not None else None
        img_status = "已为高/极高" if img_ok else ("当前非最高档，建议调整" if img_ok is False else "启动后在游戏内确认")

        dmg_mode = db_vals.get("SkinDamageMode")
        dmg_ok = (dmg_mode == "0") if dmg_mode is not None else None
        dmg_status = "已关闭" if dmg_ok else ("当前已开启，可能导致破损花屏" if dmg_ok is False else "启动后在游戏内关闭")

        rt_val = db_vals.get("RayTracing")
        rt_ok = (rt_val in ("0", "False", "false")) if rt_val is not None else None
        rt_status = "已关闭" if rt_ok else ("当前已开启，与 DX11 模组冲突" if rt_ok is False else "建议保持关闭")

        return [
            GraphicsSettingRecommendation(
                name="画面细节 / 角色细节 (LOD Bias)",
                menu_path="设置 -> 图像 -> 画面细节",
                recommended="高 / 极高",
                current_status=img_status,
                is_compliant=img_ok,
                reason="避免中远距离自动降级模型 LOD，防止模组贴图错位、部件缺失或破皮。",
            ),
            GraphicsSettingRecommendation(
                name="战损表现 (Wounded Effect)",
                menu_path="设置 -> 图像 -> 战损表现",
                recommended="关闭",
                current_status=dmg_status,
                is_compliant=dmg_ok,
                reason="防止受击时叠加角色战损污染贴图层，导致模组皮肤或服装贴图花屏。",
            ),
            GraphicsSettingRecommendation(
                name="光线追踪 (Ray Tracing)",
                menu_path="设置 -> 图像 -> 光线追踪",
                recommended="关闭",
                current_status=rt_status,
                is_compliant=rt_ok,
                reason="WWMI 模组注入基于 DX11 渲染管线；开启光追或切换 DX12 会导致模组不生效。",
            ),
        ]

    @classmethod
    def _build_hardware_settings(cls, specs: HardwareSpecs, db_vals: Dict[str, str]) -> List[GraphicsSettingRecommendation]:
        """Generates 9 real Wuthering Waves Settings -> Graphics recommendations from CPU & GPU."""
        tier = specs.tier if specs.tier in cls._TIER_LABELS else "Mid"
        quality_map = {"Ultra": "极致", "High": "质量", "Mid": "均衡", "Low": "流畅"}
        shadow_map = {"Ultra": "极高", "High": "高", "Mid": "中", "Low": "低"}
        fx_map = {"Ultra": "高", "High": "高", "Mid": "中", "Low": "低"}

        fps_rec = "120 FPS" if (tier == "Ultra" and specs.cpu_threads >= 12) else ("60 FPS" if tier != "Low" else "60 FPS (CPU吃紧可选45 FPS)")
        cur_fps = db_vals.get("CustomFrameRate")
        fps_status = f"当前配置值: {cur_fps}" if cur_fps else f"CPU {specs.cpu_threads} 线程适配"

        is_rtx = specs.gpu_vendor == "NVIDIA" and "rtx" in specs.gpu_name.lower()
        if is_rtx:
            upscale_rec = "NVIDIA DLSS 开启 (质量档) + NVIDIA Reflex 开启"
        elif specs.gpu_vendor == "Intel":
            upscale_rec = "Intel XeSS 开启 (质量档)"
        else:
            upscale_rec = "AMD FSR 开启 (质量档)"

        volumetric_rec = "体积雾: 开启 / 体积光照: 开启" if tier in ("Ultra", "High") else "体积雾: 关闭 / 体积光照: 关闭"
        vram_gb = round(specs.vram_mb / 1024.0, 1)

        return [
            GraphicsSettingRecommendation("图形质量预设", "设置 -> 图像 -> 图形质量", quality_map[tier], f"显存 {vram_gb} GB", None, "依据 GPU 与显存容量给出基准预设"),
            GraphicsSettingRecommendation("帧率上限", "设置 -> 图像 -> 帧率", fps_rec, fps_status, None, "避免 CPU 单核调度过载造成角色切换掉帧"),
            GraphicsSettingRecommendation("超分辨率 / 低延迟", "设置 -> 图像 -> 超分辨率", upscale_rec, f"{specs.gpu_vendor} GPU 匹配", None, "减轻高模多边形渲染压力并提升流畅度"),
            GraphicsSettingRecommendation("阴影质量", "设置 -> 图像 -> 阴影质量", shadow_map[tier], f"{tier} 档推荐", None, "平衡实时投影清晰度与 GPU 渲染耗时"),
            GraphicsSettingRecommendation("特效质量", "设置 -> 图像 -> 特效质量", fx_map[tier], f"{tier} 档推荐", None, "保证技能与模组发光粒子清晰且不拖垮帧率"),
            GraphicsSettingRecommendation("次表面散射", "设置 -> 图像 -> 次表面散射", "开启", "建议开启", None, "保持角色皮肤模组正常透光质感，防死白"),
            GraphicsSettingRecommendation("抗锯齿", "设置 -> 图像 -> 抗锯齿", "开启", "建议开启", None, "抑制高精细发丝与服饰模组边缘锯齿闪烁"),
            GraphicsSettingRecommendation("物理抖动 (布料/发丝)", "设置 -> 图像 -> 物理抖动", "开启", "建议开启", None, "确保带骨骼物理的模组头发与裙摆正常摆动"),
            GraphicsSettingRecommendation("体积雾 / 体积光照 / 动态模糊", "设置 -> 图像 -> 高级项", f"{volumetric_rec}，动态模糊: 关闭", "显存优化建议", None, "关闭动态模糊可显著提升高速动作下模组观感"),
        ]

    @classmethod
    def analyze_and_recommend(cls, game_path: Optional[Path] = None) -> HardwareGraphicsReport:
        """Detects PC CPU/GPU specs and builds real Wuthering Waves graphics settings guidance."""
        path_str = str(game_path) if game_path else None
        specs = detect_hardware(path_str)
        cpu_name = cls._detect_cpu_name()
        db_path = cls.find_local_storage_db(game_path)
        db_vals = cls._read_db_settings(db_path)
        vram_gb = round(specs.vram_mb / 1024.0, 1)
        ram_gb = max(1, round(specs.ram_total_mb / 1024.0))
        tier_label = cls._TIER_LABELS.get(specs.tier, specs.tier)
        return HardwareGraphicsReport(
            specs=specs,
            cpu_name=cpu_name,
            vram_gb=vram_gb,
            system_ram_gb=ram_gb,
            tier_label=tier_label,
            db_path=db_path,
            critical_settings=cls._build_critical_settings(db_vals),
            hardware_settings=cls._build_hardware_settings(specs, db_vals),
        )

    @classmethod
    def apply_critical_mod_settings(cls, game_path: Optional[Path]) -> Tuple[bool, List[str]]:
        """Writes ImageDetail=3, SkinDamageMode=0, RayTracing=0 into LocalStorage.db safely."""
        logs: List[str] = []
        db_path = cls.find_local_storage_db(game_path)
        if db_path and db_path.is_file():
            targets = [
                ("ImageDetail", "3"),
                ("SkinDamageMode", "0"),
                ("RayTracing", "0"),
                ("RayTracedReflection", "0"),
                ("RayTracedGI", "0"),
            ]
            try:
                with closing(sqlite3.connect(db_path, timeout=5.0)) as conn:
                    cur = conn.cursor()
                    for key, val in targets:
                        cur.execute(
                            "INSERT INTO LocalStorage (key, value) VALUES (?, ?) "
                            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                            (key, val),
                        )
                    conn.commit()
                logs.append("已自动应用 LocalStorage.db 模组兼容项 (画面细节=高, 战损=关, 光追=关)")
            except Exception as exc:
                log.warning("Failed updating LocalStorage.db: %s", exc)
                logs.append(f"写入 LocalStorage.db 失败: {exc}")
        if game_path:
            try:
                from core.packages.model_importers.launch_safety_guard import LaunchSafetyGuard
                LaunchSafetyGuard.prevent_dx11_raytracing_deadlock(game_path)
                logs.append("已同步校验 GameUserSettings.ini DX11 光追禁用状态")
            except Exception as exc:
                log.debug("Raytracing guard skipped: %s", exc)
        return len(logs) > 0, logs
