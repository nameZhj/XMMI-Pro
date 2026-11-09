import sys
import os
import tempfile
import shutil
from pathlib import Path

# Setup paths
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src" / "xxmi_launcher"))

import core.path_manager as Paths
import core.locale_manager as Locale
Paths.initialize(repo_root)
Locale.initialize(repo_root)

import core.config_manager as Config
Config.Manager._update_globals()
from core.packages.model_importers.wwmi_package import WWMIPackage
from core.packages.model_importers.launch_safety_guard import LaunchSafetyGuard
from core.utils.process_manager import LaunchContext, ExecutableLaunch

def test_full_launch_integration():
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        game_path = root / "Wuthering Waves Game"
        wwmi_root = root / "WWMI"

        # Game folders & files
        engine_ini_dir = game_path / "Client" / "Saved" / "Config" / "WindowsNoEditor"
        engine_ini_dir.mkdir(parents=True, exist_ok=True)
        engine_ini = engine_ini_dir / "Engine.ini"
        original_engine_text = "[SystemSettings]\nexisting_val = 1\n"
        engine_ini.write_text(original_engine_text, encoding="utf-8")

        shipping_dir = game_path / "Client" / "Binaries" / "Win64"
        shipping_dir.mkdir(parents=True, exist_ok=True)
        shipping_exe = shipping_dir / "Client-Win64-Shipping.exe"
        shipping_exe.write_text("PE_BINARY", encoding="utf-8")
        wrapper_exe = game_path / "Wuthering Waves.exe"
        wrapper_exe.write_text("WRAPPER", encoding="utf-8")

        # Incompatible proxy DLL (ACE risk)
        risky_dxgi = shipping_dir / "dxgi.dll"
        risky_dxgi.write_text("OLD_PROXY_DLL", encoding="utf-8")

        # WWMI folders & files
        wwmi_root.mkdir(parents=True, exist_ok=True)
        d3dx_ini = wwmi_root / "d3dx.ini"
        original_d3dx_text = "[Loader]\ntarget = Client-Win64-Shipping.exe\ndelay = 100\n"
        d3dx_ini.write_text(original_d3dx_text, encoding="utf-8")

        # Stale shader cache
        shader_cache_dir = wwmi_root / "ShaderCache"
        shader_cache_dir.mkdir(parents=True, exist_ok=True)
        stale_bin = shader_cache_dir / "stale_shader.bin"
        stale_bin.write_text("BYTECODE", encoding="utf-8")

        mods_dir = wwmi_root / "Mods"
        mods_dir.mkdir(parents=True, exist_ok=True)

        # Toxic file
        toxic_file = mods_dir / "CheckTexture.ini"
        toxic_file.write_text("[CheckTexture]\nval = 1\n", encoding="utf-8")

        # Mod 1
        mod1_dir = mods_dir / "YinlinMod"
        mod1_dir.mkdir(parents=True, exist_ok=True)
        mod1_ini = mod1_dir / "Yinlin.ini"
        mod1_ini.write_text(
            "[TextureOverrideYinlin]\nhash = aabb1122\nif $costume_mods == 1\n[ResourceYinlin]\nfilename = Textures/body.dds\n",
            encoding="utf-8"
        )

        # Mod 2 (Hash conflict)
        mod2_dir = mods_dir / "YinlinModConflict"
        mod2_dir.mkdir(parents=True, exist_ok=True)
        mod2_ini = mod2_dir / "YinlinConflict.ini"
        mod2_ini.write_text(
            "[TextureOverrideYinlin2]\nhash = aabb1122\n",
            encoding="utf-8"
        )

        # Configure importer path
        Config.Importers.WWMI.Importer.importer_folder = str(wwmi_root)
        Config.Importers.WWMI.Importer.game_folder = str(game_path)
        Config.Importers.WWMI.Importer.resource_tier_warned = True
        Config.Active = Config.Importers.WWMI

        # Create package and launch context targeting wrapper_exe initially
        pkg = WWMIPackage()
        target = ExecutableLaunch(
            exe_path=wrapper_exe,
            cmd_args="-SkipSplash",
        )
        ctx = LaunchContext(
            start_method=Config.Active.Importer.start_method,
            process_name="Wuthering Waves.exe",
            target=target,
        )

        # Run override_launch_context
        pkg.override_launch_context(ctx, game_path, wrapper_exe)

        # 1. 进程拉起对齐：必须固定为 Client-Win64-Shipping.exe
        print(f"Target exe path: {ctx.target.exe_path}")
        assert ctx.target.exe_path == shipping_exe
        assert ctx.process_name == "Client-Win64-Shipping.exe"
        print("Target aligned to Client-Win64-Shipping.exe successfully.")

        # 2. 参数安全过滤与合并去重
        print(f"Launch args: {ctx.target.cmd_args}")
        assert "-SkipSplash" in ctx.target.cmd_args
        assert "-dx11" in ctx.target.cmd_args
        assert "-d3d11" in ctx.target.cmd_args
        assert ctx.target.cmd_args.split().count("-dx11") == 1

        # 3. 反作弊代理 DLL 隔离
        assert not risky_dxgi.exists()
        assert (shipping_dir / "DISABLED_dxgi.dll.bak").exists()
        print("Risky proxy DLL isolated to prevent ACE error.")

        # 4. 版本更新检测与 ShaderCache 清理
        assert not stale_bin.exists()
        print("ShaderCache purged on version update.")

        # 5. Engine.ini / d3dx.ini 优化写入与基线备份
        engine_content = engine_ini.read_text(encoding="utf-8")
        assert "r.Streaming.PoolSize" in engine_content
        assert (engine_ini.with_suffix(".ini.orig.bak")).exists()
        d3dx_content = d3dx_ini.read_text(encoding="utf-8")
        assert (d3dx_ini.with_suffix(".ini.orig.bak")).exists()
        print("Baseline .orig.bak backups verified.")

        # 6. Mod 语法修复与 Hash 冲突隔离
        assert not toxic_file.exists()
        assert (mods_dir / "DISABLED_CheckTexture.ini.bak").exists()
        assert "; [AutoFixed] if $costume_mods == 1" in mod1_ini.read_text(encoding="utf-8")
        assert not mod2_dir.exists()
        assert (mods_dir / "DISABLED_YinlinModConflict").exists()
        print("Mod syntax and hash conflicts repaired.")

        # 7. 防崩溃自动回滚闭环验证
        restored = LaunchSafetyGuard.rollback_all_configs(game_path, wwmi_root)
        print(f"Restored files on rollback: {restored}")
        assert engine_ini.read_text(encoding="utf-8") == original_engine_text
        assert d3dx_ini.read_text(encoding="utf-8") == original_d3dx_text
        print("Automatic rollback successfully restored pure baseline configs.")

    print("\nALL INTEGRATION AND CRASH GUARD TESTS PASSED!")

if __name__ == "__main__":
    test_full_launch_integration()
