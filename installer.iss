; XMMI-Pro Inno Setup Script
; Modern Fluent Chinese Installer Wizard

#define MyAppName "XMMI-Pro"
#ifndef MyAppVersion
#define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "XMMI-Pro Team"
#define MyAppURL "https://github.com/nameZhj/XMMI-Pro"
#define MyAppExeName "XXMI Launcher.exe"

[Setup]
; Basic Application Info
AppId={{D37E84B1-29C3-48FA-97B2-DF8B62F0F3AA}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation Target Directory
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableReadyPage=yes
DisableDirPage=no

; Output Configuration
OutputDir=.
OutputBaseFilename=XMMI-Pro-Setup-v{#MyAppVersion}
SetupIconFile=Themes\Default\window-icon.ico
UninstallDisplayIcon={app}\Resources\Bin\{#MyAppExeName}

; High-DPI & Visual Styling
WizardStyle=modern
WizardSizePercent=115,115
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; UI Configuration
ShowLanguageDialog=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Default.isl"

[Messages]
chinesesimplified.WelcomeLabel1=欢迎安装 %1
chinesesimplified.WelcomeLabel2=XMMI-Pro 是专为二次元与开放世界游戏（鸣潮、原神、绝区零等）打造的模组管理与启动平台。%n%n✨ 已深度集成 Wuwa_Mod_Fixer 智能修复引擎，支持全量 Hash 自动适配、骨骼重映射与远景 LOD 贴图补全。%n%n请点击【下一步】继续。
chinesesimplified.WizardSelectDir=选择安装路径
chinesesimplified.SelectDirDesc=请选择 XMMI-Pro 的安装文件夹。
chinesesimplified.SelectDirLabel3=安装程序将把 %1 安装到以下文件夹：
chinesesimplified.SelectDirBrowseLabel=若要选择不同的文件夹，请点击【浏览】。
chinesesimplified.DiskSpaceMBLabel=所需磁盘空间：约 [mb] MB
chinesesimplified.WizardSelectTasks=附加任务
chinesesimplified.SelectTasksDesc=选择您希望安装程序执行的快捷方式任务。
chinesesimplified.SelectTasksLabel2=选择要在安装 XMMI-Pro 时创建的快捷方式：
chinesesimplified.WizardInstalling=正在安装
chinesesimplified.InstallingLabel=正在将 XMMI-Pro 部署至您的计算机，请稍候...
chinesesimplified.FinishedHeadingLabel=XMMI-Pro 安装完成！
chinesesimplified.FinishedLabel=XMMI-Pro 已成功安装到您的计算机上。点击【完成】退出安装程序。
chinesesimplified.ClickFinish=点击【完成】退出安装向导。
chinesesimplified.ButtonNext=下一步(&N) >
chinesesimplified.ButtonBack=< 上一步(&B)
chinesesimplified.ButtonInstall=⚡ 立即安装(&I)
chinesesimplified.ButtonCancel=取消
chinesesimplified.ButtonFinish=🚀 立即体验(&F)
chinesesimplified.ButtonBrowse=浏览(&B)...

[CustomMessages]
chinesesimplified.CreateDesktopIcon=创建桌面快捷方式
chinesesimplified.LaunchApp=立即启动 XMMI-Pro

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "快捷方式："; Flags: unchecked

[Files]
Source: "XMMI-Pro-Release\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\Resources\Bin\{#MyAppExeName}"; IconFilename: "{app}\Themes\Default\window-icon.ico"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Resources\Bin\{#MyAppExeName}"; IconFilename: "{app}\Themes\Default\window-icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\Resources\Bin\{#MyAppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent
