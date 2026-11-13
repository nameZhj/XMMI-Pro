import os
import re
import shutil
import zipfile
import tarfile
import logging
import time
import subprocess
import threading
import ctypes
from ctypes import wintypes
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Set, Dict, Callable, Any

import psutil
import platform
from core.utils.lossless_ini_editor import LosslessIniEditor, make_file_writable

import core.config_manager as Config
import core.path_manager as Paths
from core.locale_manager import L

try:
    import py7zr
except ImportError:
    py7zr = None

try:
    import rarfile
    for cand in [
        r'C:\Program Files\WinRAR\UnRAR.exe',
        r'C:\Program Files (x86)\WinRAR\UnRAR.exe',
        r'C:\Program Files\WinRAR\WinRAR.exe',
        r'C:\Program Files (x86)\WinRAR\WinRAR.exe'
    ]:
        if Path(cand).exists():
            rarfile.UNRAR_TOOL = cand
            break
except ImportError:
    rarfile = None

log = logging.getLogger(__name__)


class PasswordRequiredException(Exception):
    """Raised when an archive requires a password or provided password was invalid."""
    pass


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}
PREFERRED_PREVIEW_NAMES = {
    'preview', 'thumbnail', 'cover', 'screenshot', 'image', 'icon', 'main', 'mod', 'card', '0'
}

# Character Registry: (ID, CN Name, EN Name, [Pinyin], [GUIDs])
CHARACTER_DATABASE = [
    # --- 鸣潮 (WWMI) ---
    ('suisui', '穗穗', 'SuiSui', ['suisui'], ['276291', '9300', '85755']),
    ('jinhsi', '今汐', 'Jinhsi', ['jinxi', 'jinhsi'], ['266291']),
    ('changli', '长离', 'Changli', ['changli'], ['266292']),
    ('camellya', '椿', 'Camellya', ['chun', 'camellya'], ['266293']),
    ('shorekeeper', '守岸人', 'Shorekeeper', ['shouanren', 'shorekeeper'], ['266294']),
    ('yinlin', '吟霖', 'Yinlin', ['yinlin'], ['266295']),
    ('yangyang', '秧秧', 'Yangyang', ['yangyang'], ['266296']),
    ('verina', '维里奈', 'Verina', ['weilinai', 'verina'], ['266297']),
    ('sanhua', '散华', 'Sanhua', ['sanhua'], ['266298']),
    ('danjin', '丹瑾', 'Danjin', ['danjin'], ['266299']),
    ('jianxin', '鉴心', 'Jianxin', ['jianxin'], ['266300']),
    ('rover_f', '漂泊者女', 'Rover-F', ['piaobozhenv', 'rover'], ['266301']),
    ('rover_m', '漂泊者男', 'Rover-M', ['piaobozhenan', 'rover'], ['266302']),
    ('chixia', '炽霞', 'Chixia', ['chixia'], ['266303']),
    ('jiyan', '忌炎', 'Jiyan', ['jiyan'], ['266304']),
    ('xiangliyao', '相里要', 'Xiangli Yao', ['xiangliyao'], ['266305']),
    ('zhezhi', '折枝', 'Zhezhi', ['zhezhi'], ['266306']),
    ('youhu', '釉瑚', 'Youhu', ['youhu'], ['266307']),
    ('baizhi', '白芷', 'Baizhi', ['baizhi'], ['266308']),
    ('taoqi', '桃祈', 'Taoqi', ['taoqi'], ['266309']),
    ('calcharo', '卡卡罗', 'Calcharo', ['kakaluo', 'calcharo'], ['266310']),
    ('rococo', '洛可可', 'Rococo', ['luokeke', 'rococo'], ['266311']),
    ('phoebe', '菲比', 'Phoebe', ['feibi', 'phoebe'], ['266312']),
    ('brant', '布兰特', 'Brant', ['bulante', 'brant'], ['266313']),
    ('colletta', '珂莱塔', 'Colletta', ['kelaita', 'colletta'], ['266314']),
    ('aemeath', '爱弥斯', 'Aemeath', ['aimisi', 'aemeath'], ['266315']),
    ('lumi', '灯灯', 'Lumi', ['dengdeng', 'lumi'], ['266316']),
    ('chisa', '千咲', 'Chisa', ['qianxiao', 'chisa'], ['266317']),
    ('qingxiao', '青宵', 'Qingxiao', ['qingxiao'], ['266318']),
    ('hsin', '心/辛', 'Hsin', ['hsin'], ['266319']),

    # --- 原神 (GIMI) ---
    ('raiden', '雷电将军', 'Raiden Shogun', ['leidianjiangjun', 'raiden', 'leishen'], []),
    ('furina', '芙宁娜', 'Furina', ['funingna', 'furina', 'shuishen'], []),
    ('nahida', '纳西妲', 'Nahida', ['naxida', 'nahida', 'caoshen'], []),
    ('hutao', '胡桃', 'Hu Tao', ['hutao'], []),
    ('ganyu', '甘雨', 'Ganyu', ['ganyu'], []),
    ('yelan', '夜兰', 'Yelan', ['yelan'], []),
    ('zhongli', '钟离', 'Zhongli', ['zhongli'], []),
    ('keqing', '刻晴', 'Keqing', ['keqing'], []),
    ('shenhe', '申鹤', 'Shenhe', ['shenhe'], []),
    ('yaemiko', '八重神子', 'Yae Miko', ['bachongshenzi', 'yaemiko', 'yae'], []),

    # --- 星穹铁道 (SRMI) ---
    ('acheron', '黄泉', 'Acheron', ['huangquan', 'acheron'], []),
    ('firefly', '流萤', 'Firefly', ['liuying', 'firefly'], []),
    ('sparkle', '花火', 'Sparkle', ['huahua', 'sparkle'], []),
    ('kafka', '卡芙卡', 'Kafka', ['kafuka', 'kafka'], []),
    ('fuxuan', '符玄', 'Fu Xuan', ['fuxuan'], []),
    ('jingliu', '镜流', 'Jingliu', ['jingliu'], []),
    ('ruanmei', '阮·梅', 'Ruan Mei', ['ruanmei'], []),
    ('robin', '知更鸟', 'Robin', ['zhigengniao', 'robin'], []),

    # --- 绝区零 (ZZMI) ---
    ('janedoe', '简·杜', 'Jane Doe', ['jiandu', 'janedoe', 'jane'], []),
    ('zhuyuan', '朱鸢', 'Zhu Yuan', ['zhuyuan'], []),
    ('ellen', '艾莲·乔', 'Ellen Joe', ['ailian', 'ellen', 'ellenjoe'], []),
    ('qingyi', '青衣', 'Qingyi', ['qingyi'], []),
    ('burnice', '柏妮思', 'Burnice', ['bainisi', 'burnice'], []),
    ('yanagi', '柳', 'Yanagi', ['yanagi'], []),
    ('miyabi', '星见雅', 'Miyabi', ['xingjianya', 'miyabi'], []),
]

# Quick GUID lookup dictionary
GUID_TO_CHAR_INFO = {}
for cid, cname, ename, pinyin_list, guids in CHARACTER_DATABASE:
    for g in guids:
        GUID_TO_CHAR_INFO[g] = (cid, cname, ename)


@dataclass
class ModHotkey:
    key_raw: str
    key_display: str
    action_name: str
    action_type: str  # 'cycle' (循环切换), 'hold' (长按调整), 'toggle' (开关切换), 'press' (触发)
    ini_file: str
    variable_name: str = ""
    values: str = ""
    condition: str = ""


@dataclass
class ModItem:
    name: str
    display_name: str
    path: Path
    enabled: bool
    thumbnail_path: Optional[Path] = None
    file_count: int = 0
    size_bytes: int = 0
    mod_time: float = 0.0
    character_id: str = 'other'
    character_name: str = '通用模组'
    character_en: str = 'Generic'
    object_guids: List[str] = field(default_factory=list)
    conflict_key: str = ''
    hotkeys: List[ModHotkey] = field(default_factory=list)


@dataclass
class CharacterMenuItem:
    character_id: str
    name_cn: str
    name_en: str
    display_title: str
    guids: List[str]
    search_keywords: List[str]
    total_count: int = 0
    enabled_count: int = 0


@dataclass
class ModRepairOptions:
    """Options for Wuwa / 3DMigoto Mod Repair Engine."""
    fix_hashes: bool = True               # 1. 游戏版本更新 Hash 修复 (Main Hashes & Texture Hashes)
    fix_vertex_groups: bool = True        # 2. 骨骼与顶点组重映射 (Vertex Group Remap)
    fix_derive_textures: bool = True      # 3. 衍生贴图与 LOD 自动补全 (Derive & LOD Textures)
    fix_rules: bool = True                # 4. 索引规则与 Shapekey 修复 (Rules & Index Replacement)
    fix_resource_override: bool = True    # 5. 追加资源重载检查 (CheckTextureOverride)
    fix_stable_texture: bool = True       # 6. 状态贴图稳定模式 (Stable State Textures)
    fix_rendering_33: bool = True         # 7. Rendering 3.3 管线修复 (COLOR1 顶点掩码属性清理，防黑屏)
    fix_rover_special: bool = False       # 8. 主角材质与风主眼部专属修复 (按需开启，源码 enable_aero_rover_fix 默认为 false)
    inject_engine_ini: bool = False       # 9. Engine.ini 渲染与防破图参数注入 (修改游戏全局配置，按需开启)
    clean_trash_files: bool = True        # 清理冗余/临时干扰文件 (.DS_Store, Thumbs.db, etc.)
    normalize_ini: bool = True            # 规范化 .ini 编码 (UTF-8) 与路径反斜杠
    create_backup: bool = True            # 修复前自动创建安全回滚备份


