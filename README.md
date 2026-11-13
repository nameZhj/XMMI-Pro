# XMMI-Pro

<p align="center">
  <strong>可视化本地资产配置管理与桌面应用启动器 · Visual Asset Workspace & Desktop Launcher</strong>
</p>

<p align="center">
  <a href="#简体中文">简体中文</a> •
  <a href="#-自动化配置校验与修复引擎使用指南">配置修复指南</a> •
  <a href="#english">English</a> •
  <a href="#免责声明--disclaimers">免责声明 / Disclaimers</a> •
  <a href="#开源许可--license">开源许可 / License</a>
</p>

---

## 免责声明 / Disclaimers

> [!IMPORTANT]
> **使用与合规声明 (Legal Notice & Disclaimers)**
>
> 1. **独立开源工具 (Independent Open-Source Utility)**：
>    本项目为开源、独立的第三方本地文件组织与桌面工作区管理工具，不隶属于任何商业软件实体。
> 2. **知识产权声明 (Intellectual Property)**：
>    用户通过本工具管理的本地素材、配置文件及第三方外部资源，其版权与合法使用权均归各自所有者及授权方所有。本项目仅提供本地目录编排、格式校验及桌面进程启动辅助能力。
> 3. **非商业用途 (Strictly Non-Commercial)**：
>    本项目完全免费、开源，请遵守所在地区法律法规及目标软件的相关许可规范。用户需自行承担使用本地配置与第三方资源所带来的数据风险与责任。
> 4. **无担保声明 (No Warranty)**：
>    本项目基于 GNU GPLv3 许可证按“现状”提供，作者与贡献者不对因使用本软件造成的任何数据丢失或其他直接/间接损失承担责任。

---

## 简体中文

### 📖 项目简介
**XMMI-Pro** 是一款基于 Python 与现代暗黑界面设计的高性能可视化资产管理与桌面进程启动工具，集成多维度资源索引、无损配置修复、热更新规则同步及内置双语网页浏览器，旨在为用户提供直观、高效、可控的一体化本地工作区管理体验。

### 🌟 核心特性

- 📦 **沉浸式可视化卡片视图**：
  - 支持高清 Contain 等比完整展示本地目录缩略图，不拉伸、不裁剪。
  - 动态响应式卡片网格布局，根据窗口尺寸自适应 2~5 列排版。
- 🔧 **无损配置解析与深度修复引擎**：
  - 覆盖 **120+ 预置分类条目与多级规则数据库**，支持本地配置文件引用键、资源哈希及映射索引的批量校验与更新。
  - **缓冲属性与管线兼容修复**：自动扫描 `*TexCoord*.buf` 二进制缓冲文件并清理旧版冗余顶点属性字节，解决渲染管线升级导致的黑屏与解析异常。
  - **可视化多维度独立开关**：支持单目录定向修复与全库批量一键处理（哈希迁移、索引重映射、分层衍生资源补全、规则结构修正、冗余临时文件清理、UTF-8 编码与路径分隔符规范化）。
  - **无损快照与一键回滚**：修改前自动创建 `.backup` 安全快照，随时支持一键撤销并恢复初始状态。
- ⚡ **热更新同步与动态词库中心 (Hot Update & Sync)**：
  - **规则与中英文对照表动态同步**：内置多节点高速 CDN 与公开接口拉取，支持实时同步最新规则字典及实体中英文对照表，并按特征词选择性本地化条目名称（无匹配特征词的通用技术条目保持原名）。
  - **运行包智能导入**：支持在线同步或从本地 `.zip` 压缩包 / 解压目录一键导入并热装载核心运行时文件。
- 🌐 **内置多站点网页浏览与双语翻译插件**：
  - **嵌入式 WebView2 浏览器**：支持站点切换、登录态 Cookie 本地持久化保存、自动拦截下载压缩包并无缝导入本地工作区。
  - **网页双语实时翻译插件**：参考开源双语翻译架构，提供「双语对照 / 仅译文 / 还原原文」实时切换，内置 Microsoft、Google 及自定义 OpenAI 兼容大模型翻译引擎，外文页面自动启用。
- 📂 **树状二级分类与多维深度检索**：
  - 自动解析目录归属与哈希特征，生成左侧分类导航树与实时统计角标。
  - 支持 **拼音全拼/首字母、中文译名、英文原名、GUID、目录名** 毫秒级模糊检索。
- ⌨️ **实时快捷键解析与热重载同步**：
  - 右侧详情面板自动提取并结构化展示配置文件中的快捷键与交互参数。
  - 启用/禁用或修复资产目录时，自动向关联进程发送重载信号（F10）实现即时生效。
- 🔄 **多格式压缩包导入**：
  - 支持 `.zip`、`.7z`、`.rar` 压缩包（含加密压缩包密码弹窗交互）以及本地文件夹拖拽/选择一键导入。

