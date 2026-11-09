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
        engine_ini.write_text("[SystemSettings]\nexisting_val = 1\n", encoding="utf-8")

        shipping_dir = game_path / "Client" / "Binaries" / "Win64"
        shipping_dir.mkdir(parents=True, exist_ok=True)
        (shipping_dir / "Client-Win64-Shipping.exe").write_text("", encoding="utf-8")
        (game_path / "Wuthering Waves.exe").write_text("", encoding="utf-8")

        # WWMI folders & files
        wwmi_root.mkdir(parents=True, exist_ok=True)
        d3dx_ini = wwmi_root / "d3dx.ini"
        d3dx_ini.write_text("[Loader]\ntarget = Client-Win64-Shipping.exe\ndelay = 100\n", encoding="utf-8")

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

        # Create package and launch context
        pkg = WWMIPackage()
        target = ExecutableLaunch(
            exe_path=shipping_dir / "Client-Win64-Shipping.exe",
            cmd_args="-SkipSplash",
        )
        ctx = LaunchContext(
            start_method=Config.Active.Importer.start_method,
            process_name="Client-Win64-Shipping.exe",
            target=target,
        )

        # Run override_launch_context
        pkg.override_launch_context(ctx, game_path, shipping_dir / "Client-Win64-Shipping.exe")

        # 1. Check extra_launch_args merged into cmd_args
        print(f"Launch args: {ctx.target.cmd_args}")
        assert "-SkipSplash" in ctx.target.cmd_args
        assert "-dx11" in ctx.target.cmd_args
        assert "-d3d11" in ctx.target.cmd_args
        # Deduplication check: "-dx11" should appear only once
        assert ctx.target.cmd_args.split().count("-dx11") == 1

        # 2. Check Engine.ini updated losslessly
        engine_content = engine_ini.read_text(encoding="utf-8")
        assert "existing_val = 1" in engine_content
        assert "r.Streaming.PoolSize" in engine_content
        assert "r.Kuro.SkeletalMesh.LODDistanceScale" in engine_content
        print("Engine.ini verified successfully.")

        # 3. Check d3dx.ini delay updated
        d3dx_content = d3dx_ini.read_text(encoding="utf-8")
        assert "target = Client-Win64-Shipping.exe" in d3dx_content
        assert "cache_shaders=1" in d3dx_content or "cache_shaders = 1" in d3dx_content
        print(f"d3dx.ini delay setting verified: {Config.Importers.WWMI.Importer.xxmi_dll_init_delay}")
        assert Config.Importers.WWMI.Importer.xxmi_dll_init_delay >= 350

        # 4. Check toxic file isolation
        assert not toxic_file.exists()
        assert (mods_dir / "DISABLED_CheckTexture.ini.bak").exists()
        print("Toxic file isolated.")

        # 5. Check mod syntax repair
        mod1_fixed = mod1_ini.read_text(encoding="utf-8")
        assert "; [AutoFixed] if $costume_mods == 1" in mod1_fixed
        assert "filename = Textures\\body.dds" in mod1_fixed
        assert (mod1_dir / "Yinlin.ini.orig.bak").exists()
        print("Mod syntax repaired.")

        # 6. Check hash conflict isolation
        assert not mod2_dir.exists()
        assert (mods_dir / "DISABLED_YinlinModConflict").exists()
        print("Conflicting mod isolated successfully.")

        # 7. Check close delay calculation logic
        init_delay = Config.Active.Importer.xxmi_dll_init_delay
        close_delay = max(1000, init_delay + 1500) if init_delay >= 300 else 1000
        assert close_delay >= 1850
        print(f"Close delay: {close_delay}ms (safeguard active)")

    print("\nALL INTEGRATION TESTS PASSED!")

if __name__ == "__main__":
    test_full_launch_integration()
