#!/usr/bin/env python3
"""
XMMI-Pro Build Script
Compiles and packages XMMI-Pro into a portable distribution.
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


def build(tag: str = "v1.0.0"):
    print("=" * 60)
    print(f"Building XMMI-Pro ({tag})...")
    print("=" * 60)

    # 1. Clean previous build artifacts
    for d in [DIST_DIR, BUILD_DIR, RELEASE_DIR]:
        if d.exists():
            print(f"Cleaning {d.name}...")
            shutil.rmtree(d, ignore_errors=True)

    # 2. Run PyInstaller
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
        str(SRC_DIR / "app.py")
    ]
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

    # Launcher batch script
    launcher_bat = RELEASE_DIR / "XMMI-Pro.bat"
    launcher_bat.write_text('@echo off\nstart "" "%~dp0Resources\\Bin\\XXMI Launcher.exe"\n', encoding="utf-8")

    # 4. Zip output
    zip_base_name = f"XMMI-Pro-{tag}-Windows-x64"
    zip_path = ROOT_DIR / f"{zip_base_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    print(f"Compressing into {zip_path.name}...")
    shutil.make_archive(str(ROOT_DIR / zip_base_name), 'zip', RELEASE_DIR)

    # Export variables for GitHub Actions if running in CI
    if "GITHUB_ENV" in os.environ:
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
            f.write(f"ZIP_NAME={zip_path.name}\n")
            f.write(f"RELEASE_TAG={tag}\n")

    print("=" * 60)
    print(f"[SUCCESS] Build completed successfully! Package: {zip_path}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build XMMI-Pro Distribution")
    parser.add_argument("--tag", default=os.environ.get("GITHUB_REF_NAME", "v1.0.0"), help="Release version tag")
    args = parser.parse_args()

    tag_value = args.tag if args.tag else "v1.0.0"
    if tag_value.startswith("refs/tags/"):
        tag_value = tag_value.replace("refs/tags/", "")
    build(tag=tag_value)
