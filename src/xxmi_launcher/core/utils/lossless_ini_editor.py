"""
@file: src/xxmi_launcher/core/utils/lossless_ini_editor.py
@brief: Lossless line-level INI editor preserving comments, case, and duplicate keys with read-only unlock
@exports: LosslessIniEditor, make_file_writable
"""

import os
import re
import stat
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional

log = logging.getLogger(__name__)


def make_file_writable(file_path: Path | str) -> bool:
    """
    确保文件可写：如果文件存在且带有只读属性，使用 os.chmod 赋予 S_IWRITE 权限。
    捕获 PermissionError 防止崩溃。
    """
    try:
        p = Path(file_path)
        if not p.exists():
            return True
        current_mode = os.stat(p).st_mode
        if not (current_mode & stat.S_IWRITE):
            os.chmod(p, current_mode | stat.S_IWRITE)
        return True
    except PermissionError as e:
        log.warning(f"PermissionError unlocking read-only on {file_path}: {e}")
        return False
    except Exception as e:
        log.warning(f"Could not unlock read-only on {file_path}: {e}")
        return False


class LosslessIniEditor:
    """
    专为 UE4 Engine.ini、GameUserSettings.ini 与 3DMigoto d3dx.ini / Mod .ini 设计的无损行级编辑器。
    完全保留原始大小写、注释、缩进以及同名重复键（如多个 run = ... 或 checktextureoverride = ...）。
    """

    @classmethod
    def update_sections(
        cls,
        file_path: Path | str,
        updates: Dict[str, Dict[str, str]],
        create_backup: bool = True
    ) -> bool:
        p = Path(file_path)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("", encoding="utf-8")

        make_file_writable(p)

        if create_backup:
            orig_bak = p.with_suffix(p.suffix + ".orig.bak")
            if not orig_bak.exists():
                try:
                    shutil.copy2(p, orig_bak)
                except Exception as e:
                    log.warning(f"Failed to create backup {orig_bak}: {e}")

        raw_text = p.read_text(encoding="utf-8", errors="ignore")
        lines = raw_text.splitlines()

        out_lines: List[str] = []
        current_section: Optional[str] = None
        handled_keys: Dict[str, set] = {sec: set() for sec in updates}
        seen_sections: set = set()

        section_pattern = re.compile(r"^\s*\[([^\]]+)\]\s*$")
        kv_pattern = re.compile(r"^(\s*)([^;#=\s]+)(\s*=\s*)(.*)$")

        def flush_missing_keys(sec_name: Optional[str]):
            if not sec_name:
                return
            target_sec_key = next((s for s in updates if s.lower() == sec_name.lower()), None)
            if target_sec_key:
                for k, v in updates[target_sec_key].items():
                    if k.lower() not in handled_keys[target_sec_key]:
                        out_lines.append(f"{k}={v}")
                        handled_keys[target_sec_key].add(k.lower())

        for line in lines:
            sec_match = section_pattern.match(line)
            if sec_match:
                flush_missing_keys(current_section)
                current_section = sec_match.group(1).strip()
                seen_sections.add(current_section.lower())
                out_lines.append(line)
                continue

            target_sec = None
            if current_section:
                target_sec = next((s for s in updates if s.lower() == current_section.lower()), None)

            if target_sec:
                kv_match = kv_pattern.match(line)
                if kv_match:
                    indent, key, sep, _ = kv_match.groups()
                    key_clean = key.strip().lower()
                    matched_target_k = None
                    for tk in updates[target_sec]:
                        if tk.lower() == key_clean:
                            matched_target_k = tk
                            break

                    if matched_target_k:
                        val = updates[target_sec][matched_target_k]
                        out_lines.append(f"{indent}{matched_target_k}{sep}{val}")
                        handled_keys[target_sec].add(matched_target_k.lower())
                        continue

            out_lines.append(line)

        flush_missing_keys(current_section)

        # 追加原文件中不存在的新 Section
        for sec_name, kv_map in updates.items():
            if sec_name.lower() not in seen_sections:
                if out_lines and out_lines[-1].strip() != "":
                    out_lines.append("")
                out_lines.append(f"[{sec_name}]")
                for k, v in kv_map.items():
                    out_lines.append(f"{k}={v}")

        try:
            make_file_writable(p)
            p.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
            return True
        except PermissionError as e:
            log.error(f"PermissionError writing to {p}: {e}")
            return False
        except Exception as e:
            log.error(f"Failed writing to {p}: {e}")
            return False

    @classmethod
    def set_option(
        cls,
        file_path: Path | str,
        section_name: str,
        option_name: str,
        option_value: str
    ) -> bool:
        return cls.update_sections(file_path, {section_name: {option_name: str(option_value)}})

    @classmethod
    def remove_option(
        cls,
        file_path: Path | str,
        section_name: str,
        option_name: str
    ) -> bool:
        p = Path(file_path)
        if not p.exists():
            return False

        make_file_writable(p)
        raw_text = p.read_text(encoding="utf-8", errors="ignore")
        lines = raw_text.splitlines()

        out_lines: List[str] = []
        current_section: Optional[str] = None
        section_pattern = re.compile(r"^\s*\[([^\]]+)\]\s*$")
        kv_pattern = re.compile(r"^\s*([^;#=\s]+)\s*=")
        modified = False

        for line in lines:
            sec_match = section_pattern.match(line)
            if sec_match:
                current_section = sec_match.group(1).strip()
                out_lines.append(line)
                continue

            if current_section and current_section.lower() == section_name.lower():
                kv_match = kv_pattern.match(line)
                if kv_match and kv_match.group(1).strip().lower() == option_name.lower():
                    modified = True
                    continue

            out_lines.append(line)

        if not modified:
            return True

        try:
            make_file_writable(p)
            p.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
            return True
        except PermissionError as e:
            log.error(f"PermissionError writing to {p}: {e}")
            return False
        except Exception as e:
            log.error(f"Failed removing option from {p}: {e}")
            return False
