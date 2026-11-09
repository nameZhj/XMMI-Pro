"""
@file: src/xxmi_launcher/core/packages/model_importers/wwmi_package.py
@brief: Wuthering Waves model importer package with dual-layer path resolution and lossless config writing
@exports: WWMIPackage, WWMIConfig, WWMIPackageConfig
"""
import os
import json
import sqlite3
import logging

from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

import core.path_manager as Paths
import core.event_manager as Events
import core.config_manager as Config

from core.locale_manager import L
from core.package_manager import PackageMetadata

from core.utils.ini_handler import IniHandler, IniHandlerSettings
from core.utils.lossless_ini_editor import LosslessIniEditor, make_file_writable
from core.config.enums import InjectMode, GameLaunch, WuWaResourceTier
from core.packages.model_importers.model_importer import ModelImporterPackage, ModelImporterConfig, Version
from core.packages.migoto_package import MigotoManagerConfig
from core.platforms.game import Game
from core.utils.process_manager import LaunchContext, ExecutableLaunch

log = logging.getLogger(__name__)


@dataclass
class WWMIConfig(ModelImporterConfig):
    game: Game = Game.WUTHERING_WAVES
    game_exe_names: list[str] = field(default_factory=lambda: ['Wuthering Waves.exe'])
    process_exe_names: list[str] = field(default_factory=lambda: ['Client-Win64-Shipping.exe'])
    process_exe_rel_paths: list[str] = field(default_factory=lambda: ['Client/Binaries/Win64'])
    game_folder_names: list[str] = field(default_factory=lambda: ['Wuthering Waves Game'])
    game_folder_children: list[str] = field(default_factory=lambda: ['Client', 'Data'])
    game_process_exe: str = "Client-Win64-Shipping.exe"
    importer_folder: str = 'WWMI/'
    use_launch_options: bool = False
    launch_options: str = '-SkipSplash'
    d3d11_mode_cmd_args: str = "-dx11"
    xxmi_dll_init_delay: int = 500
    xxmi_dll_inject_mode: InjectMode = InjectMode.DIRECT
    d3dx_ini: dict[str, dict[str, dict[str, Any]]] = field(default_factory=lambda: {
        'core': {
            'Loader': {
                'loader': 'XXMI Launcher.exe',
            },
        },
        'enforce_rendering': {
            'Rendering': {
                'texture_hash': 1,
                'track_texture_updates': 1,
                'track_region_hashes': 0,
                'allow_buffer_resize': 1,
            },
        },
        'enable_hunting': {
            'Hunting': {
                'hunting': {'on': 2, 'off': 0},
            },
        },
        'dump_shaders': {
            'Hunting': {
                'marking_actions': {'on': 'clipboard hlsl asm regex', 'off': 'clipboard'},
            },
        },
    })
    unlock_fps: bool = False
    force_max_lod_bias: bool = False
    disable_wounded_fx: bool = False
    disable_wounded_fx_warned: bool = False
    mesh_lod_distance_lod_base_fov: int = 165
    resource_tier: WuWaResourceTier = WuWaResourceTier.HD
    resource_tier_warned: bool = False


@dataclass
class WWMIPackageConfig:
    Importer: WWMIConfig = field(
        default_factory=lambda: WWMIConfig()
    )
    Migoto: MigotoManagerConfig = field(
        default_factory=lambda: MigotoManagerConfig()
    )


