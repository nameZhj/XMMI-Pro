# Codebase Index

src/xxmi_launcher/core/hot_update_service.py | Orchestrates hot updates for Wuwa fixer rules, WWMI-Package, and launcher components | HotUpdateService, HotUpdateStatus
src/xxmi_launcher/core/wwmi_importer.py | Imports, validates, and deploys WWMI-Package into the active WWMI directory | WWMIImporter, WWMIImportResult
src/xxmi_launcher/gui/windows/hot_update_dialog.py | Modern dark-themed dialog for hot updates, WWMI-Package imports, and rule synchronization | HotUpdateDialog
src/xxmi_launcher/core/wuwa_char_translator.py | Dynamic Encore.moe EN-CN character/weapon mapping sync and selective mod name translator | WuwaCharTranslator
src/xxmi_launcher/core/gamebanana_service.py | GameBanana mod parser, direct download engine, and automatic installer | GameBananaService, GameBananaModInfo, GameBananaFileInfo
src/xxmi_launcher/core/mod_service.py | Native Python engine for Wuwa_Mod_Fixer and mod management | ModService, ModItem, ModFixOptions, ModHealthIssue
src/xxmi_launcher/core/wuwa_fix_config.json | Wuwa_Mod_Fixer character rules, hash databases, and pipeline configs (v3.8.0) | JSON Config
src/xxmi_launcher/core/packages/launcher_package.py | Package management and version metadata for XMMI-Pro Launcher | LauncherPackage, LauncherManagerConfig
src/xxmi_launcher/gui/classes/element.py | Base class for UI elements with lifecycle and event management | UIElement, UIElementBase
src/xxmi_launcher/gui/windows/main/message_frame/message_frame.py | Modal message, error, and confirmation dialogue frame for XMMI-Pro | MessageFrame
src/xxmi_launcher/core/utils/process_manager.py | Process execution, monitoring, and elevation management for XMMI-Pro | ProcessManager, LaunchContext, ExecutableLaunch, CommandLaunch
src/xxmi_launcher/core/application.py | Main application runtime and lifecycle coordinator for XMMI-Pro | Application
src/xxmi_launcher/core/mod_sites.py | Wuthering Waves mod websites catalog, login routing, and download JS builders | ModSiteSpec, MOD_SITE_CATALOG, get_site_by_id, detect_site_from_url, build_login_check_js, build_site_download_js
src/xxmi_launcher/core/readfrog_translator.py | Read Frog inspired batch translator supporting Microsoft, Google, and AI engines | ReadFrogConfig, ReadFrogTranslator
src/xxmi_launcher/core/readfrog_inject.js | Read Frog DOM bilingual and translation-only content script for WebView2 | window.__ReadFrog
src/xxmi_launcher/gui/windows/mod_browser_bridge.py | WinForms toolbar builder, Read Frog JS bridge, and site-aware mod download dispatcher | build_browser_chrome, ModBrowserBridge, load_readfrog_js
src/xxmi_launcher/gui/windows/mod_browser_dialogs.py | WinForms helper dialogs for multi-site login assistant and Read Frog translation config | show_account_helper_dialog, show_readfrog_settings_dialog
src/xxmi_launcher/gui/windows/mod_browser_downloads.py | WebView2 DownloadStarting interceptor, progress reporter, and standalone importer | ModBrowserDownloadHandler, sanitize_filename
src/xxmi_launcher/gui/windows/mod_site_launcher_dialog.py | Dark modal selector dialog for Wuthering Waves mod websites with login-first and Read Frog badges | ModSiteLauncherDialog
src/xxmi_launcher/gui/windows/gamebanana_browser.py | Multi-site Wuthering Waves mod browser manager and WebView2 subprocess entry point | GameBananaBrowserManager, run_gamebanana_browser
src/xxmi_launcher/gui/windows/gamebanana_download_dialog.py | Modern dark-themed dialog for mod URL parsing, file selection, and direct installation | GameBananaDownloadDialog
src/xxmi_launcher/gui/copyable_error_dialog.py | Dark-themed copyable error dialog with re-exported modal dialog helpers | CopyableErrorDialog, show_copyable_error, show_warning, show_info, ask_confirm, ModernModalDialog
src/xxmi_launcher/gui/modern_dialogs.py | Modern dark-themed modal dialogs (info, warning, confirm) preserving parent window focus | ModernModalDialog, show_info, show_warning, ask_confirm
src/xxmi_launcher/core/utils/lossless_ini_editor.py | Lossless line-level INI editor preserving comments, case, and duplicate keys with read-only unlock | LosslessIniEditor, make_file_writable
src/xxmi_launcher/core/utils/hardware_profiler.py | Zero-configuration hardware profiler and adaptive engine parameter builder | HardwareSpecs, AdaptiveModConfig, SystemHardwareProfiler
src/xxmi_launcher/core/packages/model_importers/launch_safety_guard.py | Crash guard, proxy DLL conflict isolation, and automatic rollback monitor for Wuthering Waves | LaunchSafetyGuard
src/xxmi_launcher/core/packages/model_importers/wwmi_fixer.py | Wuthering Waves mod diagnostic, repair, and hardware-adaptive optimizer | WWMIRepairAndOptimizer, LaunchSafetyGuard, apply_engine_ini_fixes, apply_d3dx_ini_fixes, apply_windows_compat_fixes, scan_and_repair_mods
src/xxmi_launcher/core/packages/model_importers/wwmi_package.py | Wuthering Waves model importer package with dual-layer path resolution and lossless config writing | WWMIPackage, WWMIConfig, WWMIPackageConfig
src/xxmi_launcher/core/game_launcher.py | Game launch orchestration, pre-launch synchronous INI optimization, and monitoring | GameLauncher
src/xxmi_launcher/core/utils/wuwa_graphics_advisor.py | CPU/GPU inspection and real Wuthering Waves in-game graphics advisor for mod stability | GraphicsSettingRecommendation, HardwareGraphicsReport, WuwaGraphicsAdvisor
src/xxmi_launcher/gui/windows/pre_launch_advisor_dialog.py | Dark modal pre-launch hardware inspection and Wuthering Waves graphics settings dialog | PreLaunchAdvisorDialog, show_pre_launch_advisor