class ModService:
    _fix_config_cache = None
    KEY_NAME_MAP = {
        'RSHIFT': '右 Shift',
        'LSHIFT': '左 Shift',
        'SHIFT': 'Shift',
        'RCTRL': '右 Ctrl',
        'LCTRL': '左 Ctrl',
        'CTRL': 'Ctrl',
        'RALT': '右 Alt',
        'LALT': '左 Alt',
        'ALT': 'Alt',
        'VK_UP': '↑',
        'VK_DOWN': '↓',
        'VK_LEFT': '←',
        'VK_RIGHT': '→',
        'VK_BACK': 'Backspace',
        'VK_RETURN': 'Enter',
        'VK_SPACE': 'Space',
        'VK_TAB': 'Tab',
        'VK_ESCAPE': 'Esc',
        'VK_OEM_1': ';',
        'VK_OEM_PLUS': '+',
        'VK_OEM_COMMA': ',',
        'VK_OEM_MINUS': '-',
        'VK_OEM_PERIOD': '.',
        'VK_OEM_2': '/',
        'VK_OEM_3': '`',
        'VK_OEM_4': '[',
        'VK_OEM_5': '\\',
        'VK_OEM_6': ']',
        'VK_OEM_7': "'",
        'VK_PRIOR': 'Page Up',
        'VK_NEXT': 'Page Down',
        'VK_END': 'End',
        'VK_HOME': 'Home',
        'VK_INSERT': 'Insert',
        'VK_DELETE': 'Delete',
    }

    ACTION_PATTERNS = [
        (re.compile(r'hair.*color', re.I), '发色切换 (Hair Color)'),
        (re.compile(r'eye.*color', re.I), '瞳色切换 (Eye Color)'),
        (re.compile(r'outfit.*color|cloth.*color|dress.*color', re.I), '服装配色 (Outfit Color)'),
        (re.compile(r'bodysuit.*color|body.*color|skin.*color', re.I), '连体衣/内衣配色 (Bodysuit)'),
        (re.compile(r'hair.*setup|hair.*style|hairpin|hair', re.I), '发型/发饰样式 (Hair Setup)'),
        (re.compile(r'breast.*setup|boob.*setup|chest|boob', re.I), '胸围/体型样式 (Breast Setup)'),
        (re.compile(r'express.*lock|lock', re.I), '表情/动作锁定 (Express Lock)'),
        (re.compile(r'weapon.*color|weapon', re.I), '武器配色 (Weapon Color)'),
        (re.compile(r'boobsorbuttorsize|togglesize|target', re.I), '体型微调目标 (Target)'),
        (re.compile(r'holdright|sizeup|increase|scaleup', re.I), '增大微调 (Size +)'),
        (re.compile(r'holdleft|sizedown|decrease|scaledown', re.I), '缩小微调 (Size -)'),
        (re.compile(r'resetsize|reset', re.I), '重置微调 (Reset Size)'),
        (re.compile(r'enable_mods|toggle_mod|togglemod|visibility|hide', re.I), '模组显隐开关 (Toggle Mod)'),
        (re.compile(r'glasses|spectacles', re.I), '眼镜切换 (Glasses)'),
        (re.compile(r'hat|cap|head', re.I), '帽子/头饰切换 (Headwear)'),
        (re.compile(r'jacket|coat|outer', re.I), '外套脱穿切换 (Jacket)'),
        (re.compile(r'shoe|foot|boots', re.I), '鞋子款式切换 (Shoes)'),
        (re.compile(r'tail', re.I), '尾巴显隐切换 (Tail)'),
        (re.compile(r'wing', re.I), '翅膀显隐切换 (Wings)'),
        (re.compile(r'mask', re.I), '面具显隐切换 (Mask)'),
    ]

    @classmethod
    def format_key_display(cls, raw_key: str) -> str:
        """Converts raw 3DMigoto key combination string into friendly readable keyboard tags."""
        tokens = raw_key.strip().split()
        clean_tokens = []
        for t in tokens:
            tu = t.upper()
            if tu in ('NO_CTRL', 'NO_ALT', 'NO_SHIFT', 'NO_MODIFIERS'):
                continue
            if tu in cls.KEY_NAME_MAP:
                clean_tokens.append(cls.KEY_NAME_MAP[tu])
            elif tu.startswith('VK_'):
                clean_tokens.append(tu[3:])
            else:
                clean_tokens.append(t)
        return ' + '.join(clean_tokens) if clean_tokens else raw_key

    @classmethod
    def parse_mod_hotkeys(cls, mod_path: Path) -> List[ModHotkey]:
        """
        Scans all .ini files within the mod folder and extracts [Key...] sections,
        translating key codes and action identifiers into human-friendly Chinese descriptions.
        """
        hotkeys: List[ModHotkey] = []
        if not mod_path.is_dir():
            return hotkeys

        seen_keys: Set[Tuple[str, str]] = set()

        try:
            for ini_file in mod_path.rglob("*.ini"):
                try:
                    text = ini_file.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    continue

                current_sec = None
                sec_raw_key = ""
                sec_type = "press"
                sec_condition = ""
                sec_var_name = ""
                sec_values = ""

                def _commit_section(s_name, s_key, s_type, s_cond, s_var, s_val, f_name):
                    if not s_key:
                        return
                    disp_key = cls.format_key_display(s_key)

                    # Determine action name
                    clean_action = s_name
                    if clean_action.lower().startswith('keyswap'):
                        clean_action = clean_action[7:]
                    elif clean_action.lower().startswith('keyhold'):
                        clean_action = clean_action[7:]
                    elif clean_action.lower().startswith('key'):
                        clean_action = clean_action[3:]
                    clean_action = clean_action.strip('_ ')

                    action_display = None
                    target_search = f"{s_name} {s_var} {clean_action}"
                    for pattern, label in cls.ACTION_PATTERNS:
                        if pattern.search(target_search):
                            action_display = label
                            break

                    if not action_display:
                        action_display = clean_action or "按键控制"

                    # Normalize trigger type
                    type_labels = {
                        'cycle': '循环切换',
                        'hold': '长按调整',
                        'toggle': '开关切换',
                        'press': '单次触发'
                    }
                    disp_type = type_labels.get(s_type.lower(), s_type)

                    dedup_key = (disp_key.lower(), action_display.lower())
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        hotkeys.append(ModHotkey(
                            key_raw=s_key,
                            key_display=disp_key,
                            action_name=action_display,
                            action_type=disp_type,
                            ini_file=f_name,
                            variable_name=s_var,
                            values=s_val,
                            condition=s_cond
                        ))

                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith(';'):
                        continue

                    if line.startswith('[') and line.endswith(']'):
                        if current_sec:
                            _commit_section(current_sec, sec_raw_key, sec_type, sec_condition, sec_var_name, sec_values, ini_file.name)

                        sec_name = line[1:-1].strip()
                        if sec_name.lower().startswith('key'):
                            current_sec = sec_name
                            sec_raw_key = ""
                            sec_type = "press"
                            sec_condition = ""
                            sec_var_name = ""
                            sec_values = ""
                        else:
                            current_sec = None
                    elif current_sec and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip().lower()
                        v = v.strip()
                        if k == 'key':
                            sec_raw_key = v
                        elif k == 'type':
                            sec_type = v
                        elif k == 'condition':
                            sec_condition = v
                        elif k.startswith('$'):
                            sec_var_name = k
                            sec_values = v

                if current_sec:
                    _commit_section(current_sec, sec_raw_key, sec_type, sec_condition, sec_var_name, sec_values, ini_file.name)

        except Exception as e:
            log.debug(f"Error parsing hotkeys for {mod_path}: {e}")

        return hotkeys

    @staticmethod
    def get_active_mods_folder() -> Optional[Path]:
        """Returns the active importer's Mods folder path, creating it if needed."""
        try:
            launcher_cfg = getattr(Config, 'Launcher', None)
            if not launcher_cfg:
                return None
            active_importer = getattr(launcher_cfg, 'active_importer', None)
            if not active_importer or active_importer == 'XXMI':
                return None
            
            importers_obj = getattr(Config, 'Importers', None)
            if not importers_obj:
                return None
            importer_package = getattr(importers_obj, active_importer, None)
            if importer_package is None and hasattr(importers_obj, '__dict__'):
                importer_package = importers_obj.__dict__.get(active_importer, None)
            if importer_package is None:
                return None
            
            importer_cfg = getattr(importer_package, 'Importer', None)
            if not importer_cfg or not hasattr(importer_cfg, 'importer_path'):
                return None
            mods_path = importer_cfg.importer_path / 'Mods'
            Paths.verify_path(mods_path)
            return mods_path
        except Exception as e:
            log.exception(f"Failed to get active mods folder: {e}")
            return None

    @classmethod
    def find_thumbnail(cls, folder_path: Path) -> Optional[Path]:
        """Finds the most suitable preview thumbnail inside a mod folder."""
        if not folder_path.is_dir():
            return None

        preferred_match = None
        first_image = None

        try:
            for root, dirs, files in os.walk(folder_path):
                rel_depth = len(Path(root).relative_to(folder_path).parts)
                if rel_depth > 2:
                    continue

                for file in files:
                    file_path = Path(root) / file
                    suffix = file_path.suffix.lower()
                    if suffix in IMAGE_EXTENSIONS:
                        stem = file_path.stem.lower()
                        if first_image is None:
                            first_image = file_path
                        if stem in PREFERRED_PREVIEW_NAMES:
                            return file_path
                        for pref in PREFERRED_PREVIEW_NAMES:
                            if pref in stem and preferred_match is None:
                                preferred_match = file_path
        except Exception as e:
            log.debug(f"Error scanning thumbnail for {folder_path}: {e}")

        return preferred_match or first_image

    @classmethod
    def analyze_mod_features(cls, folder_path: Path, display_name: str) -> Tuple[str, str, str, List[str], str]:
        """
        Analyzes mod files (.ini) to determine character identity, GUIDs, and conflict group.
        Returns: (character_id, character_name_cn, character_name_en, object_guids, conflict_key)
        """
        guids = set()
        hashes = set()
        namespaces = set()
        ini_text_corpus = []

        try:
            ini_files = list(folder_path.glob('**/*.ini'))
            for ini in ini_files:
                try:
                    text = ini.read_text(encoding='utf-8', errors='ignore')
                    ini_text_corpus.append(text[:2000])
                    for m in re.finditer(r'object_guid\s*=\s*(\d+)', text, re.IGNORECASE):
                        guid_val = m.group(1)
                        if guid_val not in {'-1000', '0'}:
                            guids.add(guid_val)
                    for m in re.finditer(r'hash\s*=\s*([0-9a-fA-F]{8})', text, re.IGNORECASE):
                        hashes.add(m.group(1).lower())
                    for m in re.finditer(r'namespace\s*=\s*([a-zA-Z0-9_]+)', text, re.IGNORECASE):
                        namespaces.add(m.group(1).lower())
                except Exception:
                    pass
        except Exception as e:
            log.debug(f"Error reading inis in {folder_path}: {e}")

        sorted_guids = sorted(list(guids))

        # 1. Match by GUID in database
        for g in sorted_guids:
            if g in GUID_TO_CHAR_INFO:
                cid, cname, ename = GUID_TO_CHAR_INFO[g]
                return cid, cname, ename, sorted_guids, f"MOD_{folder_path.name}"

        # 2. Match character by folder or display name (highest priority and precision)
        combined_name = f"{folder_path.name} {display_name}".lower()
        for cid, cname, ename, pinyin_list, char_guids in CHARACTER_DATABASE:
            if cname in folder_path.name or cname in display_name:
                return cid, cname, ename, sorted_guids, f"MOD_{folder_path.name}"
            check_words = [ename.lower()] + [p.lower() for p in pinyin_list if len(p) >= 3]
            for w in check_words:
                if re.search(rf'(?i)\b{re.escape(w)}\b', combined_name):
                    return cid, cname, ename, sorted_guids, f"MOD_{folder_path.name}"

        # 3. Match character in ini namespaces and corpus with strict word boundaries
        corpus_search = (" ".join(namespaces) + " " + " ".join(ini_text_corpus[:3])).lower()
        for cid, cname, ename, pinyin_list, char_guids in CHARACTER_DATABASE:
            if cname in corpus_search:
                return cid, cname, ename, sorted_guids, f"MOD_{folder_path.name}"
            check_words = [ename.lower()] + [p.lower() for p in pinyin_list if len(p) >= 3]
            for w in check_words:
                if re.search(rf'(?i)\b{re.escape(w)}\b', corpus_search):
                    return cid, cname, ename, sorted_guids, f"MOD_{folder_path.name}"

        # 4. Fallback: Unknown character with GUID or Generic Mod
        if sorted_guids:
            primary_guid = sorted_guids[0]
            return f"guid_{primary_guid}", f"角色 [ID: {primary_guid}]", f"Character [ID: {primary_guid}]", sorted_guids, f"MOD_{folder_path.name}"
        else:
            return "other", "通用模组", "Generic", [], f"MOD_{folder_path.name}"

    @classmethod
    def get_folder_stats(cls, folder_path: Path) -> Tuple[int, int]:
        """Calculates total file count and size in bytes."""
        count = 0
        total_size = 0
        try:
            if folder_path.is_file():
                return 1, folder_path.stat().st_size
            for root, _, files in os.walk(folder_path):
                for f in files:
                    count += 1
                    try:
                        total_size += (Path(root) / f).stat().st_size
                    except Exception:
                        pass
        except Exception:
            pass
        return count, total_size

    @classmethod
    def scan_mods(cls, search_query: str = '', filter_state: str = 'all', filter_character_id: str = 'all', auto_resolve: bool = False) -> List[ModItem]:
        """
        Scans the active Mods folder and returns a list of ModItem.
        Non-destructive: does not modify folder names during directory scan.
        """
        mods_folder = cls.get_active_mods_folder()
        if not mods_folder or not mods_folder.is_dir():
            return []

        mod_items: List[ModItem] = []
        try:
            entries = sorted(mods_folder.iterdir(), key=lambda p: p.name.lower())
        except Exception as e:
            log.exception(f"Failed to list mods folder {mods_folder}: {e}")
            return []

        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name.startswith('.') or entry.name.lower() in {'ini_validator_cache.json', 'desktop.ini', 'thumbs.db'}:
                continue

            name = entry.name
            is_disabled = (
                name.upper().startswith('DISABLED ') or
                name.upper().startswith('DISABLED_') or
                name.lower().endswith('.disabled')
            )
            enabled = not is_disabled

            display_name = name
            if name.upper().startswith('DISABLED '):
                display_name = name[9:].strip()
            elif name.upper().startswith('DISABLED_'):
                display_name = name[9:].strip()
            elif name.lower().endswith('.disabled'):
                display_name = name[:-9].strip()

            cid, cname, ename, guids, conflict_key = cls.analyze_mod_features(entry, display_name)

            thumbnail = cls.find_thumbnail(entry)
            file_count, size_bytes = cls.get_folder_stats(entry)
            try:
                mod_time = entry.stat().st_mtime
            except Exception:
                mod_time = 0.0

            hotkeys = cls.parse_mod_hotkeys(entry)

            mod_items.append(ModItem(
                name=name,
                display_name=display_name,
                path=entry,
                enabled=enabled,
                thumbnail_path=thumbnail,
                file_count=file_count,
                size_bytes=size_bytes,
                mod_time=mod_time,
                character_id=cid,
                character_name=cname,
                character_en=ename,
                object_guids=guids,
                conflict_key=conflict_key,
                hotkeys=hotkeys
            ))

        # Auto-resolve duplicate active mods in the same character group
        if auto_resolve:
            enabled_by_conflict: Dict[str, List[ModItem]] = {}
            for m in mod_items:
                if m.enabled and m.conflict_key and not m.conflict_key.startswith('MOD_'):
                    enabled_by_conflict.setdefault(m.conflict_key, []).append(m)

            has_resolved = False
            for ckey, clist in enabled_by_conflict.items():
                if len(clist) > 1:
                    for extra_mod in clist[1:]:
                        cls.toggle_mod(extra_mod, enable=False, auto_resolve_conflicts=False)
                        has_resolved = True

            if has_resolved:
                return cls.scan_mods(
                    search_query=search_query,
                    filter_state=filter_state,
                    filter_character_id=filter_character_id,
                    auto_resolve=False
                )

        # Apply Filters
        filtered = []
        for m in mod_items:
            # Multi-dimensional keyword search: CN, EN, Pinyin, GUIDs, Mod Name
            if search_query:
                q = search_query.strip().lower()
                matched = False
                if q in m.display_name.lower() or q in m.name.lower() or q in m.character_name.lower() or q in m.character_en.lower():
                    matched = True
                elif any(q in g for g in m.object_guids):
                    matched = True
                else:
                    # Check character pinyin from database
                    for cid, cname, ename, pinyin_list, guids in CHARACTER_DATABASE:
                        if cid == m.character_id:
                            if any(q in p.lower() for p in pinyin_list):
                                matched = True
                                break
                if not matched:
                    continue

            if filter_state == 'enabled' and not m.enabled:
                continue
            if filter_state == 'disabled' and m.enabled:
                continue
            if filter_character_id != 'all' and m.character_id != filter_character_id:
                continue

            filtered.append(m)

        # Sort: Enabled mods first, then disabled mods, then alphabetically by display name
        filtered.sort(key=lambda m: (not m.enabled, m.display_name.lower()))

        return filtered

    @classmethod
    def get_character_menu_items(cls, all_mods: Optional[List[ModItem]] = None, search_query: str = '') -> List[CharacterMenuItem]:
        """
        Builds the secondary left sidebar menu structure with character categories and counts.
        Supports filtering characters via search_query (CN, EN, Pinyin, GUID).
        """
        if all_mods is None:
            all_mods = cls.scan_mods(auto_resolve=False)

        char_groups: Dict[str, List[ModItem]] = {}
        for m in all_mods:
            char_groups.setdefault(m.character_id, []).append(m)

        menu_items: List[CharacterMenuItem] = []

        # 1. 'All' Item
        total_count = len(all_mods)
        enabled_count = sum(1 for m in all_mods if m.enabled)
        menu_items.append(CharacterMenuItem(
            character_id='all',
            name_cn='全部模组',
            name_en='All Mods',
            display_title=f"🌟 全部模组",
            guids=[],
            search_keywords=['all', 'quanbu', 'qb', '全部'],
            total_count=total_count,
            enabled_count=enabled_count
        ))

        # 2. Detected Characters in DB order then dynamic ones
        matched_char_ids = set(char_groups.keys())

        # First add known characters from database that have mods
        for cid, cname, ename, pinyin_list, guids in CHARACTER_DATABASE:
            if cid in char_groups:
                mods_in_char = char_groups[cid]
                t_count = len(mods_in_char)
                e_count = sum(1 for m in mods_in_char if m.enabled)
                all_kws = [cname.lower(), ename.lower()] + [p.lower() for p in pinyin_list] + guids
                menu_items.append(CharacterMenuItem(
                    character_id=cid,
                    name_cn=cname,
                    name_en=ename,
                    display_title=f"👤 {cname} ({ename})",
                    guids=guids,
                    search_keywords=all_kws,
                    total_count=t_count,
                    enabled_count=e_count
                ))
                matched_char_ids.discard(cid)

        # Then add remaining characters (e.g. unknown GUIDs or other categories)
        for cid in sorted(list(matched_char_ids)):
            mods_in_char = char_groups[cid]
            cname = mods_in_char[0].character_name
            ename = mods_in_char[0].character_en
            t_count = len(mods_in_char)
            e_count = sum(1 for m in mods_in_char if m.enabled)
            guids = mods_in_char[0].object_guids
            kws = [cname.lower(), ename.lower(), cid.lower()] + guids
            display_prefix = "👤 " if cid != "other" else "📦 "
            menu_items.append(CharacterMenuItem(
                character_id=cid,
                name_cn=cname,
                name_en=ename,
                display_title=f"{display_prefix}{cname}",
                guids=guids,
                search_keywords=kws,
                total_count=t_count,
                enabled_count=e_count
            ))

        # Filter menu items if search_query is provided
        if search_query:
            q = search_query.strip().lower()
            filtered_menu = []
            for item in menu_items:
                if item.character_id == 'all':
                    filtered_menu.append(item)
                    continue
                # Check search keywords
                if any(q in kw for kw in item.search_keywords) or q in item.name_cn.lower() or q in item.name_en.lower() or q in item.display_title.lower():
                    filtered_menu.append(item)
            return filtered_menu

        return menu_items

    @classmethod
    def sync_mod_state_to_game(cls) -> bool:
        """
        Sends the 3DMigoto F10 reload command directly to running game windows
        so that mod changes (enable, disable, repair, restore, delete, import)
        are applied in-game in real time without needing manual F10 key presses.
        Runs asynchronously in a background thread to prevent UI freezing.
        """
        def _worker():
            try:
                user32 = ctypes.windll.user32

                # 1. Target game executable names
                target_exe_names = {
                    "client-win64-shipping.exe",
                    "wuthering waves.exe",
                    "genshinimpact.exe",
                    "yuanshen.exe",
                    "starrail.exe",
                    "zenlesszonezero.exe"
                }

                # Add exe names from current active importer
                active_importer = getattr(Config.Launcher, 'active_importer', None)
                if active_importer and active_importer in Config.Importers.__dict__:
                    importer_cfg = Config.Importers.__dict__[active_importer].Importer
                    for exe_name in getattr(importer_cfg, 'game_exe_names', []):
                        if exe_name:
                            target_exe_names.add(exe_name.lower())

                # 2. Find running game PIDs
                game_pids = set()
                for p in psutil.process_iter(['pid', 'name']):
                    try:
                        pname = p.info['name']
                        if pname and pname.lower() in target_exe_names:
                            game_pids.add(p.info['pid'])
                    except Exception:
                        pass

                if not game_pids:
                    log.debug("No active game processes detected for mod reload sync.")
                    return

                # 3. Find top-level HWNDs for game processes
                target_hwnds = []
                WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

                def _enum_proc(hwnd, lparam):
                    if user32.IsWindow(hwnd):
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        if pid.value in game_pids:
                            target_hwnds.append(hwnd)
                    return True

                user32.EnumWindows(WNDENUMPROC(_enum_proc), 0)

                if not target_hwnds:
                    log.debug("No active game window handles found.")
                    return

                # 4. Send F10 reload keystroke to the game windows
                VK_F10 = 0x79
                WM_KEYDOWN = 0x0100
                WM_KEYUP = 0x0101
                WM_SYSKEYDOWN = 0x0104
                WM_SYSKEYUP = 0x0105

                for hwnd in target_hwnds:
                    user32.PostMessageW(hwnd, WM_KEYDOWN, VK_F10, 0x00440001)
                    user32.PostMessageW(hwnd, WM_KEYUP, VK_F10, 0xC0440001)
                    user32.PostMessageW(hwnd, WM_SYSKEYDOWN, VK_F10, 0x20440001)
                    user32.PostMessageW(hwnd, WM_SYSKEYUP, VK_F10, 0xC0440001)

                log.info(f"Real-time mod state sync triggered for {len(target_hwnds)} game window(s) (PIDs: {list(game_pids)}).")
            except Exception as e:
                log.debug(f"Failed to sync mod state to game: {e}")

        threading.Thread(target=_worker, daemon=True, name="ModStateGameSync").start()
        return True

    @classmethod
    def toggle_mod(cls, mod_item: ModItem, enable: Optional[bool] = None, auto_resolve_conflicts: bool = False) -> Tuple[bool, Optional[ModItem], str, List[str]]:
        """
        Toggles the enabled status of a mod by renaming its folder.
        Self-healing against out-of-sync paths and WinError 2.
        Returns: (success, new_mod_item, message, list_of_auto_disabled_mod_names)
        """
        parent_dir = mod_item.path.parent
        current_path = mod_item.path

        # 1. Self-healing check: Verify if mod_item.path exists on disk
        if not current_path.exists():
            candidates = [
                parent_dir / f"DISABLED_{mod_item.name}",
                parent_dir / f"DISABLED {mod_item.name}",
            ]
            clean_test = mod_item.name
            while clean_test.upper().startswith('DISABLED ') or clean_test.upper().startswith('DISABLED_'):
                clean_test = clean_test[9:].strip()
            candidates.append(parent_dir / clean_test)
            candidates.append(parent_dir / f"DISABLED {clean_test}")
            candidates.append(parent_dir / f"DISABLED_{clean_test}")

            found_path = next((p for p in candidates if p.exists()), None)
            if not found_path and parent_dir.exists():
                for p in parent_dir.iterdir():
                    p_clean = p.name
                    while p_clean.upper().startswith('DISABLED ') or p_clean.upper().startswith('DISABLED_'):
                        p_clean = p_clean[9:].strip()
                    if p_clean.lower() == clean_test.lower():
                        found_path = p
                        break

            if found_path:
                current_path = found_path
                mod_item.path = found_path
                mod_item.name = found_path.name
            else:
                return False, None, f"模组目录不存在: {mod_item.name}", []

        # 2. Determine actual on-disk state
        actual_name = current_path.name
        is_disabled_on_disk = (
            actual_name.upper().startswith('DISABLED ') or
            actual_name.upper().startswith('DISABLED_') or
            actual_name.lower().endswith('.disabled')
        )
        is_enabled_on_disk = not is_disabled_on_disk

        if enable is None:
            enable = not is_enabled_on_disk

        # If on-disk state already matches desired state, no rename needed
        if enable == is_enabled_on_disk:
            new_item = ModItem(
                name=actual_name,
                display_name=mod_item.display_name,
                path=current_path,
                enabled=enable,
                thumbnail_path=cls.find_thumbnail(current_path),
                file_count=mod_item.file_count,
                size_bytes=mod_item.size_bytes,
                mod_time=time.time(),
                character_id=mod_item.character_id,
                character_name=mod_item.character_name,
                character_en=mod_item.character_en,
                object_guids=mod_item.object_guids,
                conflict_key=mod_item.conflict_key,
                hotkeys=mod_item.hotkeys
            )
            cls.sync_mod_state_to_game()
            return True, new_item, "No change", []

        # 3. Clean all DISABLED prefixes to get pure base name
        clean_name = actual_name
        while clean_name.upper().startswith('DISABLED ') or clean_name.upper().startswith('DISABLED_'):
            clean_name = clean_name[9:].strip()
        if clean_name.lower().endswith('.disabled'):
            clean_name = clean_name[:-9].strip()

        if enable:
            new_name = clean_name
        else:
            new_name = f"DISABLED {clean_name}"

        new_path = parent_dir / new_name
        if new_path.exists() and new_path != current_path:
            return False, None, f"目标文件夹已存在: {new_name}", []

        try:
            renamed = False
            for attempt in range(5):
                try:
                    current_path.rename(new_path)
                    renamed = True
                    break
                except (PermissionError, OSError):
                    time.sleep(0.05)

            if not renamed:
                shutil.move(str(current_path), str(new_path))

            new_item = ModItem(
                name=new_name,
                display_name=mod_item.display_name,
                path=new_path,
                enabled=enable,
                thumbnail_path=cls.find_thumbnail(new_path),
                file_count=mod_item.file_count,
                size_bytes=mod_item.size_bytes,
                mod_time=time.time(),
                character_id=mod_item.character_id,
                character_name=mod_item.character_name,
                character_en=mod_item.character_en,
                object_guids=mod_item.object_guids,
                conflict_key=mod_item.conflict_key,
                hotkeys=mod_item.hotkeys
            )
            # Sync real-time state to game
            cls.sync_mod_state_to_game()
            return True, new_item, "Success", []
        except Exception as e:
            log.exception(f"Failed to toggle mod {mod_item.name}: {e}")
            return False, None, str(e), []

    @classmethod
    def set_custom_thumbnail(cls, mod_item: ModItem, src_image_path: Path) -> Tuple[bool, str]:
        """
        Sets or replaces the mod's preview thumbnail image with a custom selected image.
        Saves the image into the mod folder as 'preview.png'.
        """
        if not mod_item.path.exists() or not mod_item.path.is_dir():
            return False, "模组目录不存在"

        if not src_image_path.exists() or not src_image_path.is_file():
            return False, "选中的图片文件不存在"

        try:
            import io
            from PIL import Image

            # Read source image bytes safely
            with open(src_image_path, 'rb') as f:
                img_bytes = io.BytesIO(f.read())

            with Image.open(img_bytes) as img:
                target_dest = mod_item.path / "preview.png"
                img.convert("RGBA").save(target_dest, "PNG")

            return True, "预览图已成功更新"
        except Exception as e:
            log.exception(f"Failed to set custom thumbnail for {mod_item.name}: {e}")
            return False, str(e)

    @classmethod
    def rename_mod(cls, mod_item: ModItem, new_display_name: str) -> Tuple[bool, str, Optional[ModItem]]:
        """
        Renames a mod folder, preserving its DISABLED state prefix.
        """
        new_display_name = new_display_name.strip()
        if not new_display_name:
            return False, "模组名称不能为空", None

        # Sanitize folder name for Windows
        invalid_chars = r'\/:*?"<>|'
        for ch in invalid_chars:
            new_display_name = new_display_name.replace(ch, '_')

        if not mod_item.path.exists():
            return False, "模组原路径不存在", None

        is_disabled = not mod_item.enabled
        new_folder_name = f"DISABLED {new_display_name}" if is_disabled else new_display_name

        parent_dir = mod_item.path.parent
        new_path = parent_dir / new_folder_name

        if new_path.resolve() == mod_item.path.resolve():
            return True, "名称未更改", mod_item

        if new_path.exists():
            return False, f"目标文件夹已存在: {new_folder_name}", None

        try:
            # Resilient rename loop
            renamed = False
            for _ in range(5):
                try:
                    mod_item.path.rename(new_path)
                    renamed = True
                    break
                except PermissionError:
                    time.sleep(0.05)
                except Exception:
                    break

            if not renamed:
                shutil.move(str(mod_item.path), str(new_path))

            cid, cname, ename, guids, conflict_key = cls.analyze_mod_features(new_path, new_display_name)
            new_item = ModItem(
                name=new_folder_name,
                display_name=new_display_name,
                path=new_path,
                enabled=mod_item.enabled,
                thumbnail_path=cls.find_thumbnail(new_path),
                file_count=mod_item.file_count,
                size_bytes=mod_item.size_bytes,
                mod_time=time.time(),
                character_id=cid,
                character_name=cname,
                character_en=ename,
                object_guids=guids,
                conflict_key=conflict_key,
                hotkeys=cls.parse_mod_hotkeys(new_path)
            )
            # Sync real-time state to game
            cls.sync_mod_state_to_game()
            return True, "重命名成功", new_item
        except Exception as e:
            log.exception(f"Failed to rename mod {mod_item.name}: {e}")
            return False, str(e), None

    @classmethod
    def get_wuwa_fix_config_file_path(cls) -> Path:
        """Returns the primary writable path for caching the Wuwa fix definitions."""
        # 1. Check workspace source path
        source_path = Path(__file__).resolve().parent / "wuwa_fix_config.json"
        try:
            if source_path.exists() and os.access(source_path.parent, os.W_OK):
                return source_path
        except Exception:
            pass

        # 2. User local AppData cache path
        user_cache_dir = Path.home() / ".xxmi_launcher"
        try:
            user_cache_dir.mkdir(parents=True, exist_ok=True)
            return user_cache_dir / "wuwa_fix_config.json"
        except Exception:
            pass

        return source_path

    @classmethod
    def get_wuwa_fix_version_info(cls) -> Dict:
        """Returns version and character count of the loaded Wuwa fix database."""
        cfg = cls.get_wuwa_fix_config()
        ver_obj = cfg.get("version", {})
        ver_str = ver_obj.get("current_version", "1.0.0") if isinstance(ver_obj, dict) else str(ver_obj)
        chars_count = len(cfg.get("characters", {}))
        return {
            "version": ver_str,
            "character_count": chars_count,
            "min_required": ver_obj.get("min_required_version", "") if isinstance(ver_obj, dict) else ""
        }

    @classmethod
    def get_wuwa_fix_config(cls) -> Dict:
        """Loads and caches the Wuwa mod fix definitions (119+ characters/weapons)."""
        if cls._fix_config_cache is None:
            try:
                import json
                import sys
                candidates = [
                    Path.home() / ".xxmi_launcher" / "wuwa_fix_config.json",
                    Path(__file__).resolve().parent / "wuwa_fix_config.json",
                    Path(getattr(sys, '_MEIPASS', '')) / "core" / "wuwa_fix_config.json" if hasattr(sys, '_MEIPASS') else None,
                    Path(sys.executable).parent / "core" / "wuwa_fix_config.json",
                    Path(sys.executable).parent / "_internal" / "core" / "wuwa_fix_config.json",
                ]
                best_cfg = None
                best_ver = "0.0.0"
                for c in candidates:
                    if c and c.exists():
                        try:
                            data = json.loads(c.read_text(encoding='utf-8'))
                            ver = data.get("version", {}).get("current_version", "0.0.0") if isinstance(data.get("version"), dict) else str(data.get("version", "0.0.0"))
                            if best_cfg is None or ver >= best_ver:
                                best_ver = ver
                                best_cfg = data
                        except Exception:
                            pass

                if best_cfg:
                    cls._fix_config_cache = best_cfg
                else:
                    cls._fix_config_cache = {"characters": {}, "settings": {}}
            except Exception as e:
                log.debug(f"Failed to load wuwa_fix_config.json: {e}")
                cls._fix_config_cache = {"characters": {}, "settings": {}}
        return cls._fix_config_cache

    @classmethod
    def update_wuwa_fix_config_from_remote(
        cls,
        force: bool = False,
        callback: Optional[Callable[[bool, str], None]] = None
    ) -> Tuple[bool, str, Dict]:
        """
        Dynamically checks for and downloads the latest Wuwa_Mod_Fixer rules and character hashes
        from Moonholder/Wuwa_Mod_Fixer upstream with mirror/CDN fallbacks.
        """
        import urllib.request
        import json
        import ssl

        urls = [
            'https://raw.githubusercontent.com/Moonholder/Wuwa_Mod_Fixer/main/config.json',
            'https://fastly.jsdelivr.net/gh/Moonholder/Wuwa_Mod_Fixer@main/config.json',
            'https://testingcf.jsdelivr.net/gh/Moonholder/Wuwa_Mod_Fixer@main/config.json',
            'https://gcore.jsdelivr.net/gh/Moonholder/Wuwa_Mod_Fixer@main/config.json',
            'https://ghproxy.net/https://raw.githubusercontent.com/Moonholder/Wuwa_Mod_Fixer/main/config.json',
        ]

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        remote_data = None
        last_error = ""

        for u in urls:
            try:
                req = urllib.request.Request(
                    u,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) XMMI-Pro/1.0'}
                )
                with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                    if resp.status == 200:
                        raw_bytes = resp.read()
                        data = json.loads(raw_bytes.decode('utf-8'))
                        if isinstance(data, dict) and 'characters' in data and len(data['characters']) > 0:
                            remote_data = data
                            break
            except Exception as e:
                last_error = str(e)

        if not remote_data:
            msg = f"检查更新失败: 无法连接至规则服务器 ({last_error})"
            if callback:
                callback(False, msg)
            return False, msg, cls.get_wuwa_fix_config()

        # Compare with local version
        current_cfg = cls.get_wuwa_fix_config()
        curr_ver = current_cfg.get("version", {}).get("current_version", "0.0.0") if isinstance(current_cfg.get("version"), dict) else "0.0.0"
        remote_ver = remote_data.get("version", {}).get("current_version", "0.0.0") if isinstance(remote_data.get("version"), dict) else "0.0.0"
        curr_count = len(current_cfg.get("characters", {}))
        remote_count = len(remote_data.get("characters", {}))

        has_update = force or (remote_ver > curr_ver) or (remote_count > curr_count)

        if has_update:
            try:
                save_path = cls.get_wuwa_fix_config_file_path()
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_text(json.dumps(remote_data, ensure_ascii=False, indent=2), encoding='utf-8')
                cls._fix_config_cache = remote_data
                msg = f"鸣潮修复规则库已成功自动更新至 v{remote_ver} (共收录 {remote_count} 个角色与武器规则)"
                log.info(msg)
                if callback:
                    callback(True, msg)
                return True, msg, remote_data
            except Exception as e:
                msg = f"保存更新规则库失败: {e}"
                log.warning(msg)
                if callback:
                    callback(False, msg)
                return False, msg, cls.get_wuwa_fix_config()
        else:
            msg = f"当前鸣潮修复规则库已是最新版本 (v{curr_ver}，共 {curr_count} 个角色/武器)"
            if callback:
                callback(True, msg)
            return True, msg, current_cfg

    @classmethod
    def start_background_rule_updater(cls):
        """Spawns an asynchronous background worker to check and update Wuwa fix rules on startup."""
        def _worker():
            try:
                time.sleep(2)  # Delay slightly after app startup to avoid CPU contention
                cls.update_wuwa_fix_config_from_remote()
            except Exception as e:
                log.debug(f"Background rule update check error: {e}")

        t = threading.Thread(target=_worker, daemon=True, name="WuwaRuleUpdater")
        t.start()

    @staticmethod
    def _safe_backup_name(display_name: str) -> str:
        """Sanitizes a mod display name for safe backup zip file paths on Windows."""
        return re.sub(r'[\\/:*?"<>|]+', '_', display_name).strip() or "mod_backup"

    @classmethod
    def _resolve_mod_path_for_repair(cls, mod_item: ModItem) -> Optional[Path]:
        """Resolves a mod directory even if toggled (DISABLED_ prefix) after UI scan."""
        if mod_item.path.exists():
            return mod_item.path
        parent = mod_item.path.parent
        if not parent.exists():
            return None
        name = mod_item.path.name
        alt_name = name[9:] if name.upper().startswith("DISABLED_") else f"DISABLED_{name}"
        alt_path = parent / alt_name
        if alt_path.exists():
            mod_item.path = alt_path
            mod_item.name = alt_path.name
            mod_item.enabled = not alt_path.name.upper().startswith("DISABLED_")
            return alt_path
        return None

    @staticmethod
    def _extract_hashes_no_comments(lines: List[str]) -> Set[str]:
        """Extracts lowercase 8-hex hashes from active (non-comment) ini content."""
        active_text = '\n'.join(l.split(';', 1)[0] for l in lines)
        return set(re.findall(r'\b[0-9a-fA-F]{8}\b', active_text.lower()))

    @staticmethod
    def _clean_legacy_corrupt_ini_lines(lines: List[str]) -> Tuple[List[str], int]:
        """Removes invalid lines left behind by earlier buggy fixer versions."""
        cleaned: List[str] = []
        removed = 0
        for line in lines:
            low = line.strip().lower()
            if (
                re.match(r'^checktextureoverride\s*=\s*0\b', low)
                or low.startswith('$\\wwmiv1\\vg_remap')
                or low.startswith('; [auto-generated vertex group remap')
            ):
                removed += 1
                continue
            cleaned.append(line)
        return cleaned, removed

    @staticmethod
    def _parse_vg_remap_mapping(remap_str: str) -> Dict[int, int]:
        """Parses comma-separated 'src:dst' vertex group remap pairs."""
        mapping: Dict[int, int] = {}
        for part in str(remap_str).split(','):
            if ':' not in part:
                continue
            src_s, dst_s = part.split(':', 1)
            try:
                src, dst = int(src_s.strip()), int(dst_s.strip())
            except ValueError:
                continue
            if 0 <= src <= 255 and 0 <= dst <= 255 and src != dst:
                mapping[src] = dst
        return mapping

    @classmethod
    def _apply_blend_vg_remap(cls, mod_path: Path, remap_str: str) -> int:
        """Remaps 8-byte stride bone indices in *Blend*.buf files when weights > 0."""
        mapping = cls._parse_vg_remap_mapping(remap_str)
        if not mapping:
            return 0
        modified_files = 0
        for buf_path in list(mod_path.rglob('*Blend*.buf')):
            if '.bak' in buf_path.name.lower() or not buf_path.is_file():
                continue
            try:
                raw = buf_path.read_bytes()
                if len(raw) < 8 or len(raw) % 8 != 0:
                    continue
                buf = bytearray(raw)
                changed = False
                for i in range(0, len(buf), 8):
                    for j in range(4):
                        if buf[i + 4 + j] > 0 and buf[i + j] in mapping:
                            buf[i + j] = mapping[buf[i + j]]
                            changed = True
                if changed:
                    bak = buf_path.with_name(f"{buf_path.name}.orig.bak")
                    if not bak.exists():
                        bak.write_bytes(raw)
                    buf_path.write_bytes(buf)
                    modified_files += 1
            except Exception as e:
                log.debug(f"Error remapping blend buffer {buf_path}: {e}")
        return modified_files

    @staticmethod
    def _parse_ini_sections(lines: List[str]) -> List[Tuple[Optional[str], List[str]]]:
        """Splits ini lines into (header_line_or_None, body_lines) tuples safely."""
        sections: List[Tuple[Optional[str], List[str]]] = []
        cur_header: Optional[str] = None
        cur_body: List[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                sections.append((cur_header, cur_body))
                cur_header = line
                cur_body = []
            else:
                cur_body.append(line)
        sections.append((cur_header, cur_body))
        return sections

    @classmethod
    def _collect_derived_sections(
        cls,
        lines: List[str],
        target_chars: List[Tuple[str, Dict]],
        present_hashes: Set[str]
    ) -> Tuple[List[str], int]:
        """Builds derived LOD/state TextureOverride blocks cloning parent 'this = Resource...'."""
        sections = cls._parse_ini_sections(lines)
        hash_bodies: Dict[str, List[str]] = {}
        for header, body in sections:
            if not header or 'textureoverride' not in header.strip().lower():
                continue
            sec_hash = None
            has_this = False
            clone_lines: List[str] = []
            for bl in body:
                code = bl.split(';', 1)[0].strip()
                m_hash = re.match(r'(?i)^hash\s*=\s*([0-9a-fA-F]{8})\b', code)
                if m_hash:
                    sec_hash = m_hash.group(1).lower()
                    continue
                if re.match(r'(?i)^checktextureoverride\s*=', code):
                    continue
                if code:
                    if re.match(r'(?i)^this\s*=', code):
                        has_this = True
                    clone_lines.append(bl)
            if sec_hash and has_this and sec_hash not in hash_bodies:
                hash_bodies[sec_hash] = clone_lines

        extra_lines: List[str] = []
        added = 0
        for c_name, c_def in target_chars:
            for tex_hash, t_node in c_def.get('textures', {}).items():
                th_low = tex_hash.lower()
                if th_low not in present_hashes or th_low not in hash_bodies:
                    continue
                for dtype, dlist in t_node.get('derive', {}).items():
                    for dhash in dlist:
                        if dhash.lower() in present_hashes:
                            continue
                        extra_lines.append(f"")
                        extra_lines.append(f"; [Auto-generated {dtype} Texture Override for {c_name}]")
                        extra_lines.append(f"[TextureOverride_{c_name}_{dtype}_{dhash}]")
                        extra_lines.append(f"hash = {dhash}")
                        extra_lines.extend(hash_bodies[th_low])
                        present_hashes.add(dhash.lower())
                        added += 1
        return extra_lines, added

    @classmethod
    def _apply_safe_ini_section_injections(
        cls,
        lines: List[str],
        matched_chars: List[Tuple[str, Dict]],
        fix_stable: bool,
        fix_resource_override: bool
    ) -> Tuple[List[str], bool]:
        """Applies skip_components and valid CheckTextureOverride = ps-tX without list mutation loops."""
        if not fix_stable and not fix_resource_override:
            return lines, False
        skip_comps = {
            str(sc).strip().lower()
            for _, c_def in matched_chars
            for sc in c_def.get('skip_components', [])
            if str(sc).strip()
        }
        sections = cls._parse_ini_sections(lines)
        out_lines: List[str] = []
        changed = False
        for header, body in sections:
            new_body = list(body)
            if header and 'textureoverride' in header.strip().lower():
                body_code = [bl.split(';', 1)[0].strip() for bl in new_body]
                body_low = '\n'.join(body_code).lower()

                # Step G: handling = skip for configured unstable components
                if fix_stable and skip_comps and 'handling = skip' not in body_low and 'handling=skip' not in body_low:
                    for idx, code in enumerate(body_code):
                        m_comp = re.match(r'(?i)^component\s*=\s*(\S+)', code)
                        if m_comp and m_comp.group(1).lower() in skip_comps:
                            new_body.insert(idx + 1, 'handling = skip')
                            body_code.insert(idx + 1, 'handling = skip')
                            changed = True
                            break

                # Step H: inject CheckTextureOverride = ps-tX on draw sections referencing texture slots
                if (
                    fix_resource_override
                    and 'match_first_index' in body_low
                    and 'checktextureoverride' not in body_low
                    and 'commandlisttriggerresourceoverrides' not in body_low
                ):
                    slot_match = next(
                        (m for code in body_code if (m := re.match(r'(?i)^(ps-t\d+)\s*=', code))),
                        None
                    )
                    slot_val = slot_match.group(1).lower() if slot_match else None
                    if slot_val:
                        insert_pos = len(new_body)
                        while insert_pos > 0 and not new_body[insert_pos - 1].strip():
                            insert_pos -= 1
                        new_body.insert(insert_pos, f"CheckTextureOverride = {slot_val}")
                        changed = True

            if header is not None:
                out_lines.append(header)
            out_lines.extend(new_body)
        return out_lines, changed

    @classmethod
    def _match_ini_characters(
        cls,
        chars_db: Dict[str, Any],
        present_hashes: Set[str],
        ini_name_lower: str,
        mod_name_lower: str
    ) -> Tuple[List[Tuple[str, Dict]], List[Tuple[str, Dict]]]:
        """Finds matching character/weapon definitions by name or hash presence."""
        matched_chars: List[Tuple[str, Dict]] = []
        hash_chars: List[Tuple[str, Dict]] = []
        for c_name, c_def in chars_db.items():
            name_keys = [c_name.lower()]
            for extra_key in ('character_en', 'character_id'):
                if c_def.get(extra_key):
                    name_keys.append(str(c_def[extra_key]).lower())
            name_hit = any(k and (k in ini_name_lower or k in mod_name_lower) for k in name_keys)

            main_hit = any(
                (mh.get('new') and mh['new'].lower() in present_hashes)
                or any(oh.lower() in present_hashes for oh in mh.get('old', []))
                for mh in c_def.get('main_hashes', [])
            )
            tex_hit = any(
                th.lower() in present_hashes
                or any(ot.lower() in present_hashes for ot in t_node.get('replace', []))
                for th, t_node in c_def.get('textures', {}).items()
            )
            vg_hit = any(
                th.lower() in present_hashes
                for vg in c_def.get('vg_remaps', [])
                for th in vg.get('trigger_hash', [])
            )

            if name_hit or main_hit or vg_hit:
                matched_chars.append((c_name, c_def))
            if main_hit or tex_hit or vg_hit:
                hash_chars.append((c_name, c_def))
        target_chars = matched_chars if matched_chars else hash_chars
        return matched_chars, target_chars

    @classmethod
    def _create_backup_snapshot(cls, mod_item: ModItem, safe_name: str) -> Optional[str]:
        """Creates a pre-repair zip snapshot of .ini files if absent."""
        mods_folder = cls.get_active_mods_folder() or mod_item.path.parent
        if not mods_folder:
            return None
        backup_dir = mods_folder / ".mod_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        for candidate in (backup_dir / f"{safe_name}.zip", backup_dir / f"{mod_item.display_name}.zip"):
            if candidate.exists():
                return None
        backup_zip = backup_dir / f"{safe_name}.zip"
        ini_to_save = [p for p in mod_item.path.rglob('*.ini') if not p.name.endswith('.bak')]
        if not ini_to_save:
            return None
        try:
            with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_p in ini_to_save:
                    zf.write(file_p, file_p.relative_to(mod_item.path))
            return "已创建修复前原始配置安全回滚快照"
        except Exception as e:
            log.debug(f"Failed to create pre-repair backup snapshot: {e}")
            return None

    @classmethod
    def _clean_mod_trash_and_nesting(cls, mod_path: Path) -> List[str]:
        """Removes OS junk/legacy files and flattens a redundant single wrapper folder."""
        fixes: List[str] = []
        trash_names = {'checktexture.ini', 'references.ini', '.ds_store', 'thumbs.db', 'desktop.ini'}
        for item in list(mod_path.rglob('*')):
            if item.is_file() and item.name.lower() in trash_names:
                try:
                    item.unlink()
                    fixes.append(f"已清理冗余/干扰文件: {item.name}")
                except Exception:
                    pass
            elif item.is_dir() and item.name.lower() == '__macosx':
                shutil.rmtree(item, ignore_errors=True)
                fixes.append(f"已清理冗余系统目录: {item.name}")

        trash_filter = trash_names | {'__macosx'}
        sub_items = [p for p in mod_path.iterdir() if p.name.lower() not in trash_filter]
        if len(sub_items) == 1 and sub_items[0].is_dir() and sub_items[0].name.lower() not in {'textures', 'meshes', 'pinmeshes', '0'}:
            temp_swap = mod_path.parent / f"_tmp_swap_{int(time.time() * 1000)}"
            shutil.move(str(sub_items[0]), str(temp_swap))
            for inner_file in temp_swap.iterdir():
                shutil.move(str(inner_file), str(mod_path))
            shutil.rmtree(temp_swap, ignore_errors=True)
            fixes.append("已自动扁平化单层嵌套子目录结构")
        return fixes

    @classmethod
    def _decode_ini_bytes(cls, raw_bytes: bytes) -> str:
        """Decodes ini bytes using UTF-8/GBK fallback chain."""
        for enc in ('utf-8-sig', 'utf-8', 'gbk', 'gb18030', 'latin-1'):
            try:
                return raw_bytes.decode(enc)
            except Exception:
                continue
        return raw_bytes.decode('utf-8', errors='ignore')

    @classmethod
    def _apply_hash_and_rule_replacements(
        cls,
        lines: List[str],
        target_chars: List[Tuple[str, Dict]],
        present_hashes: Set[str],
        fix_hashes: bool,
        fix_rules: bool
    ) -> Tuple[int, int]:
        """Replaces outdated hashes and draw/index rules cleanly in active ini lines."""
        hash_count = 0
        rule_count = 0
        if fix_hashes:
            repl_pairs: List[Tuple[str, str]] = []
            for _, c_def in target_chars:
                for mh in c_def.get('main_hashes', []):
                    new_h = mh.get('new', '')
                    for old_h in mh.get('old', []):
                        if old_h.lower() != new_h.lower() and old_h.lower() in present_hashes:
                            repl_pairs.append((old_h, new_h))
                for new_tex, t_node in c_def.get('textures', {}).items():
                    for old_tex in t_node.get('replace', []):
                        if old_tex.lower() != new_tex.lower() and old_tex.lower() in present_hashes:
                            repl_pairs.append((old_tex, new_tex))
            for old_h, new_h in repl_pairs:
                pat = re.compile(rf'\b{re.escape(old_h)}\b', re.IGNORECASE)
                for idx, l in enumerate(lines):
                    code, sep, comment = l.partition(';')
                    if old_h.lower() in code.lower():
                        new_code = pat.sub(new_h, code)
                        if new_code != code:
                            lines[idx] = f"{new_code}{sep}{comment}"
                            hash_count += 1

        if fix_rules:
            full_text = '\n'.join(l.split(';', 1)[0] for l in lines)
            for _, c_def in target_chars:
                for rule in c_def.get('rules', []):
                    prefix = rule.get('line_prefix', '').lower()
                    for rep in rule.get('replacements', []):
                        new_val = str(rep.get('new', ''))
                        for old_val in rep.get('old', []):
                            old_s = str(old_val)
                            if old_s == new_val or old_s not in full_text:
                                continue
                            val_pat = re.compile(rf'(?<!\w){re.escape(old_s)}(?!\w)')
                            for idx, l in enumerate(lines):
                                code, sep, comment = l.partition(';')
                                if prefix in code.lower() and old_s in code:
                                    new_code = val_pat.sub(new_val, code)
                                    if new_code != code:
                                        lines[idx] = f"{new_code}{sep}{comment}"
                                        rule_count += 1
        return hash_count, rule_count

    @classmethod
    def _apply_rendering_33_and_engine_ini(cls, mod_item: ModItem, options: ModRepairOptions, fixes: List[str]) -> None:
        """Applies Rendering 3.3 TexCoord buffer cleanup and Engine.ini streaming tweaks."""
        if options.fix_rendering_33:
            r33_count = 0
            for tc_buf in list(mod_item.path.rglob('*TexCoord*.buf')):
                if '.bak' in tc_buf.name.lower() or not tc_buf.is_file():
                    continue
                try:
                    raw = tc_buf.read_bytes()
                    if len(raw) >= 16 and len(raw) % 16 == 0:
                        buf = bytearray(raw)
                        changed = False
                        for i in range(0, len(buf), 16):
                            if buf[i + 4] != 0 or buf[i + 6] != 0:
                                buf[i + 4] = 0
                                buf[i + 6] = 0
                                changed = True
                        if changed:
                            bak = tc_buf.with_name(f"{tc_buf.name}.orig.bak")
                            if not bak.exists():
                                bak.write_bytes(raw)
                            tc_buf.write_bytes(buf)
                            r33_count += 1
                except Exception as e:
                    log.debug(f"Error applying Rendering 3.3 fix to {tc_buf}: {e}")
            if r33_count > 0:
                fixes.append(f"已应用 Rendering 3.3 管线修复：清理 {r33_count} 个缓冲文件中的旧版 COLOR1 顶点掩码 (防黑屏)")

        if options.inject_engine_ini:
            try:
                launcher_cfg = getattr(Config, 'Launcher', None)
                active_importer = getattr(launcher_cfg, 'active_importer', None) if launcher_cfg else None
                importers_obj = getattr(Config, 'Importers', None)
                importer_package = getattr(importers_obj, active_importer, None) if (active_importer and importers_obj) else None
                if importer_package is None and importers_obj and active_importer and hasattr(importers_obj, '__dict__'):
                    importer_package = importers_obj.__dict__.get(active_importer, None)
                importer_cfg = getattr(importer_package, 'Importer', None) if importer_package else None
                game_folder = getattr(importer_cfg, 'game_folder', None) if importer_cfg else None
                if game_folder:
                    candidates = [
                        Path(game_folder) / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
                        Path(game_folder) / "Wuthering Waves Game" / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
                        Path(game_folder) / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini",
                    ]
                    engine_ini = next((p for p in candidates if p.exists() and p.is_file()), candidates[0])
                    opt_dict = {
                        "r.Kuro.SkeletalMesh.LODDistanceScale": "25",
                        "r.Streaming.FullyLoadUsedTextures": "1",
                        "r.Streaming.HiddenPrimitiveScale": "25",
                        "r.Streaming.UseAllMips": "1"
                    }
                    if LosslessIniEditor.update_sections(engine_ini, {"ConsoleVariables": opt_dict}):
                        fixes.append("已向游戏 Engine.ini 写入高精模型渲染与防破图参数 (4 项)")
                    else:
                        fixes.append("游戏 Engine.ini 渲染参数更新跳过或受权限保护")
            except Exception as e:
                log.debug(f"Failed to patch Engine.ini: {e}")

    @classmethod
    def has_backup(cls, mod_item: ModItem) -> bool:
        """Checks if a pre-repair backup snapshot exists for the given mod."""
        mods_folder = cls.get_active_mods_folder() or mod_item.path.parent
        if not mods_folder:
            return False
        backup_dir = mods_folder / ".mod_backups"
        safe_name = cls._safe_backup_name(mod_item.display_name)
        return (
            (backup_dir / f"{safe_name}.zip").exists()
            or (backup_dir / f"{mod_item.display_name}.zip").exists()
        )

    @classmethod
    def repair_mod(cls, mod_item: ModItem, options: Optional[ModRepairOptions] = None) -> Tuple[bool, List[str]]:
        r"""
        Comprehensive automated repair for Wuthering Waves (WWMI) & 3DMigoto mods:
        backup snapshots, junk cleanup, path normalization, hash/rule updates,
        binary Blend.buf vertex group remapping, LOD texture cloning, and safe overrides.
        """
        resolved_path = cls._resolve_mod_path_for_repair(mod_item)
        if not resolved_path:
            return False, ["模组目录不存在"]

        if options is None:
            options = ModRepairOptions()

        fixes: List[str] = []
        try:
            if options.create_backup:
                snap_msg = cls._create_backup_snapshot(mod_item, cls._safe_backup_name(mod_item.display_name))
                if snap_msg:
                    fixes.append(snap_msg)

            if options.clean_trash_files:
                fixes.extend(cls._clean_mod_trash_and_nesting(mod_item.path))

            chars_db = cls.get_wuwa_fix_config().get('characters', {})
            ini_files = [p for p in mod_item.path.rglob('*.ini') if not p.name.lower().endswith('.bak')]

            counts = {"ini": 0, "hash": 0, "vg": 0, "derive": 0, "rule": 0, "legacy": 0}
            applied_vg_keys: Set[Tuple[str, str]] = set()
            rover_mats = {'RoverFemale': {'3': 'f813702e', '4': 'e40b43c4'}, 'RoverMale': {'2': 'faf5e483'}}

            for ini_path in ini_files:
                try:
                    raw_bytes = ini_path.read_bytes()
                    lines = cls._decode_ini_bytes(raw_bytes).replace('\r\n', '\n').replace('\r', '\n').split('\n')

                    lines, legacy_removed = cls._clean_legacy_corrupt_ini_lines(lines)
                    modified = legacy_removed > 0
                    counts["legacy"] += legacy_removed

                    if options.normalize_ini:
                        for idx, line in enumerate(lines):
                            if re.match(r'^\s*filename\s*=', line, re.IGNORECASE):
                                new_line = line.replace('/', '\\')
                                if new_line != line:
                                    lines[idx] = new_line
                                    modified = True

                    present_hashes_before = cls._extract_hashes_no_comments(lines)
                    matched_chars, target_chars = cls._match_ini_characters(
                        chars_db, present_hashes_before, ini_path.name.lower(), mod_item.name.lower()
                    )

                    h_cnt, r_cnt = cls._apply_hash_and_rule_replacements(
                        lines, target_chars, present_hashes_before, options.fix_hashes, options.fix_rules
                    )
                    if h_cnt or r_cnt:
                        modified = True
                        counts["hash"] += h_cnt
                        counts["rule"] += r_cnt

                    present_hashes = cls._extract_hashes_no_comments(lines)

                    if options.fix_vertex_groups:
                        for c_name, c_def in target_chars:
                            for vg_remap in c_def.get('vg_remaps', []):
                                remap_str = vg_remap.get('vertex_groups', '')
                                trigger_hashes = vg_remap.get('trigger_hash', [])
                                triggered = (
                                    any(th.lower() in present_hashes_before for th in trigger_hashes)
                                    if trigger_hashes else c_name in {mc[0] for mc in matched_chars}
                                )
                                vg_key = (c_name, remap_str)
                                if triggered and remap_str and vg_key not in applied_vg_keys:
                                    applied_vg_keys.add(vg_key)
                                    counts["vg"] += cls._apply_blend_vg_remap(mod_item.path, remap_str)

                    if options.fix_derive_textures:
                        extra_lines, d_cnt = cls._collect_derived_sections(lines, target_chars, present_hashes)
                        if d_cnt > 0:
                            lines.extend(extra_lines)
                            modified = True
                            counts["derive"] += d_cnt

                    cur_text_lower = '\n'.join(l.split(';', 1)[0] for l in lines).lower()
                    if options.fix_rover_special:
                        for c_name, _ in matched_chars:
                            for comp_id, mat_hash in rover_mats.get(c_name, {}).items():
                                if f"component = {comp_id}" in cur_text_lower and mat_hash not in present_hashes:
                                    lines.append(
                                        f"\n; [Auto-generated Rover Materialmap Override for Component {comp_id}]\n"
                                        f"[TextureOverride_Rover_Material_{comp_id}]\nhash = {mat_hash}\n"
                                    )
                                    present_hashes.add(mat_hash.lower())
                                    modified = True

                    lines, sec_changed = cls._apply_safe_ini_section_injections(
                        lines, matched_chars, options.fix_stable_texture, options.fix_resource_override
                    )
                    if sec_changed:
                        modified = True

                    fixed_bytes = '\r\n'.join(lines).encode('utf-8')
                    if modified or (options.normalize_ini and raw_bytes != fixed_bytes):
                        bak_file = ini_path.with_name(f"{ini_path.name}.orig.bak")
                        if not bak_file.exists():
                            bak_file.write_bytes(raw_bytes)
                        ini_path.write_bytes(fixed_bytes)
                        counts["ini"] += 1
                except Exception as e:
                    log.debug(f"Error repairing ini {ini_path}: {e}")

            if counts["legacy"] > 0:
                fixes.append(f"已自动清理 {counts['legacy']} 处旧版损坏语法/异常参数行")
            if counts["hash"] > 0:
                fixes.append(f"已执行 {counts['hash']} 处版本变更 Hash 匹配与替换 (主 Hash / 贴图 Hash)")
            if counts["vg"] > 0:
                fixes.append(f"已重构 {counts['vg']} 个 Blend 缓冲文件的骨骼与顶点组映射 (修复破皮拉扯)")
            if counts["derive"] > 0:
                fixes.append(f"已自动补全 {counts['derive']} 个衍生贴图与 LOD 远景防黑材质重载")
            if counts["rule"] > 0:
                fixes.append(f"已调整 {counts['rule']} 处绘制索引与 Shapekey 规则参数")
            if counts["ini"] > 0:
                fixes.append(f"已优化并保存 {counts['ini']} 个 .ini 配置文件的编码与路径规范")
            else:
                fixes.append(f"已校验全部 {len(ini_files)} 个 .ini 文件（结构完好）")

            cls._apply_rendering_33_and_engine_ini(mod_item, options, fixes)
            if not fixes:
                fixes.append("经全面检测，模组文件结构完整且未发现异常。")
            return True, fixes
        except Exception as e:
            log.exception(f"Error during repair_mod for {mod_item.name}: {e}")
            return False, [f"修复过程发生异常: {str(e)}"]

    @classmethod
    def batch_repair_mods(
        cls,
        mod_items: List[ModItem],
        options: Optional[ModRepairOptions] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Tuple[int, int, List[str]]:
        """
        Batch repairs a collection of mods with user-selected repair options.
        Returns: (success_count, fail_count, summary_logs)
        """
        if options is None:
            options = ModRepairOptions()

        total = len(mod_items)
        success_count = 0
        fail_count = 0
        summary_logs = []

        for idx, mod in enumerate(mod_items, 1):
            if progress_callback:
                progress_callback(idx, total, mod.display_name)
            success, fixes = cls.repair_mod(mod, options=options)
            if success:
                success_count += 1
                summary_logs.append(f"✅ [{mod.display_name}]: {', '.join(fixes)}")
            else:
                fail_count += 1
                summary_logs.append(f"❌ [{mod.display_name}]: {', '.join(fixes)}")

        # Sync once after entire batch
        cls.sync_mod_state_to_game()
        return success_count, fail_count, summary_logs

    @classmethod
    def restore_mod(cls, mod_item: ModItem) -> Tuple[bool, str]:
        """
        Restores a mod back to its original pre-repair files from .orig.bak files or backup zip.
        Safely restores configuration and buffer backups without deleting unrelated mod assets.
        """
        resolved_path = cls._resolve_mod_path_for_repair(mod_item)
        if not resolved_path:
            return False, "模组目录不存在"

        restored = False
        # 1. Restore from local .orig.bak files if present (.ini and .buf)
        for bak_file in list(resolved_path.rglob('*.orig.bak')):
            target_file = bak_file.with_name(bak_file.name[:-9])
            try:
                shutil.copy2(bak_file, target_file)
                restored = True
            except Exception:
                pass

        # 2. Restore from backup_zip if present
        mods_folder = cls.get_active_mods_folder() or resolved_path.parent
        if mods_folder:
            backup_dir = mods_folder / ".mod_backups"
            safe_name = cls._safe_backup_name(mod_item.display_name)
            candidates = (backup_dir / f"{safe_name}.zip", backup_dir / f"{mod_item.display_name}.zip")
            backup_zip = next((p for p in candidates if p.exists()), None)
            if backup_zip:
                try:
                    with zipfile.ZipFile(backup_zip, 'r') as zf:
                        zf.extractall(resolved_path)
                    restored = True
                except Exception as e:
                    log.exception(f"Failed to restore from zip {backup_zip}: {e}")

        if restored:
            cls.sync_mod_state_to_game()
            return True, "已成功将模组配置文件还原至修复前的原始版本"

        return False, "未找到该模组的修复前备份记录，当前无需复原"

    @classmethod
    def delete_mod(cls, mod_item: ModItem) -> Tuple[bool, str]:
        """Deletes a mod folder."""
        try:
            if mod_item.path.is_dir():
                shutil.rmtree(mod_item.path)
            elif mod_item.path.is_file():
                mod_item.path.unlink()
            # Sync real-time state to game
            cls.sync_mod_state_to_game()
            return True, "删除成功"
        except Exception as e:
            log.exception(f"Failed to delete mod {mod_item.name}: {e}")
            return False, str(e)

    @classmethod
    def batch_toggle_all(cls, enable: bool, character_id: str = 'all') -> int:
        """Toggles all mods in the active Mods folder (or specific character) to enable or disable."""
        mods = cls.scan_mods(filter_state='disabled' if enable else 'enabled', filter_character_id=character_id, auto_resolve=False)
        count = 0
        for mod in mods:
            success, _, _, _ = cls.toggle_mod(mod, enable=enable, auto_resolve_conflicts=False)
            if success:
                count += 1
        if count > 0:
            cls.sync_mod_state_to_game()
        return count

    @classmethod
    def _extract_archive_internal(cls, src_path: Path, temp_dir: Path, password: Optional[str] = None):
        """
        Internal extractor supporting .zip, .7z, .rar, .tar, .tar.gz, .tgz, .tar.bz2, .tbz2, .tar.xz, .txz, .zst, .tar.zst.
        Raises PasswordRequiredException if encrypted and password missing/wrong.
        """
        suffix = src_path.suffix.lower()
        full_name = src_path.name.lower()

        # 1. ZIP Archive
        if suffix == '.zip':
            with zipfile.ZipFile(src_path, 'r') as zf:
                pwd_bytes = password.encode('utf-8') if password else None
                try:
                    zf.extractall(temp_dir, pwd=pwd_bytes)
                except RuntimeError as re_err:
                    err_msg = str(re_err).lower()
                    if 'password' in err_msg or 'encrypted' in err_msg or 'bad password' in err_msg:
                        raise PasswordRequiredException(str(re_err))
                    raise
                except zipfile.BadZipFile as bz_err:
                    err_msg = str(bz_err).lower()
                    if 'password' in err_msg or 'encrypted' in err_msg:
                        raise PasswordRequiredException(str(bz_err))
                    raise

        # 2. 7Z Archive
        elif suffix == '.7z':
            extracted = False
            if py7zr is not None:
                try:
                    with py7zr.SevenZipFile(src_path, mode='r', password=password) as archive:
                        archive.extractall(path=temp_dir)
                    extracted = True
                except Exception as e:
                    # In py7zr, missing or incorrect password raises PasswordRequired, LZMAError, Bad7zFile, or CRC error
                    raise PasswordRequiredException(str(e))

            if not extracted:
                # System unpacker fallback
                win_cflags = 0x08000000 if platform.system() == "Windows" else 0
                for tool in [
                    r'C:\Program Files\7-Zip\7z.exe',
                    r'C:\Program Files (x86)\7-Zip\7z.exe',
                    r'C:\Program Files\WinRAR\WinRAR.exe',
                    r'C:\Program Files (x86)\WinRAR\WinRAR.exe'
                ]:
                    if Path(tool).exists():
                        pwd_arg = f"-p{password}" if password else "-p-"
                        res = subprocess.run(
                            [tool, 'x', '-y', pwd_arg, f"-o{temp_dir}" if '7z' in tool.lower() else str(temp_dir), str(src_path)],
                            capture_output=True,
                            creationflags=win_cflags,
                            encoding="utf-8",
                            errors="ignore"
                        )
                        if res.returncode == 0:
                            extracted = True
                            break
                        elif 'password' in (res.stderr or '').lower() or 'password' in (res.stdout or '').lower() or res.returncode in (2, 3):
                            raise PasswordRequiredException("7z tool reports password required or wrong password")

            if not extracted:
                win_cflags = 0x08000000 if platform.system() == "Windows" else 0
                res = subprocess.run(
                    ['tar.exe', '-xf', str(src_path), '-C', str(temp_dir)],
                    capture_output=True,
                    creationflags=win_cflags,
                    encoding="utf-8",
                    errors="ignore"
                )
                if res.returncode != 0:
                    shutil.unpack_archive(str(src_path), str(temp_dir))

        # 3. RAR Archive
        elif suffix == '.rar':
            extracted = False
            if rarfile is not None and getattr(rarfile, 'UNRAR_TOOL', None):
                try:
                    with rarfile.RarFile(src_path) as rf:
                        rf.extractall(temp_dir, pwd=password)
                    extracted = True
                except (rarfile.PasswordRequired, rarfile.BadRarFile, Exception) as e:
                    err_str = str(e).lower()
                    if isinstance(e, rarfile.PasswordRequired) or 'password' in err_str or 'encrypted' in err_str or 'bad' in err_str:
                        raise PasswordRequiredException(str(e))
                    raise

            if not extracted:
                win_cflags = 0x08000000 if platform.system() == "Windows" else 0
                for winrar_path in [
                    r'C:\Program Files\WinRAR\WinRAR.exe',
                    r'C:\Program Files (x86)\WinRAR\WinRAR.exe',
                    r'C:\Program Files\WinRAR\UnRAR.exe',
                    r'C:\Program Files (x86)\WinRAR\UnRAR.exe'
                ]:
                    if Path(winrar_path).exists():
                        pwd_arg = f"-p{password}" if password else "-p-"
                        res = subprocess.run(
                            [winrar_path, 'x', '-ibck', '-y', pwd_arg, str(src_path), str(temp_dir)],
                            capture_output=True,
                            creationflags=win_cflags,
                            encoding="utf-8",
                            errors="ignore"
                        )
                        if res.returncode == 0:
                            extracted = True
                            break
                        elif res.returncode in (3, 11) or 'password' in (res.stderr or '').lower() or 'password' in (res.stdout or '').lower():
                            raise PasswordRequiredException("WinRAR reports password required or wrong password")

            if not extracted:
                win_cflags = 0x08000000 if platform.system() == "Windows" else 0
                res = subprocess.run(
                    ['tar.exe', '-xf', str(src_path), '-C', str(temp_dir)],
                    capture_output=True,
                    creationflags=win_cflags,
                    encoding="utf-8",
                    errors="ignore"
                )
                if res.returncode != 0:
                    shutil.unpack_archive(str(src_path), str(temp_dir))

        # 4. Zstandard Archive (.zst / .tar.zst)
        elif suffix == '.zst' or full_name.endswith('.tar.zst'):
            import zstandard
            dctx = zstandard.ZstdDecompressor()
            decompressed_tar = temp_dir / '_inner.tar'
            with open(src_path, 'rb') as ifh, open(decompressed_tar, 'wb') as ofh:
                dctx.copy_stream(ifh, ofh)
            with tarfile.open(decompressed_tar, 'r:*') as tf:
                tf.extractall(temp_dir)
            decompressed_tar.unlink(missing_ok=True)

        # 5. Standard Tarballs (.tar, .tar.gz, .tgz, .tar.bz2, .tbz2, .tar.xz, .txz, etc.)
        else:
            try:
                with tarfile.open(src_path, 'r:*') as tf:
                    tf.extractall(temp_dir)
            except Exception:
                shutil.unpack_archive(str(src_path), str(temp_dir))

    @classmethod
    def import_mod_from_path(
        cls,
        src_path: Path,
        password: Optional[str] = None,
        password_callback: Optional[Callable[[Path, str], Optional[str]]] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> Tuple[bool, str]:
        """
        Imports a mod folder or archive (.zip, .7z, .rar, .tar.gz, etc.) into the active Mods directory.
        Features:
        - Smart Password Strategy: Automatically tries default password "huihui" for encrypted archives;
          if decryption fails, calls password_callback(src_path, filename) to interactively prompt the user.
        - Structure Flattening: Automatically flattens single nested root folder.
        - Conflict Management: Automatically disables newly imported mod if character conflict exists.
        - Instant In-Game Reload: Sends F10 reload signal to running game.
        """
        mods_folder = cls.get_active_mods_folder()
        if not mods_folder:
            return False, "未找到当前游戏的 Mods 目录"

        src_path = Path(src_path)
        if not src_path.exists():
            return False, f"源路径不存在: {src_path}"

        try:
            target_dest = None

            # 1. Directory Import
            if src_path.is_dir():
                if progress_callback:
                    progress_callback(f"正在导入文件夹: {src_path.name}...", 0.3)

                dest_name = src_path.name
                dest_path = mods_folder / dest_name
                idx = 1
                while dest_path.exists():
                    dest_path = mods_folder / f"{dest_name} ({idx})"
                    idx += 1

                shutil.copytree(src_path, dest_path)
                target_dest = dest_path

            # 2. Archive Import
            elif src_path.is_file():
                suffix = src_path.suffix.lower()
                stem = src_path.stem
                valid_archive_exts = {'.zip', '.7z', '.rar', '.tar', '.gz', '.tgz', '.bz2', '.tbz2', '.xz', '.txz', '.zst'}

                is_valid = suffix in valid_archive_exts or '.tar.' in src_path.name.lower() or src_path.name.lower().endswith('.tar.zst')
                if not is_valid:
                    return False, f"不支持的文件类型: {suffix}"

                if progress_callback:
                    progress_callback(f"正在准备解压: {src_path.name}...", 0.1)

                temp_dir = mods_folder / f"_tmp_extract_{int(time.time()*1000)}"
                temp_dir.mkdir(parents=True, exist_ok=True)

                def _do_extract(pwd: Optional[str] = None):
                    # Clean temp_dir contents before extraction attempt
                    for item in temp_dir.iterdir():
                        if item.is_dir():
                            shutil.rmtree(item, ignore_errors=True)
                        else:
                            item.unlink(missing_ok=True)
                    cls._extract_archive_internal(src_path, temp_dir, password=pwd)

                try:
                    # Step A: If password is provided explicitly, try it first
                    if password:
                        if progress_callback:
                            progress_callback(f"正在使用指定密码解压: {src_path.name}...", 0.3)
                        _do_extract(password)
                    else:
                        # Step B: Try extraction without password
                        try:
                            if progress_callback:
                                progress_callback(f"正在解压压缩包: {src_path.name}...", 0.3)
                            _do_extract(None)
                        except PasswordRequiredException:
                            # Step C: Encrypted archive detected! Try default password "huihui"
                            DEFAULT_PWD = "huihui"
                            log.info(f"Archive {src_path.name} is encrypted. Trying default password '{DEFAULT_PWD}'...")
                            if progress_callback:
                                progress_callback(f"检测到加密，正在尝试默认密码 '{DEFAULT_PWD}': {src_path.name}...", 0.4)

                            try:
                                _do_extract(DEFAULT_PWD)
                                log.info(f"Successfully decrypted {src_path.name} using default password '{DEFAULT_PWD}'.")
                            except PasswordRequiredException:
                                # Step D: Default password "huihui" failed! Prompt user via password_callback
                                log.warning(f"Default password '{DEFAULT_PWD}' failed for {src_path.name}.")
                                if not password_callback:
                                    shutil.rmtree(temp_dir, ignore_errors=True)
                                    return False, f"压缩包【{src_path.name}】已加密，默认密码 '{DEFAULT_PWD}' 解压失败，请提供解压密码"

                                while True:
                                    user_pwd = password_callback(src_path, src_path.name)
                                    if user_pwd is None:
                                        shutil.rmtree(temp_dir, ignore_errors=True)
                                        return False, f"用户取消了解压密码输入，已跳过压缩包【{src_path.name}】"

                                    if progress_callback:
                                        progress_callback(f"正在使用输入的密码解压: {src_path.name}...", 0.4)

                                    try:
                                        _do_extract(user_pwd)
                                        log.info(f"Successfully decrypted {src_path.name} with user-provided password.")
                                        break
                                    except PasswordRequiredException:
                                        log.warning(f"User entered incorrect password for {src_path.name}. Prompting again...")
                                        continue
                                    except Exception as ex:
                                        shutil.rmtree(temp_dir, ignore_errors=True)
                                        return False, f"解压过程发生错误: {ex}"

                    if progress_callback:
                        progress_callback(f"正在整理模组目录与解析特征: {src_path.name}...", 0.7)

                    # Analyze extracted items
                    extracted_items = [
                        p for p in temp_dir.iterdir()
                        if p.name not in {'__MACOSX', '.DS_Store', 'desktop.ini', 'thumbs.db'}
                    ]

                    if not extracted_items:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return False, f"解压后的压缩包内容为空: {src_path.name}"

                    clean_stem = stem
                    if clean_stem.lower().endswith('.tar'):
                        clean_stem = clean_stem[:-4]

                    dest = mods_folder / clean_stem
                    idx = 1
                    while dest.exists():
                        dest = mods_folder / f"{clean_stem} ({idx})"
                        idx += 1

                    # Flatten if single nested root folder
                    if len(extracted_items) == 1 and extracted_items[0].is_dir():
                        inner_folder = extracted_items[0]
                        shutil.move(str(inner_folder), str(dest))
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    else:
                        shutil.move(str(temp_dir), str(dest))

                    target_dest = dest

                except Exception as e:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    log.exception(f"Extraction error for {src_path}: {e}")
                    return False, f"解压发生错误: {str(e)}"

            # 3. Conflict Check on Newly Imported Mod
            if target_dest and target_dest.exists():
                cid, cname, ename, guids, conflict_key = cls.analyze_mod_features(target_dest, target_dest.name)
                if conflict_key and not conflict_key.startswith('MOD_'):
                    existing_enabled = [
                        m for m in cls.scan_mods(filter_state='enabled', auto_resolve=False)
                        if m.path.resolve() != target_dest.resolve() and m.conflict_key == conflict_key
                    ]
                    # If an enabled mod already exists for this character, disable the newly imported one
                    if existing_enabled:
                        disabled_name = f"DISABLED {target_dest.name}"
                        disabled_dest = mods_folder / disabled_name
                        idx = 1
                        while disabled_dest.exists():
                            disabled_dest = mods_folder / f"DISABLED {target_dest.name} ({idx})"
                            idx += 1
                        target_dest.rename(disabled_dest)
                        target_dest = disabled_dest

            if progress_callback:
                progress_callback("导入完成！", 1.0)

            # Sync real-time state to game
            cls.sync_mod_state_to_game()
            return True, f"已成功导入模组: {target_dest.name if target_dest else '完成'}"

        except Exception as e:
            log.exception(f"Failed to import mod from {src_path}: {e}")
            return False, f"导入错误: {str(e)}"

