> **本说明由AI生成**
> 
> *This documentation is AI-generated.*

# XMMI-Pro

<p align="center">
  <strong>模组管理与启动器增强版 · Visual Mod Manager & Launcher</strong>
</p>

<p align="center">
  <a href="#简体中文">简体中文</a> •
  <a href="#-鸣潮模组深度修复引擎-wuwa-mod-fixer-使用指南">修复引擎使用指南</a> •
  <a href="#english">English</a> •
  <a href="#免责声明--disclaimers">免责声明 / Disclaimers</a> •
  <a href="#开源许可--license">开源许可 / License</a> •
  <a href="#开源引用--credits">致谢与引用 / Credits</a>
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
- 🔧 **深度模组修复与版本适配引擎 (基于 [Wuwa_Mod_Fixer](https://github.com/Moonholder/Wuwa_Mod_Fixer) v3.7.1)**：
  - 覆盖 **120+ 角色与全量武器规则数据库**（全面支持景燃 Jingran、莫宁 Mornye、千咲 Chisa、爱弥斯 Aemeath、青宵 Qingxiao、心/辛 Hsin 等最新角色/武器适配）。
  - 支持 **Rendering 3.3 管线修复**：自动识别并清理 `*TexCoord*.buf` 缓冲中的旧版 COLOR1 顶点掩码属性，彻底解决 3.3 管线更新后的模型黑屏与顶点遮罩崩溃。
  - **可视化多维度修复选项**：提供 11 项精细化独立修复开关（Hash 更新、骨骼与顶点组重映射、衍生贴图/LOD 防黑补全、Shapekey 与规则修复、状态贴图稳定、Rendering 3.3 管线修复、主角专属材质、Engine.ini 渲染注入等），支持单模组独立修复与全库批量一键深度修复。
  - **无损安全快照与一键回滚**：修复前自动创建 `.backup` 安全快照，随时一键撤销并还原至初始状态。
- ⚡ **软件热更新与规则同步中心 (Hot Update & Sync)**：
  - **规则库一键动态更新**：内置多源国内与国际 CDN 镜像（fastly、jsdelivr、ghproxy 等），无需重启启动器即可毫秒级热拉取上游最新角色与武器修复规则。
  - **WWMI-Package 智能导入与同步**：支持直连上游 [SpectrumQT/WWMI-Package](https://github.com/SpectrumQT/WWMI-Package) 自动下载解包导入，同时支持从本地 `.zip` 压缩包或解压目录一键导入并热装载。
  - **上游代码与补丁同步**：已全量整合 [SpectrumQT/XXMI-Launcher](https://github.com/SpectrumQT/XXMI-Launcher) 上游最新至 v2.4.9 的核心特性（含动画性能优化、Steam/GRYPHLINK 启动器识别与异常修复、多语言更新等）。
- 📂 **角色二级分类与多维深度检索**：
  - 智能解析 Mod 角色归属，生成左侧分类导航树及动态数量角标。
  - 支持 **拼音全拼/首字母、中文角色名、英文名、GUID、文件夹名** 毫秒级多维模糊搜索。
- 🎮 **实时快捷键面板与游戏状态同步**：
  - 右侧详情面板自动解析并结构化呈现 Mod 包含的所有快捷键与控制指令。
  - 模组启用/禁用/修复时，自动向运行中的游戏进程发送重载信号（F10），实现游戏内状态秒级热更新。
- 🔄 **完善的格式导入支持**：
  - 支持 `.zip`、`.7z`、`.rar` 压缩包批量解压导入以及本地文件夹一键导入。

### 🛠️ 鸣潮模组深度修复引擎 (Wuwa Mod Fixer) 使用指南

XMMI-Pro 深度集成了基于 [Moonholder/Wuwa_Mod_Fixer](https://github.com/Moonholder/Wuwa_Mod_Fixer) v3.7.1 演进的原生 Python 修复引擎。无论是单项快速处理还是全库批量适配，均可在启动器内无缝完成。

#### 1. 适用场景与常见问题
- 🎮 **游戏版本大更新后失效**：更新后模型不显示、骨骼错位拉伸、贴图破皮或显示红白方块。
- 👁️ **远景变黑 / 材质丢失**：模型在拉远视角时身体变黑或透明（缺失 LOD / Wet / Charged 衍生贴图）。
- 🖥️ **Rendering 3.3 管线黑屏问题**：游戏升级 Rendering 3.3 管线后，模型在游戏中导致画面变黑或崩溃（由旧版 COLOR1 顶点掩码字节引起）。
- 💃 **特定角色状态异常**：爱弥斯 (Aemeath)、椿 (Camellya)、千咲 (Chisa) 等角色的特殊状态贴图异常，或白芷、长离骨骼权重不匹配。

#### 2. 修复模式与操作步骤

- **模式 A：单模组定向修复（推荐调试单个 Mod 时使用）**
  1. 在模组卡片上右键点击，在快捷菜单中选择 **“🔧 深度修复”**（或选中模组后在右侧详情面板底部点击 **“🔧 深度修复”**）。
  2. 在弹出的修复设置窗口中检查修复选项（默认已配置最佳预设）。
  3. 点击 **“🚀 开始修复”**，右侧实时日志将显示逐步修复详情与统计结果。
  4. 修复完成后，Mod 将自动保存并同步至游戏（若游戏正在运行，将自动触发 F10 实时重载）。

- **模式 B：全库批量一键修复（推荐游戏大版本更新后使用）**
  1. 在模组管理页面顶部操作栏，点击 **“⚡ 批量修复”** 按钮。
  2. 确认修复配置后点击启动，系统将依次扫描并自动修复当前已启用的全部模组，并在日志窗口中输出汇总报告。

- **模式 C：无损还原与安全回滚**
  - 在单模组修复设置窗口中，若当前模组曾经进行过修复且存在安全备份，底部 **“⏪ 还原初始 (回滚备份)”** 按钮将点亮可用。
  - 点击即可将该模组一键恢复至初始状态，完全避免误修改或损坏原始资产。

#### 3. 核心修复选项深度解析

| 修复选项 | 说明与技术原理 | 推荐配置 |
| :--- | :--- | :---: |
| **游戏版本更新 Hash 替换** | 自动匹配并更新 120+ 角色与武器在版本迭代后的主 Hash 与贴图 Hash，恢复正常渲染定位 | ✅ 默认开启 |
| **骨骼与顶点组重映射 (`vg_remap`)** | 重新计算并映射顶点组索引与骨骼权重，解决白芷、长离等因骨骼更新引发的破皮与拉扯 | ✅ 默认开启 |
| **衍生贴图与 LOD 远景防黑补全** | 智能补全缺少的分级贴图重载 (`LOD`, `Wet`, `Charged`, `Injured`)，解决视角拉远后变黑 | ✅ 默认开启 |
| **索引规则与 Shapekey 修复** | 修正 `match_first_index`、`match_index_count`，校准面部表情与顶点偏移数据 | ✅ 默认开启 |
| **追加资源重载检查** | 追加 `CheckTextureOverride` 拦截校验，防止多材质或同类型贴图重载相互冲突 | ✅ 默认开启 |
| **状态贴图稳定模式** | 针对爱弥斯 (Aemeath)、椿 (Camellya)、千咲 (Chisa) 等角色状态贴图进行防脱落稳定处理 | ✅ 默认开启 |
| **Rendering 3.3 管线修复** | 自动扫描 `*TexCoord*.buf`，清除旧版残余的 COLOR1 顶点掩码字节，彻底解决 3.3 管线黑屏问题 | ✅ 默认开启 |
| **主角材质与风主眼部专属修复** | 为漂泊者生成专属 Materialmap 材质映射，并单独修复风主满充能状态下的眼部贴图 | ⚪ 按需开启 |
| **Engine.ini 渲染与防破图注入** | 向游戏 `Engine.ini` 写入 `LODDistanceScale` 高精渲染与纹理流式加载优化，改善微卡顿 | ⚪ 按需开启 |
| **清理冗余与临时干扰文件** | 深度清除 `References.ini`, `CheckTexture.ini`, `.DS_Store`, `Thumbs.db` 等冗余或冲突文件 | ✅ 默认开启 |
| **规范化 INI 编码与路径反斜杠** | 统一转换为 UTF-8 编码并修复 Windows 路径分隔符，避免解析器乱码或丢失路径 | ✅ 默认开启 |
| **创建安全回滚备份** | 在执行任何文件修改前，自动打包生成 `.backup` 备份快照，确保随时可无损还原 | ✅ 强烈推荐 |

#### 4. 在线规则库与 WWMI 热更新
- 启动器内置了最新的 **v3.7.1 完整离线规则库**（覆盖 120+ 角色与武器配置，含景燃、莫宁等最新修复）。
- 启动器还内置了智能多节点在线更新机制，优先通过国内高速 CDN 镜像（Fastly / jsDelivr / Cloudflare / ghproxy）静默检测并同步远程修复规则，保证第一时间适配游戏未来更新。
- 点击操作栏 **“⚡ 热更新与同步”** 即可一键拉取最新规则、在线同步或本地导入 **WWMI-Package**。

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

# 5. 本地一键编译与打包（自动生成中文 Setup EXE 安装包与便携绿色压缩包）
python build_release.py
```

---

## English

### 📖 About XMMI-Pro
**XMMI-Pro** is an enhanced, visual mod management tool and launcher based on the open-source project [SpectrumQT/XXMI-Launcher](https://github.com/SpectrumQT/XXMI-Launcher). It brings a next-generation UI, automated health checks, deep repair engines (powered by Wuwa_Mod_Fixer v3.7.0), and real-time game synchronization.

### 🌟 Key Features

- 📦 **Visual Mod Grid with Aspect-Fit Previews**:
  - Displays mod thumbnails with exact aspect containment (no distortion or cropping).
  - Responsive column auto-layout (2 to 5 columns) based on viewport width.
- 🔧 **Deep Mod Repair Engine & Options (Powered by [Wuwa_Mod_Fixer](https://github.com/Moonholder/Wuwa_Mod_Fixer) v3.7.1)**:
  - Supports **120+ characters and weapons** with automated version hash replacement, vertex group remapping (`vg_remap`), derivative/LOD texture completion, and rule/index adjustments.
  - **Rendering 3.3 Pipeline Fix**: Automatically cleans legacy COLOR1 vertex mask attributes in `*TexCoord*.buf` buffers, preventing black screens and shader crashes.
  - **Interactive Repair Options**: 11 modular toggles for hash fix, bone remap, LOD textures, stable state textures, special character fixes, and Engine.ini optimizations.
  - **Backup & Instant Rollback**: Automatic `.backup` snapshots before repairs with 1-click restore.
- ⚡ **Integrated Hot Update & WWMI-Package Sync**:
  - Live rule sync via multi-region high-speed CDNs.
  - Direct upstream import & local zip/directory deployment for [SpectrumQT/WWMI-Package](https://github.com/SpectrumQT/WWMI-Package).
  - Synced upstream [SpectrumQT/XXMI-Launcher](https://github.com/SpectrumQT/XXMI-Launcher) v2.4.9 codebase enhancements.
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
- 🌟 **Windows Setup Installer (Recommended)**: Download `XMMI-Pro-Setup-vX.X.X.exe` for a modern Chinese setup wizard with automatic desktop/start menu shortcuts.
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

# Package release locally (generates EXE installer and portable ZIP)
python build_release.py
```

---

## 开源引用 / Credits

XMMI-Pro is built upon and inspired by the remarkable contributions of the open-source modding community:

- **Upstream Launcher Project**: [SpectrumQT/XXMI-Launcher](https://github.com/SpectrumQT/XXMI-Launcher) by [SpectrumQT](https://github.com/SpectrumQT)
- **Mod Repair & Compatibility Engine**:
  - **[Wuwa_Mod_Fixer](https://github.com/Moonholder/Wuwa_Mod_Fixer)** by [Moonholder](https://github.com/Moonholder): 本项目内置的鸣潮 Mod 深度修复与版本更新适配算法（Hash 更新规则、顶点组权重修复 `vg_remap`、衍生贴图/LOD 防黑补全、Shapekey 与索引重构、Rendering 3.3 管线修复等）参考并整合了社区开源项目 [Moonholder/Wuwa_Mod_Fixer](https://github.com/Moonholder/Wuwa_Mod_Fixer) (v3.7.1) 的算法架构与规则逻辑。特此向其开发者表示衷心感谢与致敬！
  - *The deep mod repair algorithms, hash database, vertex group remapping, texture LOD fixes, Rendering 3.3 pipeline fixes, and rule parsing mechanisms integrated in this project are based upon and derived from the open-source community project [Moonholder/Wuwa_Mod_Fixer](https://github.com/Moonholder/Wuwa_Mod_Fixer).*
- **Model Importers & Community Developers**:
  - **WWMI / WWMI-Package / EFMI**: [SpectrumQT](https://github.com/SpectrumQT)
  - **ZZMI**: [LeoTorrez](https://github.com/leotorrez), [Scyll](https://gamebanana.com/members/2644630), [SilentNightSound](https://github.com/SilentNightSound), [SinsOfSeven](https://github.com/SinsOfSeven), [Gustav0](https://github.com/Seris0), [Satan1c](https://gamebanana.com/members/2789093)
  - **SRMI / GIMI / HIMI**: [SilentNightSound](https://github.com/SilentNightSound), [LeoTorrez](https://github.com/leotorrez), [SinsOfSeven](https://github.com/SinsOfSeven), [Gustav0](https://github.com/Seris0), [Nurarihyon](https://github.com/NurarihyonMaou)

---

## 开源许可 / License

本项目基于 **[GNU General Public License v3.0 (GPLv3)](LICENSE)** 开源。根据 GPLv3 协议条款，任何基于此项目的衍生作品均须保持相同开源协议。


