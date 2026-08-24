# XMMI-Pro

<p align="center">
  <strong>模组管理与启动器增强版 · Visual Mod Manager & Launcher</strong>
</p>

<p align="center">
  <a href="#简体中文">简体中文</a> •
  <a href="#english">English</a> •
  <a href="#免责声明--disclaimers">免责声明 / Disclaimers</a> •
  <a href="#开源许可--license">开源许可 / License</a> •
  <a href="#鸣谢--upstream-acknowledgments">鸣谢 / Acknowledgments</a>
</p>

---

## 免责声明 / Disclaimers

> [!IMPORTANT]
> **法律与合规声明 (Legal Notice & Disclaimers)**
> 
> 1. **非官方社区工具 (Unofficial Community Tool)**：
>    本项目为开源、非官方的第三方社区辅助工具，与任何游戏开发商/发行商没有任何关联、背书或商业合作。
> 2. **知识产权声明 (Intellectual Property)**：
>    游戏中涉及的所有游戏名称、商标、版权资产、角色形象与多媒体素材均归其各自版权所有者所有。本项目仅提供文件组织、本地模组管理及便捷启动功能。
> 3. **非商业用途 (Strictly Non-Commercial)**：
>    本项目完全免费、开源，严禁用于任何商业盈利、非法侵权或违反游戏最终用户许可协议（EULA）的行为。用户需自行承担使用第三方模组的风险与责任。
> 4. **无担保声明 (No Warranty)**：
>    本项目基于 GNU GPLv3 许可证提供，作者与贡献者不对因使用本软件造成的任何数据丢失、封号风险或其他直接/间接损失承担责任。

---

## 简体中文