class WWMIPackage(ModelImporterPackage):
    def __init__(self):
        super().__init__(PackageMetadata(
            package_name='WWMI',
            auto_load=False,
            github_repo_owner='SpectrumQT',
            github_repo_name='WWMI-Package',
            asset_version_pattern=r'.*(\d\.\d\.\d).*',
            asset_name_format='WWMI-PACKAGE-v%s.zip',
            signature_pattern=r'^## Signature[\r\n]+- ((?:[A-Za-z0-9+\/]{4})*(?:[A-Za-z0-9+\/]{4}|[A-Za-z0-9+\/]{3}=|[A-Za-z0-9+\/]{2}={2}))\r?$',
            signature_public_key='MHYwEAYHKoZIzj0CAQYFK4EEACIDYgAEYac352uRGKZh6LOwK0fVDW/TpyECEfnRtUp+bP2PJPP63SWOkJ3a/d9pAnPfYezRVJ1hWjZtpRTT8HEAN/b4mWpJvqO43SAEV/1Q6vz9Rk/VvRV3jZ6B/tmqVnIeHKEb',
            exit_after_update=False,
            installation_path='WWMI/',
            requirements=['XXMI'],
        ))

    def get_installed_version(self):
        try:
            return str(Version(Config.Importers.WWMI.Importer.importer_path / 'Core' / 'WWMI' / 'WuWa-Model-Importer.ini', pattern=r'^global \$wwmi_version = (\d+)\.*(\d)(\d*)'))
        except Exception as e:
            return ''

    def normalize_game_path(self, game_path: Path) -> Path:
        if not game_path.is_absolute():
            raise ValueError(L('error_game_path_not_absolute', 'Failed to normalize path {path}: Path is not absolute!').format(path=game_path))

        if game_path.is_file():
            game_path = game_path.parent

        def is_valid_client_root(cand: Path) -> bool:
            if not cand or not cand.is_dir():
                return False
            shipping_exe = cand / 'Client' / 'Binaries' / 'Win64' / 'Client-Win64-Shipping.exe'
            return shipping_exe.is_file()

        # 1. 优先校验双层嵌套目录: Wuthering Waves Game
        nested_cand = game_path / 'Wuthering Waves Game'
        if is_valid_client_root(nested_cand):
            return nested_cand

        # 2. 当前目录即包含有效 Client/Binaries/Win64/Client-Win64-Shipping.exe
        if is_valid_client_root(game_path):
            return game_path

        # 3. 向上逐级回溯（针对用户选择子目录的情况，如 Client 或 Win64 目录）
        for parent_dir in game_path.parents:
            if is_valid_client_root(parent_dir):
                return parent_dir
            if is_valid_client_root(parent_dir / 'Wuthering Waves Game'):
                return parent_dir / 'Wuthering Waves Game'

        # 4. 深度检索定位 Client-Win64-Shipping.exe
        for shipping_exe in game_path.glob('**/Client-Win64-Shipping.exe'):
            try:
                root_cand = shipping_exe.parents[3]
                if is_valid_client_root(root_cand):
                    return root_cand
            except IndexError:
                pass

        if (game_path / 'Wuthering Waves.exe').is_file():
            return game_path

        game_path_original = game_path
        for path in game_path.rglob('*.exe'):
            if path.name == 'Wuthering Waves.exe' and path.is_file():
                cand = Path(path).parent
                if is_valid_client_root(cand / 'Wuthering Waves Game'):
                    return cand / 'Wuthering Waves Game'
                return cand

        raise ValueError(L('error_wuthering_waves_exe_not_found', 'Failed to normalize path {path}: Wuthering Waves.exe or Client-Win64-Shipping.exe not found!').format(path=game_path_original))

    def autodetect_game_folders(self) -> list[Path]:
        paths = self.reg_search_game_folders(Config.Active.Importer.process_exe_names)

        kuro_launcher_path = Path(os.getenv('APPDATA')) / 'KRLauncher'
        for root, dirs, files in kuro_launcher_path.walk():
            for file in files:
                if file != 'kr_starter_game.json':
                    continue
                file_path = root / file
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        path = json.load(f).get('path', None)
                        if path is not None:
                            paths.append(path)
                except:
                    continue

        result = []

        for path in paths:
            try:
                result.append(self.normalize_game_path(path))
            except:
                pass

        return result

    def validate_game_path(self, game_folder):
        game_path = super().validate_game_path(game_folder)
        game_path = self.normalize_game_path(game_path)

        shipping_exe = game_path / 'Client' / 'Binaries' / 'Win64' / 'Client-Win64-Shipping.exe'
        exe_path = game_path / 'Wuthering Waves.exe'
        if not exe_path.is_file() and (game_path.parent / 'Wuthering Waves.exe').is_file():
            exe_path = game_path.parent / 'Wuthering Waves.exe'

        if not exe_path.is_file() and not shipping_exe.is_file():
            raise ValueError(L('error_wwmi_game_folder_missing_files', 'Game folder must contain `Wuthering Waves.exe` or `Client-Win64-Shipping.exe`!'))

        common_folder = self.get_parent_directory(game_path, 'common')
        if common_folder is not None and common_folder.parent.name == 'steamapps':
            if game_path.parent.name != 'common':
                Events.Fire(Events.Application.ShowError(
                    modal=True,
                    confirm_text=L('message_button_ok', 'OK'),
                    message=L('message_text_wwmi_invalid_steam_installation', """
                        Invalid Wuthering Waves installation detected for Steam:
                        {game_path}
                        
                        {folder_name} folder with {exe_name} must be directly placed in:
                        {common_folder}
                        
                        Please run game file repair via Steam or fix it manually.
                    """).format(
                        game_path=game_path, folder_name=game_path.name, exe_name=exe_path.name, common_folder=common_folder
                    )
                ))
                raise ValueError(L('error_steam_game_repair_required', 'Game installation must be repaired via Steam!'))

        for dir_name in ['Client']:
            if dir_name not in [x.name for x in game_path.iterdir() if x.is_dir()]:
                raise ValueError(L('error_game_folder_missing_folder', 'Game folder must contain {dir_name} folder!').format(dir_name=dir_name))
        return game_path

    @staticmethod
    def _resolve_shipping_exe(game_path: Path | None) -> Path | None:
        """解析鸣潮核心主执行程序 Client-Win64-Shipping.exe 路径"""
        if not game_path:
            return None
        candidates = [
            game_path / "Client" / "Binaries" / "Win64" / "Client-Win64-Shipping.exe",
            game_path / "Wuthering Waves Game" / "Client" / "Binaries" / "Win64" / "Client-Win64-Shipping.exe",
            game_path.parent / "Wuthering Waves Game" / "Client" / "Binaries" / "Win64" / "Client-Win64-Shipping.exe",
            game_path.parent / "Client" / "Binaries" / "Win64" / "Client-Win64-Shipping.exe",
        ]
        for cand in candidates:
            if cand.is_file():
                return cand
        for p in game_path.glob("**/Client-Win64-Shipping.exe"):
            if p.is_file():
                return p
        return None

    def _apply_hardware_optimization_and_repair(
        self,
        launch_context: LaunchContext,
        game_path: Path | None,
    ) -> None:
        """根据硬件配置自动优化 Engine.ini / d3dx.ini / 启动参数，检测版本更新自愈，并启动防崩守护线程"""
        try:
            target_game_path = game_path or Path(Config.Importers.WWMI.Importer.game_folder)
            wwmi_root = Path(Config.Importers.WWMI.Importer.importer_path)
            if not target_game_path or not target_game_path.exists():
                log.warning("Game path not found, skipping WWMI hardware adaptive optimization.")
                return

            if not wwmi_root.exists():
                log.warning("WWMI importer root not found, skipping WWMI hardware adaptive optimization.")
                return

            from core.packages.model_importers.wwmi_fixer import WWMIRepairAndOptimizer
            from core.packages.model_importers.launch_safety_guard import LaunchSafetyGuard
            optimizer = WWMIRepairAndOptimizer(target_game_path, wwmi_root)

            # 硬件自适应优化与参数写入
            specs, adaptive_cfg, opt_logs = optimizer.apply_hardware_adaptive_optimization()
            for log_line in opt_logs:
                log.info(log_line)

            Config.Importers.WWMI.Importer.xxmi_dll_init_delay = adaptive_cfg.init_delay_ms
            if hasattr(Config.Active, 'Importer'):
                Config.Active.Importer.xxmi_dll_init_delay = adaptive_cfg.init_delay_ms

            # 通过 LaunchSafetyGuard 安全过滤并注入引擎启动参数
            safe_extra_args = LaunchSafetyGuard.filter_launch_args_for_exe(
                getattr(launch_context.target, "exe_path", None),
                adaptive_cfg.extra_launch_args
            )
            if isinstance(launch_context.target, ExecutableLaunch):
                existing_parts = launch_context.target.cmd_args.split()
                existing_keys = {p.split("=")[0].lower() for p in existing_parts}
                for arg in safe_extra_args:
                    arg_clean = arg.strip()
                    arg_key = arg_clean.split("=")[0].lower()
                    if arg_clean and arg_key not in existing_keys:
                        launch_context.target.cmd_args = (launch_context.target.cmd_args + " " + arg_clean).strip()
                        existing_keys.add(arg_key)

            Events.Fire(Events.Application.StatusUpdate(
                status=L(
                    'status_hardware_adaptive_optimized',
                    'Applied {tier} hardware adaptive optimization (VRAM: {vram}MB, CPU: {cpu}T)'
                ).format(
                    tier=specs.tier,
                    vram=specs.vram_mb,
                    cpu=specs.cpu_threads,
                )
            ))

            # 检测鸣潮版本更新并自愈着色器编译缓存
            is_version_updated = optimizer.check_game_version_updated()
            if is_version_updated:
                log.info("[版本更新自愈] 检测到鸣潮客户端版本更新，自动清空陈旧着色器缓存以防 UE4 Fatal Error")

            report = optimizer.scan_and_repair_mods(purge_shader_cache=is_version_updated, auto_disable_conflicts=True)
            if report.get("disabled_conflict_folders"):
                isolated_cnt = len(report["disabled_conflict_folders"])
                Events.Fire(Events.Application.StatusUpdate(
                    status=L(
                        'status_mod_conflicts_isolated',
                        'Isolated {count} conflicting mod folders to prevent crashing'
                    ).format(count=isolated_cnt)
                ))
                log.warning(f"Auto-isolated {isolated_cnt} conflicting mod folders: {report['disabled_conflict_folders']}")

            # 启动 25 秒防崩监控与自动回滚守护线程
            LaunchSafetyGuard.start_crash_monitor_thread(target_game_path, wwmi_root)

        except Exception as e:
            log.warning(f"Error during WWMI auto optimization and repair: {e}", exc_info=True)

    def override_launch_context(
        self,
        launch_context: LaunchContext,
        game_path: Path | None,
        game_exe_path: Path | None,
    ) -> None:
        # 固定拉起目标为真正的 Client-Win64-Shipping.exe，防止外层引导程序丢参数与注入
        shipping_exe = self._resolve_shipping_exe(game_path) or game_exe_path
        if shipping_exe and shipping_exe.exists():
            launch_context.target.exe_path = shipping_exe
            launch_context.work_dir = shipping_exe.parent
            launch_context.process_name = shipping_exe.name

        self._apply_hardware_optimization_and_repair(launch_context, game_path)

        if Config.Importers.WWMI.Importer.game_launch != GameLaunch.DIRECT:
            return

        if not Config.Importers.WWMI.Importer.use_launch_options or "krqlv" not in Config.Importers.WWMI.Importer.launch_options:
            self.notify_resource_tier()
            if "-krqlv=" not in launch_context.target.cmd_args.lower():
                launch_context.target.cmd_args += f" -krqlv={Config.Importers.WWMI.Importer.resource_tier.name.lower()}"

    def optimize_mods(self, event: Events.ModelImporter.OptimizeMods):
        """响应用户触发的‘深度修复 Mod’事件，彻底清空 ShaderCache 编译缓存并深度修复"""
        try:
            game_path = Path(Config.Importers.WWMI.Importer.game_folder)
            wwmi_root = Path(Config.Importers.WWMI.Importer.importer_path)
            if game_path.exists() and wwmi_root.exists():
                from core.packages.model_importers.wwmi_fixer import WWMIRepairAndOptimizer
                optimizer = WWMIRepairAndOptimizer(game_path, wwmi_root)
                optimizer.scan_and_repair_mods(purge_shader_cache=True, auto_disable_conflicts=True)
                log.info("[深度修复] 用户手动触发模组优化，已清空着色器编译缓存")
        except Exception as e:
            log.warning(f"Error in WWMIPackage.optimize_mods cache purge: {e}")
        super().optimize_mods(event)

    @staticmethod
    def notify_resource_tier():
        if Config.Importers.WWMI.Importer.resource_tier_warned:
            return

        resource_tiers = {item: item.value for item in WuWaResourceTier}

        (user_confirmed_resource_tier, resource_tier_id) = Events.Call(Events.Application.ShowWarning(
            title=L('message_title_resource_tier_selection', "Select Resource Quality"),
            message=L('message_text_resource_tier_selection', """
                **{game}** requires **[Resource Quality]({page_link})** to be selected to avoid game crash on loading.
                
                For **Steam** and **Epic Games** installations select **{default_tier}**.
                
                For **official launcher** installation select **any actually downloaded** tier (default is usually **{default_tier}**):
            
                {radio_widget}
                
                You can also change it later with **{general_settings_wuwa_resource_tier_label}** in **General Settings**.
            """).format(
                game=Config.Importers.WWMI.Importer.game.value,
                page_link=r"https://wutheringwaves.kurogames.com/en/main/news/detail/5513",
                default_tier=WuWaResourceTier.HD.value,
            ),
            confirm_text=L('message_button_confirm', 'Confirm'),
            cancel_text=L('message_button_open_settings', 'Open Settings'),
            radio_options=list(resource_tiers.values()),
            selected_id=1,
            modal=True,
        ))

        if user_confirmed_resource_tier is not None:
            Config.Importers.WWMI.Importer.resource_tier_warned = True

            if user_confirmed_resource_tier is True:
                Config.Importers.WWMI.Importer.resource_tier = list(resource_tiers.keys())[resource_tier_id]

    def configure_game_settings(self, game_path: Path | None, game_exe_path: Path | None):
        # Auto-config below requires reliably detectable installation location.
        if Config.Importers.WWMI.Importer.game_launch not in [GameLaunch.DIRECT, GameLaunch.STEAM, GameLaunch.EPIC_GAMES]:
            return
        if not game_path:
            return

        # Configure GameUserSettings.ini.
        if Config.Importers.WWMI.Importer.unlock_fps:
            self.update_game_user_settings_ini(game_path)

        # Configure LocalStorage.db.
        if Config.Importers.WWMI.Importer.configure_game or Config.Importers.WWMI.Importer.unlock_fps:
            self.configure_settings(game_path)

        # Prevent further configuration if WWMI isn't going to be used.
        if not Config.Active.Importer.is_xxmi_dll_used():
            return

        # Configure Engine.ini.
        self.update_engine_ini(game_path)

        # Configure UserEngine.ini.
        self.update_user_engine_ini(game_path)

    def configure_settings(self, game_path: Path):
        Events.Fire(Events.Application.StatusUpdate(status=L('status_configuring_settings', 'Configuring in-game settings...')))

        try:
            with SettingsManager(game_path) as settings_manager:
                if Config.Importers.WWMI.Importer.unlock_fps:
                    # Set frame rate to 120
                    settings_manager.set_fps_setting(120)
                else:
                    # Remove any existing triggers locking the frame rate setting
                    settings_manager.reset_fps_setting()

                if not Config.Active.Importer.is_xxmi_dll_used():
                    return

                if not Config.Importers.WWMI.Importer.configure_game:
                    return

                # Set "LOD Bias" to "Ultra High" - required to force high quality textures mods are made for
                if Config.Importers.WWMI.Importer.force_max_lod_bias:
                    settings_manager.set_setting('ImageDetail', '3')

                # Force Ray Tracing Off as it doesn't work with DX11 aka WWMI
                settings_manager.set_setting('RayTracing', '0')
                settings_manager.set_setting('RayTracedReflection', '0')
                settings_manager.set_setting('RayTracedGI', '0')

                # Take care of Wounded Effect that 'breaks' modded textures if not handled properly
                if not Config.Importers.WWMI.Importer.disable_wounded_fx_warned:
                    if settings_manager.get_setting('SkinDamageMode') == '1':
                        user_dialogue = Events.Application.ShowWarning(
                            modal=True,
                            title=L('message_title_wounded_effect_detected', 'Wounded Effect Detected'),
                            confirm_text=L('message_button_disable', 'Disable'),
                            cancel_text=L('message_button_keep_enabled', 'Keep Enabled'),
                            message=L('message_text_wounded_effect_detected', """
                                Looks like Wounded Effect is enabled in game settings.
                                It is not supported by most mods and textures will break after few hits taken.
                                
                                Click `Disable` to turn it Off and ensure proper rendering of modded textures.
                                Click `Keep Enabled` if you never get hit or use Injured Effect Remover tool.
                            """),
                        )
                        Config.Importers.WWMI.Importer.disable_wounded_fx_warned = True
                        user_requested_injured_fx_disable = Events.Call(user_dialogue)
                        if user_requested_injured_fx_disable:
                            Config.Importers.WWMI.Importer.disable_wounded_fx = True

                if Config.Importers.WWMI.Importer.disable_wounded_fx:
                    settings_manager.set_setting('SkinDamageMode', '0')
                else:
                    settings_manager.set_setting('SkinDamageMode', '1')


        except Exception as e:

            if Config.Importers.WWMI.Importer.unlock_fps:
                raise Exception(L('error_wwmi_fps_unlock_failed', """
                    Failed to force 120 FPS!
                    Please disable `Force 120 FPS` in launcher's General Settings.
                    
                    {error_text}
                """).format(error_text=e)) from e

            if Config.Importers.WWMI.Importer.configure_game:
                raise Exception(L('error_wwmi_game_config_failed', """
                    Failed to configure in-game settings for WWMI!
                    Please disable `Configure Game Settings` in launcher's General Settings and check in-game settings:
                    * Graphics > `Graphics Quality` must be `Quality`.
                    
                    {error_text}
                """).format(error_text=e)) from e

    def update_engine_ini(self, game_path: Path):
        engine_ini_path = game_path / 'Client' / 'Saved' / 'Config' / 'WindowsNoEditor' / 'Engine.ini'
        if not engine_ini_path.exists() and (game_path / 'Wuthering Waves Game').exists():
            engine_ini_path = game_path / 'Wuthering Waves Game' / 'Client' / 'Saved' / 'Config' / 'WindowsNoEditor' / 'Engine.ini'

        Events.Fire(Events.Application.StatusUpdate(
            status=L('status_updating_file', 'Updating {file_name}...').format(file_name=engine_ini_path.name))
        )

        try:
            make_file_writable(engine_ini_path)
            LosslessIniEditor.remove_option(engine_ini_path, 'ConsoleVariables', 'r.Kuro.SkeletalMesh.DistanceLODBaseFOV')
        except PermissionError as e:
            log.warning(f"PermissionError updating Engine.ini: {e}")
        except Exception as e:
            log.warning(f"Error updating Engine.ini: {e}")

    def update_user_engine_ini(self, game_path: Path):
        engine_ini_path = game_path / 'Client' / 'Config' / 'UserEngine.ini'
        if not engine_ini_path.exists() and (game_path / 'Wuthering Waves Game').exists():
            engine_ini_path = game_path / 'Wuthering Waves Game' / 'Client' / 'Config' / 'UserEngine.ini'

        Events.Fire(Events.Application.StatusUpdate(
            status=L('status_updating_file', 'Updating {file_name}...').format(file_name=engine_ini_path.name))
        )

        try:
            make_file_writable(engine_ini_path)
            LosslessIniEditor.set_option(
                engine_ini_path,
                'ConsoleVariables',
                'r.Kuro.SkeletalMesh.DistanceLODBaseFOV',
                str(Config.Importers.WWMI.Importer.mesh_lod_distance_lod_base_fov)
            )
        except PermissionError as e:
            log.warning(f"PermissionError updating UserEngine.ini: {e}")
        except Exception as e:
            log.warning(f"Error updating UserEngine.ini: {e}")

    def update_game_user_settings_ini(self, game_path: Path):
        Events.Fire(Events.Application.StatusUpdate(status=L('status_updating_file', 'Updating {file_name}...').format(file_name='GameUserSettings.ini')))

        ini_path = game_path / 'Client' / 'Saved' / 'Config' / 'WindowsNoEditor' / 'GameUserSettings.ini'
        if not ini_path.exists() and (game_path / 'Wuthering Waves Game').exists():
            ini_path = game_path / 'Wuthering Waves Game' / 'Client' / 'Saved' / 'Config' / 'WindowsNoEditor' / 'GameUserSettings.ini'

        try:
            make_file_writable(ini_path)
            LosslessIniEditor.set_option(
                ini_path,
                '/Script/Engine.GameUserSettings',
                'FrameRateLimit',
                '120.000000'
            )
        except PermissionError as e:
            log.warning(f"PermissionError updating GameUserSettings.ini: {e}")
        except Exception as e:
            log.warning(f"Error updating GameUserSettings.ini: {e}")