### 🛠️ 自动化配置校验与修复引擎使用指南

#### 1. 适用场景与常见问题
- 🔄 **版本迭代后配置失效**：底层接口或索引变动导致资源加载不全、索引错位或解析报错。
- 👁️ **多级缓存缺失**：远端或特定状态下资源显示异常（缺少分层衍生资源重载配置）。
- 🖥️ **管线缓冲兼容性异常**：二进制 `*TexCoord*.buf` 残留旧版属性字节导致渲染画面异常或程序崩溃。

#### 2. 操作模式
- **模式 A：单目录定向修复**
  1. 右键目标资产卡片或选中后在右侧详情栏点击 **“🔧 深度修复”**。
  2. 在配置窗口按需勾选修复开关后点击 **“🚀 开始修复”**，实时查看处理日志。
- **模式 B：全库批量一键修复**
  1. 在顶部操作栏点击 **“⚡ 批量修复”**，自动扫描当前已启用的全部目录并生成汇总报告。
- **模式 C：安全快照回滚**
  - 若目录存在修复前备份，点击 **“⏪ 还原初始 (回滚备份)”** 即可一键无损恢复至修改前文件状态。

### 🚀 快速开始

#### 方法一：下载 Release 发行版（推荐）
进入本仓库 [Releases 页面](https://github.com/nameZhj/XMMI-Pro/releases) 下载对应版本：
- 🌟 **Windows 安装包（推荐）**：下载 `XMMI-Pro-Setup-vX.X.X.exe`，一键安装并生成快捷方式。
- 💼 **免安装绿色便携版**：下载 `XMMI-Pro-vX.X.X-Windows-x64.zip`，解压后双击运行即可。

#### 方法二：源码运行与本地打包
```bash
# 1. 克隆代码仓库
git clone https://github.com/nameZhj/XMMI-Pro.git
cd XMMI-Pro

# 2. 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行桌面端
python src/xxmi_launcher/app.py

# 5. 本地编译与打包（生成 Setup 安装包与便携 ZIP 包）
python build_release.py
```

---

## English

### 📖 About XMMI-Pro
**XMMI-Pro** is a Python-based visual local asset workspace manager and desktop runtime launcher featuring responsive grid previews, lossless INI/binary validation engines, dynamic dictionary synchronization, and an embedded WebView2 browser with bilingual webpage translation.

### 🌟 Key Features

- 📦 **Visual Asset Grid with Aspect-Fit Previews**:
  - Renders preview thumbnails cleanly without distortion or cropping across an adaptive 2–5 column layout.
- 🔧 **Lossless Configuration & Binary Repair Engine**:
  - Validates and migrates configuration hashes, index mappings, derivative overrides, binary `*TexCoord*.buf` buffer attributes, UTF-8 encoding, and Windows path separators.
  - Supports single-item repair, full-workspace batch repair, automatic `.backup` snapshots, and 1-click rollback.
- ⚡ **Hot Update & Dynamic Dictionary Sync**:
  - Multi-CDN rule updates, selective terminology translation (leaving unmatched technical folders intact), and `.zip`/directory runtime package imports.
- 🌐 **Embedded Browser & Bilingual Webpage Translator**:
  - Built on WebView2 with persistent login session cookies, automatic archive download interception/import, and a bilingual / translation-only DOM translator supporting Microsoft, Google, and OpenAI-compatible AI backends.
- 📂 **Multi-Dimensional Indexing & Search**:
  - Instant search across Chinese names, English names, Pinyin initials, GUIDs, and directory names, plus structured hotkey inspection and live `F10` reload signaling.
- 🔄 **Multi-Format Archive Support**:
  - Extracts and imports `.zip`, `.7z`, and `.rar` archives (with interactive password prompts when needed) or local folders via drag-and-drop.

### 🚀 Getting Started

#### Option 1: Download Release (Recommended)
Download from [Releases](https://github.com/nameZhj/XMMI-Pro/releases):
- 🌟 **Windows Setup Installer**: `XMMI-Pro-Setup-vX.X.X.exe`
- 📦 **Portable Archive**: `XMMI-Pro-vX.X.X-Windows-x64.zip`

#### Option 2: Run from Source
```bash
git clone https://github.com/nameZhj/XMMI-Pro.git
cd XMMI-Pro

python -m venv .venv
.\.venv\Scripts\activate

pip install -r requirements.txt
python src/xxmi_launcher/app.py

# Build installer and portable ZIP locally
python build_release.py
```

---

## 开源许可 / License

本项目基于 **[GNU General Public License v3.0 (GPLv3)](LICENSE)** 开源。根据 GPLv3 协议条款，任何基于此项目的衍生作品均须保持相同开源协议。
