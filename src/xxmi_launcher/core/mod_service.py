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
from typing import Optional, List, Tuple, Set, Dict, Callable

import psutil

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

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}
PREFERRED_PREVIEW_NAMES = {
    'preview', 'thumbnail', 'cover', 'screenshot', 'image', 'icon', 'main', 'mod', 'card', '0'
}

# Character Registry: (ID, CN Name, EN Name, [Pinyin], [GUIDs])
CHARACTER_DATABASE = [
    # --- 鸣潮 (WWMI) ---
    ('suisui', '穗穗', 'SuiSui', ['suisui', 'ss'], ['276291', '9300', '85755']),
    ('jinhsi', '今汐', 'Jinhsi', ['jinxi', 'jinhsi', 'jx'], ['266291']),
    ('changli', '长离', 'Changli', ['changli', 'cl'], ['266292']),
    ('camellya', '椿', 'Camellya', ['chun', 'camellya', 'c'], ['266293']),
    ('shorekeeper', '守岸人', 'Shorekeeper', ['shouanren', 'shorekeeper', 'sar'], ['266294']),
    ('yinlin', '吟霖', 'Yinlin', ['yinlin', 'yl'], ['266295']),
    ('yangyang', '秧秧', 'Yangyang', ['yangyang', 'yy'], ['266296']),
    ('verina', '维里奈', 'Verina', ['weilinai', 'verina', 'wln'], ['266297']),
    ('sanhua', '散华', 'Sanhua', ['sanhua', 'sh'], ['266298']),
    ('danjin', '丹瑾', 'Danjin', ['danjin', 'dj'], ['266299']),
    ('jianxin', '鉴心', 'Jianxin', ['jianxin', 'jx'], ['266300']),
    ('rover_f', '漂泊者女', 'Rover-F', ['piaobozhenv', 'rover', 'pbzn', 'pbz'], ['266301']),
    ('rover_m', '漂泊者男', 'Rover-M', ['piaobozhenan', 'rover', 'pbzn', 'pbz'], ['266302']),
    ('chixia', '炽霞', 'Chixia', ['chixia', 'cx'], ['266303']),
    ('jiyan', '忌炎', 'Jiyan', ['jiyan', 'jy'], ['266304']),
    ('xiangliyao', '相里要', 'Xiangli Yao', ['xiangliyao', 'xly'], ['266305']),
    ('zhezhi', '折枝', 'Zhezhi', ['zhezhi', 'zz'], ['266306']),
    ('youhu', '釉瑚', 'Youhu', ['youhu', 'yh'], ['266307']),
    ('baizhi', '白芷', 'Baizhi', ['baizhi', 'bz'], ['266308']),
    ('taoqi', '桃祈', 'Taoqi', ['taoqi', 'tq'], ['266309']),
    ('calcharo', '卡卡罗', 'Calcharo', ['kakaluo', 'calcharo', 'kkl'], ['266310']),
    ('rococo', '洛可可', 'Rococo', ['luokeke', 'rococo', 'lkk'], ['266311']),
    ('phoebe', '菲比', 'Phoebe', ['feibi', 'phoebe', 'fb'], ['266312']),
    ('brant', '布兰特', 'Brant', ['bulante', 'brant', 'blt'], ['266313']),
    ('colletta', '珂莱塔', 'Colletta', ['kelaita', 'colletta', 'klt'], ['266314']),

    # --- 原神 (GIMI) ---
    ('raiden', '雷电将军', 'Raiden Shogun', ['leidianjiangjun', 'raiden', 'leishen', 'ldjj'], []),
    ('furina', '芙宁娜', 'Furina', ['funingna', 'furina', 'shuishen', 'fnn'], []),
    ('nahida', '纳西妲', 'Nahida', ['naxida', 'nahida', 'caoshen', 'nxd'], []),
    ('hutao', '胡桃', 'Hu Tao', ['hutao', 'ht'], []),
    ('ganyu', '甘雨', 'Ganyu', ['ganyu', 'gy'], []),
    ('yelan', '夜兰', 'Yelan', ['yelan', 'yl'], []),
    ('zhongli', '钟离', 'Zhongli', ['zhongli', 'zl'], []),
    ('keqing', '刻晴', 'Keqing', ['keqing', 'kq'], []),
    ('shenhe', '申鹤', 'Shenhe', ['shenhe', 'sh'], []),
    ('yaemiko', '八重神子', 'Yae Miko', ['bachongshenzi', 'yaemiko', 'yae', 'bcsz'], []),

    # --- 星穹铁道 (SRMI) ---
    ('acheron', '黄泉', 'Acheron', ['huangquan', 'acheron', 'hq'], []),
    ('firefly', '流萤', 'Firefly', ['liuying', 'firefly', 'ly'], []),
    ('sparkle', '花火', 'Sparkle', ['huahua', 'sparkle', 'hh'], []),
    ('kafka', '卡芙卡', 'Kafka', ['kafuka', 'kafka', 'kfk'], []),
    ('fuxuan', '符玄', 'Fu Xuan', ['fuxuan', 'fx'], []),
    ('jingliu', '镜流', 'Jingliu', ['jingliu', 'jl'], []),
    ('ruanmei', '阮·梅', 'Ruan Mei', ['ruanmei', 'rm'], []),
    ('robin', '知更鸟', 'Robin', ['zhigengniao', 'robin', 'zgn'], []),

    # --- 绝区零 (ZZMI) ---
    ('janedoe', '简·杜', 'Jane Doe', ['jiandu', 'janedoe', 'jane', 'jd'], []),
    ('zhuyuan', '朱鸢', 'Zhu Yuan', ['zhuyuan', 'zy'], []),
    ('ellen', '艾莲·乔', 'Ellen Joe', ['ailian', 'ellen', 'ellenjoe', 'el'], []),
    ('qingyi', '青衣', 'Qingyi', ['qingyi', 'qy'], []),
    ('burnice', '柏妮思', 'Burnice', ['bainisi', 'burnice', 'bns'], []),
    ('yanagi', '柳', 'Yanagi', ['liu', 'yanagi', 'l'], []),
    ('miyabi', '星见雅', 'Miyabi', ['xingjianya', 'ya', 'miyabi', 'xjy'], []),
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
    fix_rover_special: bool = False       # 7. 主角材质与风主眼部专属修复 (按需开启，源码 enable_aero_rover_fix 默认为 false)
    inject_engine_ini: bool = False       # 8. Engine.ini 渲染与防破图参数注入 (修改游戏全局配置，按需开启)
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
                return cid, cname, ename, sorted_guids, f"GUID_{g}"

        # 2. Match by Character Database Keywords (CN, EN, Pinyin)
        corpus_search = (display_name + " " + " ".join(namespaces) + " " + " ".join(ini_text_corpus[:3])).lower()
        for cid, cname, ename, pinyin_list, char_guids in CHARACTER_DATABASE:
            keywords = [cname.lower(), ename.lower()] + [p.lower() for p in pinyin_list]
            for kw in keywords:
                if len(kw) >= 2 and kw in corpus_search:
                    primary_guid = char_guids[0] if char_guids else (sorted_guids[0] if sorted_guids else cid)
                    return cid, cname, ename, sorted_guids, f"CHAR_{cid}"

        # 3. Fallback: Unknown character with GUID or Generic Mod
        if sorted_guids:
            primary_guid = sorted_guids[0]
            return f"guid_{primary_guid}", f"角色 [ID: {primary_guid}]", f"Character [ID: {primary_guid}]", sorted_guids, f"GUID_{primary_guid}"
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
    def scan_mods(cls, search_query: str = '', filter_state: str = 'all', filter_character_id: str = 'all', auto_resolve: bool = True) -> List[ModItem]:
        """
        Scans the active Mods folder and returns a list of ModItem.
        If auto_resolve is True, ensures strictly 1 mod per character conflict group is enabled.
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
    def toggle_mod(cls, mod_item: ModItem, enable: Optional[bool] = None, auto_resolve_conflicts: bool = True) -> Tuple[bool, Optional[ModItem], str, List[str]]:
        """
        Toggles the enabled status of a mod by renaming its folder.
        Silently switches off any other active mod for the same character.
        Returns: (success, new_mod_item, message, list_of_auto_disabled_mod_names)
        """
        if enable is None:
            enable = not mod_item.enabled

        if enable == mod_item.enabled:
            return True, mod_item, "No change", []

        auto_disabled: List[str] = []
        # If enabling, auto-disable any other active mod for the same character
        if enable and auto_resolve_conflicts and mod_item.conflict_key and not mod_item.conflict_key.startswith('MOD_'):
            all_mods = cls.scan_mods(filter_state='enabled', auto_resolve=False)
            for other in all_mods:
                if other.path != mod_item.path and other.conflict_key == mod_item.conflict_key:
                    s, _, _, _ = cls.toggle_mod(other, enable=False, auto_resolve_conflicts=False)
                    if s:
                        auto_disabled.append(other.display_name)

        parent_dir = mod_item.path.parent
        old_name = mod_item.name
        
        if enable:
            if old_name.upper().startswith('DISABLED '):
                new_name = old_name[9:].strip()
            elif old_name.upper().startswith('DISABLED_'):
                new_name = old_name[9:].strip()
            elif old_name.lower().endswith('.disabled'):
                new_name = name[:-9].strip()
            else:
                new_name = old_name
        else:
            new_name = f"DISABLED {old_name}"

        new_path = parent_dir / new_name
        if new_path.exists() and new_path != mod_item.path:
            return False, None, f"目标文件夹已存在: {new_name}", []

        try:
            renamed = False
            for attempt in range(5):
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
            return True, new_item, "Success", auto_disabled
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
        """Loads and caches the Wuwa mod fix definitions (115+ characters/weapons)."""
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
                cfg_path = None
                for c in candidates:
                    if c and c.exists():
                        cfg_path = c
                        break

                if cfg_path and cfg_path.exists():
                    cls._fix_config_cache = json.loads(cfg_path.read_text(encoding='utf-8'))
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
            'https://ghproxy.net/https://raw.githubusercontent.com/Moonholder/Wuwa_Mod_Fixer/main/config.json',
            'https://raw.gitmirror.com/Moonholder/Wuwa_Mod_Fixer/main/config.json',
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

    @classmethod
    def has_backup(cls, mod_item: ModItem) -> bool:
        """Checks if a pre-repair backup snapshot exists for the given mod."""
        mods_folder = cls.get_active_mods_folder() or mod_item.path.parent
        if not mods_folder:
            return False
        backup_zip = mods_folder / ".mod_backups" / f"{mod_item.display_name}.zip"
        return backup_zip.exists()

    @classmethod
    def repair_mod(cls, mod_item: ModItem, options: Optional[ModRepairOptions] = None) -> Tuple[bool, List[str]]:
        r"""
        Comprehensive automated repair for Wuthering Waves (WWMI) & 3DMigoto mods,
        integrating the Wuwa_Mod_Fixer engine:
        1. Pre-repair backup snapshot creation for 1-click rollback.
        2. Clean up conflicting / temporary files (.DS_Store, Thumbs.db, CheckTexture.ini, etc.).
        3. Flatten nested single root directory.
        4. Normalize .ini encodings to UTF-8 and path separators to backslashes (\).
        5. Replace game update main hashes and texture hashes across all characters & weapons.
        6. Apply vertex group remapping (vg_remap) to fix bone deformation and mesh stretching.
        7. Auto-generate LOD and derivative texture override sections to fix zoomed-out black textures.
        8. Apply index and shapekey rules (match_first_index, match_index_count, vg_offset).
        9. Apply Rover materialmap adaptation and female aero rover eye charge fix.
        10. Apply stable state texture overrides (Aemeath, Camellya).
        11. Inject Engine.ini high-detail LOD and texture streaming variables.
        """
        fixes = []
        if not mod_item.path.exists():
            return False, ["模组目录不存在"]

        if options is None:
            options = ModRepairOptions()

        try:
            # 0. Create pre-repair backup snapshot
            mods_folder = cls.get_active_mods_folder() or mod_item.path.parent
            if options.create_backup and mods_folder:
                backup_dir = mods_folder / ".mod_backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_zip = backup_dir / f"{mod_item.display_name}.zip"
                if not backup_zip.exists():
                    try:
                        with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for file_p in mod_item.path.rglob('*'):
                                if file_p.is_file():
                                    rel_path = file_p.relative_to(mod_item.path)
                                    zf.write(file_p, rel_path)
                        fixes.append("已创建修复前原始模组安全回滚备份")
                    except Exception as e:
                        log.debug(f"Failed to create pre-repair backup snapshot: {e}")

            # 1. Clean conflicting / trash files
            if options.clean_trash_files:
                trash_names = {'checktexture.ini', 'references.ini', '.ds_store', 'thumbs.db', 'desktop.ini'}
                trash_dirs = {'__macosx'}
                for item in list(mod_item.path.rglob('*')):
                    if item.is_file() and item.name.lower() in trash_names:
                        try:
                            item.unlink()
                            fixes.append(f"已清理冗余/干扰文件: {item.name}")
                        except Exception:
                            pass
                    elif item.is_dir() and item.name.lower() in trash_dirs:
                        try:
                            shutil.rmtree(item, ignore_errors=True)
                            fixes.append(f"已清理冗余系统目录: {item.name}")
                        except Exception:
                            pass

            # 2. Check and flatten single nested root directory
            trash_filter = {'checktexture.ini', 'references.ini', '.ds_store', 'thumbs.db', 'desktop.ini', '__macosx'}
            sub_items = [p for p in mod_item.path.iterdir() if p.name.lower() not in trash_filter]
            if len(sub_items) == 1 and sub_items[0].is_dir() and sub_items[0].name.lower() not in {'textures', 'meshes', 'pinmeshes', '0'}:
                inner = sub_items[0]
                temp_swap = mod_item.path.parent / f"_tmp_swap_{int(time.time()*1000)}"
                shutil.move(str(inner), str(temp_swap))
                for inner_file in temp_swap.iterdir():
                    shutil.move(str(inner_file), str(mod_item.path))
                shutil.rmtree(temp_swap, ignore_errors=True)
                fixes.append("已自动扁平化单层嵌套子目录结构")

            # Load Wuwa Fix Database
            wuwa_cfg = cls.get_wuwa_fix_config()
            chars_db = wuwa_cfg.get('characters', {})

            ini_files = list(mod_item.path.rglob('*.ini'))
            repaired_ini_count = 0
            hash_replacements_count = 0
            vg_remaps_count = 0
            lod_derives_count = 0
            rules_applied_count = 0

            for ini_path in ini_files:
                try:
                    raw_bytes = ini_path.read_bytes()
                    text = None
                    for enc in ['utf-8-sig', 'utf-8', 'gbk', 'gb18030', 'latin-1']:
                        try:
                            text = raw_bytes.decode(enc)
                            break
                        except Exception:
                            continue
                    if text is None:
                        text = raw_bytes.decode('utf-8', errors='ignore')

                    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
                    modified = False

                    # A. Normalize paths
                    if options.normalize_ini:
                        for idx, line in enumerate(lines):
                            if re.match(r'^\s*filename\s*=', line, re.IGNORECASE):
                                new_line = line.replace('/', '\\')
                                if new_line != line:
                                    lines[idx] = new_line
                                    modified = True

                    # Detect which characters/weapons match this ini
                    full_ini_text = '\n'.join(lines)
                    matched_chars = []
                    for c_name, c_def in chars_db.items():
                        is_matched = False
                        # Check main hashes
                        for mh in c_def.get('main_hashes', []):
                            for old_h in mh.get('old', []):
                                if re.search(rf'(?i)\b{old_h}\b', full_ini_text):
                                    is_matched = True
                                    break
                            if is_matched or (mh.get('new') and re.search(rf'(?i)\b{mh["new"]}\b', full_ini_text)):
                                is_matched = True
                                break
                        # Check character name
                        if not is_matched and (c_name.lower() in ini_path.name.lower() or c_name.lower() in mod_item.name.lower()):
                            is_matched = True

                        if is_matched:
                            matched_chars.append((c_name, c_def))

                    # B. Hash & Texture Replacements
                    if options.fix_hashes:
                        for c_name, c_def in (matched_chars if matched_chars else chars_db.items()):
                            # Main hashes
                            for mh in c_def.get('main_hashes', []):
                                new_h = mh.get('new', '')
                                for old_h in mh.get('old', []):
                                    if old_h.lower() != new_h.lower():
                                        for idx, l in enumerate(lines):
                                            if re.search(rf'(?i)\b{old_h}\b', l):
                                                lines[idx] = re.sub(rf'(?i)\b{old_h}\b', new_h, l)
                                                modified = True
                                                hash_replacements_count += 1
                            # Textures
                            for new_tex, t_node in c_def.get('textures', {}).items():
                                for old_tex in t_node.get('replace', []):
                                    if old_tex.lower() != new_tex.lower():
                                        for idx, l in enumerate(lines):
                                            if re.search(rf'(?i)\b{old_tex}\b', l):
                                                lines[idx] = re.sub(rf'(?i)\b{old_tex}\b', new_tex, l)
                                                modified = True
                                                hash_replacements_count += 1

                    # C. Rules & Index Replacement (match_first_index, match_index_count, etc.)
                    if options.fix_rules:
                        for c_name, c_def in (matched_chars if matched_chars else chars_db.items()):
                            for rule in c_def.get('rules', []):
                                prefix = rule.get('line_prefix', '')
                                for rep in rule.get('replacements', []):
                                    new_val = rep.get('new', '')
                                    for old_val in rep.get('old', []):
                                        if old_val != new_val:
                                            for idx, l in enumerate(lines):
                                                if prefix.lower() in l.lower() and old_val in l:
                                                    lines[idx] = l.replace(old_val, new_val)
                                                    modified = True
                                                    rules_applied_count += 1

                    # D. Vertex Group Remapping
                    if options.fix_vertex_groups:
                        for c_name, c_def in (matched_chars if matched_chars else chars_db.items()):
                            for vg_remap in c_def.get('vg_remaps', []):
                                trigger_hashes = vg_remap.get('trigger_hash', [])
                                is_triggered = any(re.search(rf'(?i)\b{th}\b', full_ini_text) for th in trigger_hashes) if trigger_hashes else (c_name in [mc[0] for mc in matched_chars])
                                if is_triggered and vg_remap.get('vertex_groups'):
                                    vg_str = vg_remap['vertex_groups']
                                    # Update or append vertex group remap instruction
                                    has_vg_line = False
                                    for idx, l in enumerate(lines):
                                        if 'vg_remap' in l.lower() or 'vertex_groups' in l.lower():
                                            lines[idx] = f"$\\WWMIv1\\vg_remap = {vg_str}"
                                            has_vg_line = True
                                            modified = True
                                            vg_remaps_count += 1
                                            break
                                    if not has_vg_line and '$\\WWMIv1\\' in full_ini_text:
                                        lines.append(f"\n; [Auto-generated Vertex Group Remap for {c_name}]\n$\\WWMIv1\\vg_remap = {vg_str}\n")
                                        modified = True
                                        vg_remaps_count += 1

                    # E. Derive / LOD Texture Overrides
                    if options.fix_derive_textures:
                        cur_text = '\n'.join(lines)
                        for c_name, c_def in (matched_chars if matched_chars else chars_db.items()):
                            for tex_hash, t_node in c_def.get('textures', {}).items():
                                derives = t_node.get('derive', {})
                                if not derives:
                                    continue
                                # If this base texture hash is overridden in this ini
                                if re.search(rf'(?i)\b{tex_hash}\b', cur_text):
                                    for dtype, dlist in derives.items():
                                        for dhash in dlist:
                                            # If derived hash is not yet present
                                            if not re.search(rf'(?i)\b{dhash}\b', cur_text):
                                                lines.append(f"\n; [Auto-generated {dtype} Texture Override for {c_name}]\n[TextureOverride_{c_name}_{dtype}_{dhash}]\nhash = {dhash}\nCheckTextureOverride = 0\n")
                                                modified = True
                                                lod_derives_count += 1
                                                cur_text = '\n'.join(lines)

                    # F. Rover & Special Character Fixes
                    if options.fix_rover_special:
                        for c_name, c_def in matched_chars:
                            if c_name in ['RoverFemale', 'RoverMale']:
                                rover_mat_maps = {'RoverFemale': {'3': 'f813702e', '4': 'e40b43c4'}, 'RoverMale': {'2': 'faf5e483'}}
                                for comp_id, mat_hash in rover_mat_maps.get(c_name, {}).items():
                                    if f"component = {comp_id}" in cur_text.lower() and mat_hash not in cur_text:
                                        lines.append(f"\n; [Auto-generated Rover Materialmap Override for Component {comp_id}]\n[TextureOverride_Rover_Material_{comp_id}]\nhash = {mat_hash}\nCheckTextureOverride = 0\n")
                                        modified = True
                                        cur_text = '\n'.join(lines)

                    # G. State Texture Stabilization & Skip Components (Aemeath/Shorekeeper/Changli etc.)
                    if options.fix_stable_texture:
                        for c_name, c_def in matched_chars:
                            skip_comps = c_def.get('skip_components', [])
                            for sc in skip_comps:
                                sc_pattern = rf'(?i)component\s*=\s*{sc}\b'
                                for idx, l in enumerate(lines):
                                    if re.search(sc_pattern, l):
                                        # Ensure handling = skip is applied to this component section
                                        sec_start = idx
                                        while sec_start >= 0 and not lines[sec_start].strip().startswith('['):
                                            sec_start -= 1
                                        sec_end = idx
                                        while sec_end < len(lines) and not (sec_end > idx and lines[sec_end].strip().startswith('[')):
                                            sec_end += 1
                                        sec_block = '\n'.join(lines[sec_start:sec_end])
                                        if 'handling = skip' not in sec_block.lower():
                                            lines.insert(idx + 1, 'handling = skip')
                                            modified = True
                                            break

                    # H. Texture Override Check (CheckTextureOverride)
                    if options.fix_resource_override:
                        in_override_sec = False
                        has_check = False
                        sec_idx = -1
                        for idx, l in enumerate(lines):
                            stripped = l.strip()
                            if stripped.startswith('[') and stripped.endswith(']'):
                                if in_override_sec and not has_check and sec_idx >= 0:
                                    lines.insert(sec_idx + 1, 'CheckTextureOverride = 0')
                                    modified = True
                                in_override_sec = 'textureoverride' in stripped.lower()
                                has_check = False
                                sec_idx = idx
                            elif in_override_sec:
                                if 'checktextureoverride' in stripped.lower():
                                    has_check = True
                        if in_override_sec and not has_check and sec_idx >= 0:
                            lines.append('CheckTextureOverride = 0')
                            modified = True

                    # Save updated content
                    fixed_content = '\r\n'.join(lines)
                    if modified or (options.normalize_ini and raw_bytes != fixed_content.encode('utf-8')):
                        ini_path.write_bytes(fixed_content.encode('utf-8'))
                        repaired_ini_count += 1
                except Exception as e:
                    log.debug(f"Error repairing ini {ini_path}: {e}")

            # Summary messages
            if hash_replacements_count > 0:
                fixes.append(f"已执行 {hash_replacements_count} 处版本变更 Hash 匹配与替换 (主 Hash / 贴图 Hash)")
            if vg_remaps_count > 0:
                fixes.append(f"已应用 {vg_remaps_count} 处骨骼与顶点组重映射 (修复破皮拉扯)")
            if lod_derives_count > 0:
                fixes.append(f"已自动补全 {lod_derives_count} 个衍生贴图与 LOD 远景防黑材质重载")
            if rules_applied_count > 0:
                fixes.append(f"已调整 {rules_applied_count} 处绘制索引与 Shapekey 规则参数")
            if repaired_ini_count > 0:
                fixes.append(f"已优化并保存 {repaired_ini_count} 个 .ini 配置文件的编码与路径规范")
            else:
                fixes.append(f"已校验全部 {len(ini_files)} 个 .ini 文件（结构完好）")

            # 4. Engine.ini optimization injection for Wuthering Waves
            if options.inject_engine_ini:
                try:
                    launcher_cfg = getattr(Config, 'Launcher', None)
                    active_importer = getattr(launcher_cfg, 'active_importer', None) if launcher_cfg else None
                    importers_obj = getattr(Config, 'Importers', None)
                    if active_importer and importers_obj:
                        importer_package = getattr(importers_obj, active_importer, None)
                        if importer_package is None and hasattr(importers_obj, '__dict__'):
                            importer_package = importers_obj.__dict__.get(active_importer, None)
                        if importer_package:
                            importer_cfg = getattr(importer_package, 'Importer', None)
                            game_folder = getattr(importer_cfg, 'game_folder', None) if importer_cfg else None
                            if game_folder:
                                engine_ini = Path(game_folder) / "Client" / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini"
                                if not engine_ini.exists():
                                    engine_ini = Path(game_folder) / "Saved" / "Config" / "WindowsNoEditor" / "Engine.ini"

                                if engine_ini.exists() and engine_ini.is_file():
                                    e_text = engine_ini.read_text(encoding='utf-8', errors='ignore')
                                    opt_vars = [
                                        "r.Kuro.SkeletalMesh.LODDistanceScale=25",
                                        "r.Streaming.FullyLoadUsedTextures=1",
                                        "r.Streaming.HiddenPrimitiveScale=25",
                                        "r.Streaming.UseAllMips=1"
                                    ]
                                    missing_vars = [v for v in opt_vars if v.split('=')[0].strip() not in e_text]
                                    if missing_vars:
                                        if "[ConsoleVariables]" not in e_text:
                                            e_text += "\n\n[ConsoleVariables]\n"
                                        for mv in missing_vars:
                                            e_text += f"{mv}\n"
                                        engine_ini.write_text(e_text, encoding='utf-8')
                                        fixes.append(f"已向游戏 Engine.ini 写入高精模型渲染与防破图参数 ({len(missing_vars)} 项)")
                                    else:
                                        fixes.append("游戏 Engine.ini 渲染与防破图参数已是最佳配置")
                except Exception as e:
                    log.debug(f"Failed to patch Engine.ini: {e}")

            if not fixes:
                fixes.append("经全面检测，模组文件结构完整且未发现异常。")

            # Sync real-time state to game
            cls.sync_mod_state_to_game()
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
        Restores a mod back to its original pre-repair files from the backup snapshot.
        """
        mods_folder = cls.get_active_mods_folder() or mod_item.path.parent
        if not mods_folder:
            return False, "未找到当前游戏的 Mods 目录"

        backup_zip = mods_folder / ".mod_backups" / f"{mod_item.display_name}.zip"
        if not backup_zip.exists():
            return False, "未找到该模组的修复前备份记录，当前无需复原"

        if not mod_item.path.exists():
            return False, "模组目录不存在"

        try:
            temp_dir = mods_folder / f"_tmp_restore_{int(time.time()*1000)}"
            temp_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(backup_zip, 'r') as zf:
                zf.extractall(temp_dir)

            # Clear current files inside mod folder
            for p in list(mod_item.path.iterdir()):
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                elif p.is_file():
                    try:
                        p.unlink()
                    except Exception:
                        pass

            # Move restored files into mod folder
            for p in list(temp_dir.iterdir()):
                shutil.move(str(p), str(mod_item.path))

            shutil.rmtree(temp_dir, ignore_errors=True)
            # Sync real-time state to game
            cls.sync_mod_state_to_game()
            return True, "已成功将模组还原至修复前的原始文件"
        except Exception as e:
            log.exception(f"Failed to restore mod {mod_item.name}: {e}")
            return False, f"复原失败: {str(e)}"

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
    def import_mod_from_path(cls, src_path: Path, progress_callback: Optional[Callable[[str, float], None]] = None) -> Tuple[bool, str]:
        """
        Imports a mod folder or archive (.zip, .7z, .rar, etc.) into the active Mods directory.
        Properly unpacks archives and flattens nested single root folders.
        Automatically checks for conflict and disables the new mod if another mod of the same character is already enabled.
        """
        mods_folder = cls.get_active_mods_folder()
        if not mods_folder:
            return False, "未找到当前游戏的 Mods 目录"

        if not src_path.exists():
            return False, f"源路径不存在: {src_path}"

        try:
            target_dest = None

            # 1. If it's a directory, copy directly
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

            # 2. If it's an archive (.zip, .7z, .rar, etc.)
            elif src_path.is_file():
                suffix = src_path.suffix.lower()
                stem = src_path.stem
                valid_archive_exts = {'.zip', '.7z', '.rar', '.tar', '.gz', '.tgz', '.bz2', '.xz'}

                if suffix not in valid_archive_exts:
                    return False, f"不支持的文件类型: {suffix}"

                if progress_callback:
                    progress_callback(f"正在准备解压: {src_path.name}...", 0.1)

                temp_dir = mods_folder / f"_tmp_extract_{int(time.time()*1000)}"
                temp_dir.mkdir(parents=True, exist_ok=True)

                try:
                    # A. ZIP files
                    if suffix == '.zip':
                        if progress_callback:
                            progress_callback("正在解压 ZIP 压缩包...", 0.3)
                        with zipfile.ZipFile(src_path, 'r') as zf:
                            zf.extractall(temp_dir)

                    # B. 7Z files
                    elif suffix == '.7z':
                        if progress_callback:
                            progress_callback("正在解压 7Z 压缩包...", 0.3)
                        extracted = False
                        if py7zr is not None:
                            try:
                                with py7zr.SevenZipFile(src_path, mode='r') as archive:
                                    archive.extractall(path=temp_dir)
                                extracted = True
                            except Exception as e:
                                log.debug(f"py7zr extraction fallback: {e}")

                        if not extracted:
                            res = subprocess.run(
                                ['tar.exe', '-xf', str(src_path), '-C', str(temp_dir)],
                                capture_output=True
                            )
                            if res.returncode != 0:
                                shutil.unpack_archive(str(src_path), str(temp_dir))

                    # C. RAR files
                    elif suffix == '.rar':
                        if progress_callback:
                            progress_callback("正在解压 RAR 压缩包...", 0.3)
                        extracted = False
                        if rarfile is not None and getattr(rarfile, 'UNRAR_TOOL', None):
                            try:
                                with rarfile.RarFile(src_path) as rf:
                                    rf.extractall(temp_dir)
                                extracted = True
                            except Exception as e:
                                log.debug(f"rarfile extraction fallback: {e}")

                        if not extracted:
                            for winrar_path in [
                                r'C:\Program Files\WinRAR\WinRAR.exe',
                                r'C:\Program Files (x86)\WinRAR\WinRAR.exe',
                                r'C:\Program Files\WinRAR\UnRAR.exe'
                            ]:
                                if Path(winrar_path).exists():
                                    res = subprocess.run([winrar_path, 'x', '-ibck', '-y', str(src_path), str(temp_dir)])
                                    if res.returncode == 0:
                                        extracted = True
                                        break

                        if not extracted:
                            res = subprocess.run(['tar.exe', '-xf', str(src_path), '-C', str(temp_dir)], capture_output=True)
                            if res.returncode != 0:
                                shutil.unpack_archive(str(src_path), str(temp_dir))

                    # D. TAR / GZ / Other archives
                    else:
                        if progress_callback:
                            progress_callback("正在解压压缩文件...", 0.3)
                        try:
                            with tarfile.open(src_path, 'r:*') as tf:
                                tf.extractall(temp_dir)
                        except Exception:
                            shutil.unpack_archive(str(src_path), str(temp_dir))

                    if progress_callback:
                        progress_callback("正在整理模组目录与解析特征...", 0.7)

                    # Analyze extracted items
                    extracted_items = [
                        p for p in temp_dir.iterdir()
                        if p.name not in {'__MACOSX', '.DS_Store', 'desktop.ini', 'thumbs.db'}
                    ]

                    if not extracted_items:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        return False, "解压后的压缩包内容为空"

                    dest = mods_folder / stem
                    idx = 1
                    while dest.exists():
                        dest = mods_folder / f"{stem} ({idx})"
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