class SettingsManager:
    def __init__(self, game_path: Path):
        self.path = game_path / 'Client' / 'Saved' / 'LocalStorage'
        self.db: LocalStorage | None = None

    def __enter__(self):
        Paths.verify_path(self.path)

        default_db_path = self.path / 'LocalStorage.db'

        # Locate the most recently modified db file
        active_db_path, db_paths = self.get_active_db_path()

        # Remove all LocalStorage files except the most recently modified one
        for db_path in db_paths:
            if db_path != active_db_path:
                self.remove_db(db_path)

        # Rename active LocalStorage files to default
        if active_db_path is not None and active_db_path != default_db_path:
            self.rename_db(active_db_path, default_db_path)

        # Open active LocalStorage file for edits
        self.db = LocalStorage(default_db_path)
        self.db.connect()

        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.db.save()

    def get_setting(self, key: str) -> str | None:
        return self.db.get_value(key)

    def set_setting(self, key: str, value: int | float | str, lock: bool = False):
        value = str(value)
        self.db.set_value(key, value)
        if lock:
            self.db.set_value_lock_trigger(f'{key}Lock', key, value)

    def set_fps_setting(self, value: int):
        triggers = self.db.get_all_triggers()

        lock_exist = False
        for trigger in triggers:
            # Our trigger already exists, we'll verify its behaviour later
            if trigger.name == 'CustomFrameRateLock':
                lock_exist = True
                continue
            # Delete 3-rd party triggers for CustomFrameRate
            if 'CustomFrameRate' in trigger.body:
                self.db.delete_trigger(trigger.name)

        # Ensure that our trigger is keeping correct FPS value
        if lock_exist:
            fps = self.db.get_value('CustomFrameRate')
            if fps != str(value):
                # FPS value doesn't match our expectations, lets remove potentially corrupted or old trigger
                self.db.delete_trigger('CustomFrameRateLock')
            else:
                return

        # Mix in the magic data (kudos to WakuWakuPadoru for dumping it), else some clients just refuse to go 120 FPS
        self.db.set_value('MenuData', json.dumps({
            '___MetaType___': '___Map___',
            'Content': [
                [1, 100], [2, 100], [3, 100], [4, 100], [5, 0], [6, 0],
                [7, -0.4658685302734375], [10, 3], [11, 3], [20, 0], [21, 0],
                [22, 0], [23, 0], [24, 0], [25, 0], [26, 0], [27, 0], [28, 0],
                [29, 0], [30, 0], [31, 0], [32, 0], [33, 0], [34, 0], [35, 0],
                [36, 0], [37, 0], [38, 0], [39, 0], [40, 0], [41, 0], [42, 0],
                [43, 0], [44, 0], [45, 0], [46, 0], [47, 0], [48, 0], [49, 0],
                [50, 0], [51, 1], [52, 1], [53, 0], [54, 3], [55, 1], [56, 2],
                [57, 1], [58, 1], [59, 1], [61, 0], [62, 0], [63, 1], [64, 1],
                [65, 0], [66, 0], [67, 3], [68, 2], [69, 100], [70, 100], [79, 1],
                [81, 0], [82, 1], [83, 1], [84, 0], [85, 0], [87, 0], [88, 0],
                [89, 50], [90, 50], [91, 50], [92, 50], [93, 1], [99, 0], [100, 30],
                [101, 0], [102, 1], [103, 0], [104, 50], [105, 0], [106, 0.3],
                [107, 0], [112, 0], [113, 0], [114, 0], [115, 0], [116, 0],
                [117, 0], [118, 0], [119, 0], [120, 0], [121, 1], [122, 1],
                [123, 0], [130, 0], [131, 0], [132, 1], [135, 1], [133, 0]
            ]
        }))
        self.db.set_value('PlayMenuInfo', json.dumps({
            '1': 100, '2': 100, '3': 100, '4': 100, '5': 0, '6': 0,
            '7': -0.4658685302734375, '10': 3, '11': 3, '20': 0, '21': 0,
            '22': 0, '23': 0, '24': 0, '25': 0, '26': 0, '27': 0, '28': 0,
            '29': 0, '30': 0, '31': 0, '32': 0, '33': 0, '34': 0, '35': 0,
            '36': 0, '37': 0, '38': 0, '39': 0, '40': 0, '41': 0, '42': 0,
            '43': 0, '44': 0, '45': 0, '46': 0, '47': 0, '48': 0, '49': 0,
            '50': 0, '51': 1, '52': 1, '53': 0, '54': 3, '55': 1, '56': 2,
            '57': 1, '58': 1, '59': 1, '61': 0, '62': 0, '63': 1, '64': 1,
            '65': 0, '66': 0, '67': 3, '68': 2, '69': 100, '70': 100, '79': 1,
            '81': 0, '82': 1, '83': 1, '84': 0, '85': 0, '87': 0, '88': 0,
            '89': 50, '90': 50, '91': 50, '92': 50, '93': 1, '99': 0, '100': 30,
            '101': 0, '102': 1, '103': 0, '104': 50, '105': 0, '106': 0.3,
            '107': 0, '112': 0, '113': 0, '114': 0, '115': 0, '116': 0,
            '117': 0, '118': 0, '119': 0, '120': 0, '121': 1, '122': 1,
            '123': 0, '130': 0, '131': 0, '132': 1
        }))

        # Set FPS setting and lock it from further changes via trigger
        self.set_setting('CustomFrameRate', str(value), True)

    def reset_fps_setting(self):
        triggers = self.db.get_all_triggers()
        # Delete all triggers for CustomFrameRate
        for trigger in triggers:
            if 'CustomFrameRate' in trigger.body:
                self.db.delete_trigger(trigger.name)

    def get_active_db_path(self):
        active_db_path = None
        db_paths = []
        for db_path in self.path.iterdir():
            # Skip anything that doesn't match `LocalStorage*.db` file mask
            if not db_path.is_file() or not db_path.name.startswith('LocalStorage') or db_path.suffix != '.db':
                continue
            # Make sure we can write db file
            Events.Fire(Events.PathManager.VerifyFileAccess(path=db_path, write=True))
            # Make sure we can write journal file if it exists
            journal_path = db_path.with_suffix('.db-journal')
            if journal_path.is_file():
                Events.Fire(Events.PathManager.VerifyFileAccess(path=journal_path, write=True))
            # Search for the most recently modified file
            if active_db_path is None or db_path.stat().st_mtime > active_db_path.stat().st_mtime:
                active_db_path = db_path
            # Add db to the list
            db_paths.append(db_path)
        return active_db_path, db_paths

    def rename_db(self, old_path: Path, new_path: Path):
        log.debug(f'Renaming {old_path} to {new_path}...')
        # Rename DB journal
        journal_path = old_path.with_suffix('.db-journal')
        if journal_path.is_file():
            journal_path.rename(new_path.with_suffix('.db-journal'))
        # Rename DB file
        old_path.rename(new_path)

    def remove_db(self, db_path: Path):
        log.debug(f'Removing {db_path}...')
        # Remove DB journal
        journal_path = db_path.with_suffix('.db-journal')
        if journal_path.is_file():
            journal_path.unlink()
        # Remove DB file
        db_path.unlink()


