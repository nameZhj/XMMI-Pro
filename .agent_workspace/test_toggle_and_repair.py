import sys
import shutil
from pathlib import Path

sys.path.insert(0, 'src/xxmi_launcher')
from core.mod_service import ModService, ModItem, ModRepairOptions

def test_toggle_self_healing():
    test_dir = Path(".agent_workspace/test_mods")
    shutil.rmtree(test_dir, ignore_errors=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    # 1. Simulate a mod that was renamed on disk to DISABLED_MyMod
    # but the ModItem in memory still points to MyMod
    mod_on_disk = test_dir / "DISABLED_TestMod"
    mod_on_disk.mkdir()
    (mod_on_disk / "mod.ini").write_text("[TextureOverride]\nhash = 12345678\n", encoding="utf-8")

    stale_item = ModItem(
        name="TestMod",
        display_name="TestMod",
        path=test_dir / "TestMod",
        enabled=True
    )

    # Test toggling with stale path - should self-heal, find DISABLED_TestMod, and enable it!
    success, new_item, msg, _ = ModService.toggle_mod(stale_item, enable=True)
    assert success, f"Toggle failed: {msg}"
    assert (test_dir / "TestMod").exists(), "TestMod folder should exist"
    assert not (test_dir / "DISABLED_TestMod").exists(), "DISABLED_TestMod should no longer exist"
    assert new_item.enabled is True, "Item should be enabled"

    # Test toggling to disabled
    success, new_item, msg, _ = ModService.toggle_mod(new_item, enable=False)
    assert success, f"Toggle disable failed: {msg}"
    assert (test_dir / "DISABLED TestMod").exists() or (test_dir / "DISABLED_TestMod").exists()
    assert new_item.enabled is False

    # Test toggling when already disabled (no-op)
    success, new_item, msg, _ = ModService.toggle_mod(new_item, enable=False)
    assert success, f"No-op failed: {msg}"
    assert new_item.enabled is False

    print("✅ test_toggle_self_healing passed successfully!")

def test_repair_and_restore():
    test_dir = Path(".agent_workspace/test_mods_repair")
    shutil.rmtree(test_dir, ignore_errors=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    mod_dir = test_dir / "TestCharMod"
    mod_dir.mkdir()
    ini_file = mod_dir / "char.ini"
    ini_file.write_text("[TextureOverride]\nhash = 12345678\nfilename = textures/body.dds\n", encoding="utf-8")
    
    # Create a 5MB dummy texture file
    tex_file = mod_dir / "body.dds"
    tex_file.write_bytes(b"\x00" * (5 * 1024 * 1024))

    mod_item = ModItem(
        name="TestCharMod",
        display_name="TestCharMod",
        path=mod_dir,
        enabled=True
    )

    opts = ModRepairOptions(normalize_ini=True, create_backup=True)
    success, fixes = ModService.repair_mod(mod_item, options=opts)
    assert success, f"Repair failed: {fixes}"

    # Verify .orig.bak was created and texture file is intact
    assert ini_file.with_name("char.ini.orig.bak").exists(), ".orig.bak should exist"
    assert tex_file.exists() and len(tex_file.read_bytes()) == 5 * 1024 * 1024, "Texture file should not be modified or deleted"

    # Test restore
    res_ok, res_msg = ModService.restore_mod(mod_item)
    assert res_ok, f"Restore failed: {res_msg}"
    assert tex_file.exists(), "Texture file should still exist after restore"

    # Clean up
    shutil.rmtree(test_dir, ignore_errors=True)
    print("✅ test_repair_and_restore passed successfully!")

if __name__ == "__main__":
    test_toggle_self_healing()
    test_repair_and_restore()
