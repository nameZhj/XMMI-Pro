#!/usr/bin/env python3
"""
XMMI-Pro Build Script
Compiles and packages XMMI-Pro into:
1. Modern Chinese Setup Installer (XMMI-Pro-Setup-{tag}.exe) via Inno Setup
2. Portable Windows ZIP Archive (XMMI-Pro-{tag}-Windows-x64.zip)
"""
import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src" / "xxmi_launcher"
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
RELEASE_DIR = ROOT_DIR / "XMMI-Pro-Release"


def find_iscc():
    """Locates Inno Setup 6 ISCC compiler."""
    candidates = [
        shutil.which("iscc"),
        shutil.which("ISCC"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Inno Setup 6\ISCC.exe",
        r"D:\Inno Setup 6\ISCC.exe",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(c)
    return None


def build(tag: str = "v1.0.0"):
    print("=" * 60)
    print(f"Building XMMI-Pro ({tag})...")
    print("=" * 60)

    # 1. Clean previous build artifacts
    for d in [DIST_DIR, BUILD_DIR, RELEASE_DIR]:
        if d.exists():
            print(f"Cleaning {d.name}...")
            shutil.rmtree(d, ignore_errors=True)

    # 2. Run PyInstaller with embedded Version Info & complete packages
    version_file = ROOT_DIR / "file_version_info.txt"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "XXMI Launcher",
        "--paths", str(SRC_DIR),
        "--collect-all", "customtkinter",
        "--collect-all", "tkinterweb",
        "--collect-all", "PIL",
        "--collect-all", "py7zr",
        "--collect-all", "dacite",
        "--collect-all", "darkdetect",
        "--collect-all", "pyglet",
        "--collect-all", "winshell",
        "--collect-all", "wmi",
        "--collect-all", "requests",
        "--collect-all", "markdown",
        "--collect-all", "mdx_gfm",
        "--collect-all", "cryptography",
        "--collect-all", "win32api",
        "--collect-all", "pywintypes",
        "--collect-all", "win32gui",
        "--collect-all", "tkinterdnd2",
        "--hidden-import", "tkinterdnd2",
        "--hidden-import", "rarfile",
        "--hidden-import", "core.mod_service",
        "--hidden-import", "core.hot_update_service",
        "--hidden-import", "core.wwmi_importer",
        "--hidden-import", "core.drag_drop",
        "--hidden-import", "gui.copyable_error_dialog",
        "--hidden-import", "gui.windows.hot_update_dialog",
        "--hidden-import", "gui.windows.main.mod_manager_frame.mod_manager_frame",
        "--hidden-import", "dacite",
        "--hidden-import", "darkdetect",
        "--hidden-import", "pyglet",
        "--hidden-import", "winshell",
        "--hidden-import", "wmi",
        "--hidden-import", "requests",
        "--hidden-import", "markdown",
        "--hidden-import", "mdx_gfm",
        "--hidden-import", "cryptography",
        "--hidden-import", "win32api",
        "--hidden-import", "pywintypes",
        "--hidden-import", "win32gui",
        "--hidden-import", "win32con",
        "--hidden-import", "win32process",
        "--hidden-import", "pythoncom",
        "--hidden-import", "ctypes",
        "--hidden-import", "ctypes.wintypes",
        "--add-data", f"{SRC_DIR / 'core' / 'wuwa_fix_config.json'}{os.pathsep}core",
    ]
    try:
        import av
        cmd.extend(["--collect-all", "av", "--hidden-import", "av"])
    except ImportError:
        pass
    if version_file.exists():
        cmd.extend(["--version-file", str(version_file)])
    cmd.append(str(SRC_DIR / "app.py"))

    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT_DIR)
    if result.returncode != 0:
        print("[FAILED] PyInstaller build failed with exit code:", result.returncode)
        sys.exit(result.returncode)

    # 3. Assemble Release Directory Structure
    print("Assembling release structure...")
    bin_target = RELEASE_DIR / "Resources" / "Bin"
    bin_target.mkdir(parents=True, exist_ok=True)

    built_bin = DIST_DIR / "XXMI Launcher"
    if built_bin.exists():
        for item in built_bin.iterdir():
            if item.is_dir():
                shutil.copytree(item, bin_target / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, bin_target / item.name)

    # Copy Resources, Locale, Themes, LICENSE, README
    for folder in ["Locale", "Themes"]:
        src_folder = ROOT_DIR / folder
        if src_folder.exists():
            shutil.copytree(src_folder, RELEASE_DIR / folder, dirs_exist_ok=True)

    for file_name in ["LICENSE", "README.md"]:
        f_path = ROOT_DIR / file_name
        if f_path.exists():
            shutil.copy2(f_path, RELEASE_DIR / file_name)

    # Launcher batch script for portable use
    launcher_bat = RELEASE_DIR / "XMMI-Pro.bat"
    launcher_bat.write_text('@echo off\nstart "" "%~dp0Resources\\Bin\\XXMI Launcher.exe"\n', encoding="utf-8")

    # 4. Zip output (Portable distribution)
    zip_base_name = f"XMMI-Pro-{tag}-Windows-x64"
    zip_path = ROOT_DIR / f"{zip_base_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    print(f"Compressing into {zip_path.name}...")
    shutil.make_archive(str(ROOT_DIR / zip_base_name), 'zip', RELEASE_DIR)
    print(f"[SUCCESS] Portable package created: {zip_path}")

    # 5. Compile Modern Inno Setup Installer (XMMI-Pro-Setup-v1.0.0.exe)
    iscc_bin = find_iscc()
    installer_exe = ROOT_DIR / f"XMMI-Pro-Setup-{tag}.exe"
    if iscc_bin and (ROOT_DIR / "installer.iss").exists():
        print(f"Compiling Modern Inno Setup Installer ({iscc_bin})...")
        iscc_cmd = [iscc_bin, f"/DMyAppVersion={tag.lstrip('vV')}", str(ROOT_DIR / "installer.iss")]
        res = subprocess.run(iscc_cmd, cwd=ROOT_DIR)
        if res.returncode == 0 and installer_exe.exists():
            print(f"[SUCCESS] Modern Setup Installer generated: {installer_exe}")
        else:
            print(f"[WARNING] Inno Setup compilation finished with code: {res.returncode}")
    else:
        print("[INFO] Inno Setup compiler (ISCC) not found, skipping setup exe build.")

    # Export environment variables for GitHub Actions CI
    if "GITHUB_ENV" in os.environ:
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
            f.write(f"ZIP_NAME={zip_path.name}\n")
            f.write(f"RELEASE_TAG={tag}\n")
            if installer_exe.exists():
                f.write(f"SETUP_EXE={installer_exe.name}\n")

    print("=" * 60)
    print(f"[SUCCESS] Build process completed successfully for {tag}!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build XMMI-Pro Distribution")
    parser.add_argument("--tag", default=os.environ.get("GITHUB_REF_NAME", "v1.0.0"), help="Release version tag")
    args = parser.parse_args()
    build(args.tag)