### 📖 项目简介
**XMMI-Pro** 是基于开源项目 [SpectrumQT/XXMI-Launcher](https://github.com/SpectrumQT/XXMI-Launcher) 进行深度定制与功能增强的高性能可视化模组管理与游戏启动工具。旨在为玩家提供更加直观、智能、安全的一体化 Mod 管理体验。

### 🌟 核心特性

- 📦 **沉浸式可视化模组卡片**：
  - 支持高清 Contain 等比完整展示模组预览图，不拉伸、不裁剪。
  - 动态响应式卡片网格布局，根据窗口尺寸自适应 2~5 列排版。
- 🔧 **深度模组修复与版本适配引擎 (基于 Wuwa_Mod_Fixer)**：
  - 覆盖 115+ 角色与武器数据库，一键自动修复游戏版本更新 Hash、骨骼与顶点组重映射 (`vg_remap`)、衍生贴图与 LOD 远景防黑材质补全、绘制索引与 Shapekey 规则。
  - **可视化多维度修复选项**：提供 8 大独立修复开关（Hash、顶点组、衍生贴图、规则、主角/风主专属、状态贴图、Engine.ini 等），支持单个修复与全库批量一键修复。
  - **一键回滚备份**：修复前自动创建安全快照，随时一键撤销并还原至初始文件。
- 📂 **角色二级分类与多维深度检索**：
  - 智能解析 Mod 角色归属，生成左侧分类导航树及动态数量角标。
  - 支持 **拼音全拼/首字母、中文角色名、英文名、GUID、文件夹名** 毫秒级多维模糊搜索。
- 🎮 **实时快捷键面板与游戏状态同步**：
  - 右侧详情面板自动解析并结构化呈现 Mod 包含的所有快捷键与控制指令。
  - 模组启用/禁用/修复时，自动向运行中的游戏进程发送重载信号（F10），实现游戏内状态秒级热更新。
- 🔄 **完善的格式导入支持**：
  - 支持 `.zip`、`.7z`、`.rar` 压缩包批量解压导入以及本地文件夹一键导入。

### 🚀 快速开始

#### 方法一：下载 Release 发行版（推荐）
进入本仓库 [Releases 页面](https://github.com/nameZhj/XMMI-Pro/releases) 下载适合的版本：
- 🌟 **现代极速中文安装包（推荐）**：下载 `XMMI-Pro-Setup-vX.X.X.exe`，现代 Fluent 暗黑安装向导，一键极速安装并自动创建桌面快捷方式。
- 🛠️ **Windows Installer MSI 安装包**：下载 `XMMI-Pro-Setup-vX.X.X.msi`，标准 Windows Installer 安装包。
- 💼 **免安装绿色便携版**：下载 `XMMI-Pro-vX.X.X-Windows-x64.zip`，解压后双击运行 `XMMI-Pro.bat` 即可直接使用。

#### 方法二：源码运行与本地开发
```bash
# 1. 克隆代码仓库
git clone https://github.com/nameZhj/XMMI-Pro.git
cd XMMI-Pro

# 2. 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行启动器
python src/xxmi_launcher/app.py

# 5. 本地一键编译与打包（自动生成 MSI 安装包与便携绿色压缩包）
python build_release.py
```

---

## English

### 📖 About XMMI-Pro
**XMMI-Pro** is an enhanced, visual mod management tool and launcher based on the open-source project [SpectrumQT/XXMI-Launcher](https://github.com/SpectrumQT/XXMI-Launcher). It brings a next-generation UI, automated health checks, deep repair engines (powered by Wuwa_Mod_Fixer), and real-time game synchronization.

### 🌟 Key Features

- 📦 **Visual Mod Grid with Aspect-Fit Previews**:
  - Displays mod thumbnails with exact aspect containment (no distortion or cropping).
  - Responsive column auto-layout (2 to 5 columns) based on viewport width.
- 🔧 **Deep Mod Repair Engine & Options (Powered by Wuwa_Mod_Fixer)**:
  - Supports 115+ characters and weapons with automated version hash replacement, vertex group remapping (`vg_remap`), derivative/LOD texture completion, and rule/index adjustments.
  - **Interactive Repair Options**: Modular toggles for hash fix, bone remap, LOD textures, special character fixes, and Engine.ini optimizations.
  - **Backup & Instant Rollback**: Automatic snapshots before repairs with 1-click restore.
- 📂 **Character Navigation & Multi-Dimensional Search**:
  - Automatic character category mapping with live item counter badges.
  - Ultra-fast search across Chinese names, English names, Pinyin, GUIDs, and file names.
- 🎮 **Hotkey Inspector & Live Game Synchronization**:
  - Automatically parses hotkeys and controls in mod `.ini` files.
  - Broadcasts live F10 reload signals to running games for instant in-game updates.
- 🔄 **Universal Format Support**:
  - Supports `.zip`, `.7z`, `.rar` archive extraction and folder-based mod imports.

### 🚀 Getting Started

#### Option 1: Download Release (Recommended)
Download the preferred distribution from [Releases](https://github.com/nameZhj/XMMI-Pro/releases):
- 🌟 **Windows Installer MSI (Recommended)**: Download `XMMI-Pro-Setup-vX.X.X.msi` for a native Windows Installer setup with automatic desktop/start menu shortcuts.
- 📦 **Portable Package**: Download `XMMI-Pro-vX.X.X-Windows-x64.zip`, extract and run `XMMI-Pro.bat`.

#### Option 2: Run from Source
```bash
# Clone the repository
git clone https://github.com/nameZhj/XMMI-Pro.git
cd XMMI-Pro

# Setup environment
python -m venv .venv
.\.venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Run
python src/xxmi_launcher/app.py

# Package release locally (generates MSI and portable ZIP)
python build_release.py
```

---

## 鸣谢 / Upstream Acknowledgments

XMMI-Pro is built upon and inspired by the remarkable contributions of the open-source modding community:

- **Upstream Project**: [SpectrumQT/XXMI-Launcher](https://github.com/SpectrumQT/XXMI-Launcher) by [SpectrumQT](https://github.com/SpectrumQT)
- **Model Importers & Community Developers**:
  - **WWMI / EFMI**: [SpectrumQT](https://github.com/SpectrumQT)
  - **ZZMI**: [LeoTorrez](https://github.com/leotorrez), [Scyll](https://gamebanana.com/members/2644630), [SilentNightSound](https://github.com/SilentNightSound), [SinsOfSeven](https://github.com/SinsOfSeven), [Gustav0](https://github.com/Seris0), [Satan1c](https://gamebanana.com/members/2789093)
  - **SRMI / GIMI / HIMI**: [SilentNightSound](https://github.com/SilentNightSound), [LeoTorrez](https://github.com/leotorrez), [SinsOfSeven](https://github.com/SinsOfSeven), [Gustav0](https://github.com/Seris0), [Nurarihyon](https://github.com/NurarihyonMaou)

---

## 开源许可 / License

本项目基于 **[GNU General Public License v3.0 (GPLv3)](LICENSE)** 开源。根据 GPLv3 协议条款，任何基于此项目的衍生作品均须保持相同开源协议。
