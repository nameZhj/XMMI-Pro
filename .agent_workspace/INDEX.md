# Codebase Index

src/xxmi_launcher/core/hot_update_service.py | Orchestrates hot updates for Wuwa fixer rules, WWMI-Package, and launcher components | HotUpdateService, HotUpdateStatus
src/xxmi_launcher/core/wwmi_importer.py | Imports, validates, and deploys WWMI-Package into the active WWMI directory | WWMIImporter, WWMIImportResult
src/xxmi_launcher/gui/windows/hot_update_dialog.py | Modern dark-themed dialog for hot updates, WWMI-Package imports, and rule synchronization | HotUpdateDialog
src/xxmi_launcher/core/mod_service.py | Native Python engine for Wuwa_Mod_Fixer and mod management | ModService, ModItem, ModFixOptions, ModHealthIssue
src/xxmi_launcher/core/wuwa_fix_config.json | Wuwa_Mod_Fixer character rules, hash databases, and pipeline configs (v3.7.1) | JSON Config
src/xxmi_launcher/core/packages/launcher_package.py | Package management and version metadata for XMMI-Pro Launcher | LauncherPackage, LauncherManagerConfig
src/xxmi_launcher/gui/classes/element.py | Base class for UI elements with lifecycle and event management | UIElement, UIElementBase
src/xxmi_launcher/gui/windows/main/message_frame/message_frame.py | Modal message, error, and confirmation dialogue frame for XMMI-Pro | MessageFrame
src/xxmi_launcher/core/utils/process_manager.py | Process execution, monitoring, and elevation management for XMMI-Pro | ProcessManager, LaunchContext, ExecutableLaunch, CommandLaunch
src/xxmi_launcher/core/application.py | Main application runtime and lifecycle coordinator for XMMI-Pro | Application
src/xxmi_launcher/gui/windows/gamebanana_browser.py | Integrated GameBanana mod browser with automatic download interception, 1-click downloads, and mod import | GameBananaBrowserManager, run_gamebanana_browser
src/xxmi_launcher/core/gamebanana_service.py | GameBanana mod parser, direct download engine, and automatic installer | GameBananaService, GameBananaModInfo, GameBananaFileInfo
src/xxmi_launcher/gui/windows/gamebanana_download_dialog.py | Modern dark-themed dialog for GameBanana URL parsing, file selection, and direct installation | GameBananaDownloadDialog