@dataclass
class SQLiteTrigger:
    name: str
    table: str
    body: str


class LocalStorage:
    def __init__(self, path: Path):
        self.path = path
        self.connection = None
        self.cursor = None
        self.modified = False

    def disconnect(self):
        if self.connection is None:
            return
        self.connection.close()
        self.cursor = None
        self.modified = False
        self.connection = None
        log.debug(f'[{self.path.name}]: Connection closed')

    def connect(self):
        self.disconnect()
        log.debug(f'[{self.path.name}]: Connecting...')
        self.connection = sqlite3.connect(self.path)
        try:
            self.cursor = self.connection.cursor()
            try:
                self.cursor.execute("SELECT * FROM LocalStorage")
            except sqlite3.OperationalError:
                log.debug(f'[{self.path.name}]: Creating new settings database...')
                self.cursor.execute("CREATE TABLE LocalStorage(key text primary key not null, value text not null)")
                data = [
                    ('NotFirstTimeOpenPush', '"___1B___"'),
                    ('HasLocalGameSettings', '"___1B___"'),
                    ('IsCustomImageQuality', '"___1B___"'),
                ]
                self.cursor.executemany(f"INSERT INTO LocalStorage VALUES (?,?)", data)
        except Exception as e:
            self.disconnect()
            raise Exception(L('error_local_storage_init_failed', 'Failed to initialize LocalStorage: {error_text}').format(error_text=e))

    def save(self):
        if not self.modified:
            self.disconnect()
            return
        self.connection.commit()
        self.disconnect()
        log.debug(f'[{self.path.name}]: File updated')

    def get_value(self, key) -> str | None:
        result = self.cursor.execute(f"SELECT value FROM LocalStorage WHERE key='{key}'")
        data = result.fetchone()
        if data is None or len(data) != 1:
            return None
        else:
            return data[0]

    def set_value(self, key: str, value: str):
        old_value = self.get_value(key)
        if value == old_value:
            log.debug(f'[{self.path.name}]: Skipped {key} value: {value} (already set)')
            return
        if old_value is None:
            self.cursor.execute(f"INSERT INTO LocalStorage VALUES ('{key}', '{value}')")
            log.debug(f'[{self.path.name}]: Added {key} value: {value}')
        else:
            self.cursor.execute(f"UPDATE LocalStorage SET value = '{value}' WHERE key='{key}'")
            log.debug(f'[{self.path.name}]: Updated {key} value: {old_value} -> {value}')
        self.modified = True

    def delete_value(self, key):
        if self.get_value(key) is None:
            return
        self.cursor.execute(f"DELETE FROM LocalStorage WHERE key='{key}'")
        log.debug(f'[{self.path.name}]: Removed {key} value')
        self.modified = True

    def get_trigger(self, name) -> SQLiteTrigger | None:
        result = self.cursor.execute(f"SELECT * FROM sqlite_master WHERE type='trigger' AND name='{name}'")
        data = result.fetchone()
        if data is None:
            return None
        else:
            return SQLiteTrigger(name=data[1], table=data[2], body=data[4])

    def get_all_triggers(self) -> list[SQLiteTrigger] | None:
        result = self.cursor.execute(f"SELECT * FROM sqlite_master WHERE type='trigger'")
        data = result.fetchmany()
        if data is None:
            return None
        else:
            return [SQLiteTrigger(name=t[1], table=t[2], body=t[4]) for t in data]

    def set_value_lock_trigger(self, name, key, value):
        self.delete_trigger(name)
        self.cursor.execute(f'''
            CREATE TRIGGER {name}
            AFTER UPDATE OF value ON LocalStorage
            WHEN NEW.key = '{key}'
            BEGIN
                UPDATE LocalStorage
                SET value = {value}
                WHERE key = '{key}';
            END;
        ''')
        log.debug(f'[{self.path.name}]: Added lock trigger {name} for {key} value: {value}')
        self.modified = True

    def delete_trigger(self, name):
        if self.get_trigger(name) is None:
            return
        self.cursor.execute(f'DROP TRIGGER IF EXISTS {name}')
        log.debug(f'[{self.path.name}]: Removed trigger {name}')
        self.modified = True

