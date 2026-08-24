#!/usr/bin/env python3
"""
XMMI-Pro Build Script
Compiles and packages XMMI-Pro into:
1. Portable Windows ZIP Archive (XMMI-Pro-{tag}-Windows-x64.zip)
2. Modern Chinese Setup Installer (XMMI-Pro-Setup-{tag}.exe) via Inno Setup
3. Windows Installer MSI (XMMI-Pro-Setup-{tag}.msi) via WiX Toolset v5
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


def find_or_install_wix():
    """Locates or automatically installs WiX Toolset v5 CLI."""
    wix_cmd = shutil.which("wix")
    if wix_cmd:
        return wix_cmd

    # Check dotnet global tools directory
    user_home = Path.home()
    dotnet_tool_wix = user_home / ".dotnet" / "tools" / "wix.exe"
    if dotnet_tool_wix.exists():
        return str(dotnet_tool_wix)

    # Attempt to install wix v5 via dotnet
    if shutil.which("dotnet"):
        print("Installing WiX Toolset v5 via dotnet tool...")
        try:
            subprocess.run(["dotnet", "tool", "install", "--global", "wix", "--version", "5.0.2"], check=True)
            subprocess.run(["wix", "extension", "add", "WixToolset.UI.wixext/5.0.2"], check=False)
            subprocess.run(["wix", "extension", "add", "WixToolset.Util.wixext/5.0.2"], check=False)
            if dotnet_tool_wix.exists():
                return str(dotnet_tool_wix)
            return "wix"
        except Exception as e:
            print(f"Warning: Failed to install WiX via dotnet tool: {e}")

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

    # 2. Run PyInstaller with embedded Version Info
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
        "--hidden-import", "rarfile",
        "--hidden-import", "core.mod_service",
        "--hidden-import", "gui.windows.main.mod_manager_frame.mod_manager_frame",
        "--add-data", f"{SRC_DIR / 'core' / 'wuwa_fix_config.json'}{os.pathsep}core",
    ]
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

    # 6. Compile Windows Installer MSI (XMMI-Pro-Setup-v1.0.0.msi)
    installer_msi = ROOT_DIR / f"XMMI-Pro-Setup-{tag}.msi"
    wix_bin = find_or_install_wix()
    clean_version = tag.lstrip("vV")
    ver_parts = clean_version.split(".")
    while len(ver_parts) < 3:
        ver_parts.append("0")
    clean_version = ".".join(ver_parts[:3])

    if wix_bin and (ROOT_DIR / "installer.wxs").exists():
        print(f"Compiling Windows Installer MSI via WiX Toolset ({wix_bin})...")
        wix_cmd = [
            wix_bin, "build",
            "-arch", "x64",
            "-culture", "zh-CN",
            "-d", f"Version={clean_version}",
            "-ext", "WixToolset.UI.wixext",
            "-ext", "WixToolset.Util.wixext",
            str(ROOT_DIR / "installer.wxs"),
            "-o", str(installer_msi)
        ]
        res = subprocess.run(wix_cmd, cwd=ROOT_DIR)
        if res.returncode == 0 and installer_msi.exists():
            print(f"[SUCCESS] Windows Installer MSI generated: {installer_msi}")
        else:
            print(f"[WARNING] WiX Toolset build finished with code: {res.returncode}")

    # Export environment variables for GitHub Actions CI
    if "GITHUB_ENV" in os.environ:
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
            f.write(f"ZIP_NAME={zip_path.name}\n")
            f.write(f"RELEASE_TAG={tag}\n")
            if installer_exe.exists():
                f.write(f"SETUP_EXE={installer_exe.name}\n")
            if installer_msi.exists():
                f.write(f"SETUP_MSI={installer_msi.name}\n")

    print("=" * 60)
    print(f"[SUCCESS] Build process completed successfully for {tag}!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build XMMI-Pro Distribution")
    parser.add_argument("--tag", default=os.environ.get("GITHUB_REF_NAME", "v1.0.0"), help="Release version tag")
    args = parser.parse_args()
    build(args.tag)
