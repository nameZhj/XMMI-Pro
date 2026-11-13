"""
@file: src/xxmi_launcher/core/wuwa_char_translator.py
@brief: Dynamic Wuthering Waves EN-CN character/weapon mapping sync and selective mod name translator.
@exports: WuwaCharTranslator
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import datetime
import json
import logging
import os
import re
import ssl
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# Unambiguous costume/variant feature terms (applied only when a trigger feature matches)
FEATURE_PHRASES: Dict[str, str] = {
    "wedding dress": "婚纱", "bunny girl": "兔女郎", "school uniform": "校服", "maid outfit": "女仆装", "swimsuit": "泳装",
    "bikini": "比基尼", "lingerie": "内衣", "bodysuit": "连体衣", "cheongsam": "旗袍", "qipao": "旗袍", "kimono": "和服",
    "no coat": "无外套", "no jacket": "无外衣", "no hat": "无帽子", "no mask": "无面具", "no glasses": "无眼镜", "no cape": "无披风",
    "no skirt": "无裙摆", "short hair": "短发", "long hair": "长发", "high heels": "高跟鞋", "stockings": "丝袜", "pantyhose": "连裤袜",
    "barefoot": "赤足", "summer": "夏日", "maid": "女仆", "dress": "连衣裙", "outfit": "服装", "costume": "服饰", "skin": "皮肤",
    "hairstyle": "发型", "hair": "发型", "wings": "翅膀", "tail": "尾巴", "weapon": "武器", "umbrella": "雨伞", "glasses": "眼镜",
    "mask": "面具", "jacket": "外套", "coat": "外衣", "skirt": "短裙", "heels": "高跟", "armor": "装甲", "cyber": "赛博",
    "toggle": "可切换", "physics": "物理效果", "glow": "发光", "transparent": "半透明", "nude": "全果", "topless": "无上装",
}

STANDALONE_TRIGGER_TERMS = {
    "bikini", "swimsuit", "lingerie", "cheongsam", "qipao", "kimono", "wedding dress", "bunny girl", "school uniform", "maid outfit", "bodysuit",
}


class WuwaCharTranslator:
    """Fetches, caches, and applies EN-CN character/weapon & feature-based mod name translation."""

    _cache_data: Optional[Dict[str, Any]] = None
    _primary_lookup: Dict[str, str] = {}
    _phrase_lookup: Dict[str, str] = {}
    _multiword_patterns: List[Tuple[re.Pattern, str, bool]] = []

    @classmethod
    def get_cache_file_path(cls) -> Path:
        """Returns writable path for persisting synced character EN-CN tables."""
        src_path = Path(__file__).resolve().parent / "wuwa_char_names.json"
        try:
            if src_path.parent.exists() and os.access(src_path.parent, os.W_OK):
                return src_path
        except Exception:
            pass
        user_dir = Path.home() / ".xxmi_launcher"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir / "wuwa_char_names.json"

    @classmethod
    def get_name_map_data(cls) -> Dict[str, Any]:
        """Loads cached EN-CN map JSON from disk, picking the newest available copy."""
        if cls._cache_data is not None:
            return cls._cache_data
        candidates = [
            Path.home() / ".xxmi_launcher" / "wuwa_char_names.json",
            Path(__file__).resolve().parent / "wuwa_char_names.json",
            Path(getattr(sys, "_MEIPASS", "")) / "core" / "wuwa_char_names.json" if hasattr(sys, "_MEIPASS") else None,
            Path(sys.executable).parent / "core" / "wuwa_char_names.json",
            Path(sys.executable).parent / "_internal" / "core" / "wuwa_char_names.json",
        ]
        best_data: Optional[Dict[str, Any]] = None
        best_score = (-1, -1)
        for cand in candidates:
            if not cand or not cand.is_file():
                continue
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
                ver_digits = "".join(ch for ch in str(data.get("version", "")) if ch.isdigit())
                count = len(data.get("characters", {})) + len(data.get("weapons", {}))
                score = (int(ver_digits) if ver_digits else 0, count)
                if best_data is None or score > best_score:
                    best_data, best_score = data, score
            except Exception:
                continue
        cls._cache_data = best_data or {"version": "0", "characters": {}, "aliases": {}, "weapons": {}}
        cls._rebuild_lookup()
        return cls._cache_data

    @classmethod
    def _rebuild_lookup(cls) -> None:
        """Rebuilds normalized lookup tables and longest-first multiword regex patterns."""
        data = cls._cache_data or {}
        primary: Dict[str, str] = {}
        for section in ("weapons", "aliases", "characters"):
            for en_k, cn_v in data.get(section, {}).items():
                k_clean = str(en_k).strip()
                if k_clean and cn_v:
                    primary[k_clean.lower()] = str(cn_v).strip()

        phrases: Dict[str, str] = dict(primary)
        for k, v in FEATURE_PHRASES.items():
            k_low = k.lower()
            phrases.setdefault(k_low, v)
            if " " in k_low:
                collapsed = k_low.replace(" ", "")
                phrases.setdefault(collapsed, v)
                if k_low in STANDALONE_TRIGGER_TERMS:
                    phrases[collapsed] = v
        cls._primary_lookup = primary
        cls._phrase_lookup = phrases

        multi = [
            (k, v, k in primary or k in STANDALONE_TRIGGER_TERMS)
            for k, v in phrases.items()
            if any(sep in k for sep in (" ", ":", "'", "-", "_"))
        ]
        multi.sort(key=lambda item: len(item[0]), reverse=True)
        cls._multiword_patterns = [
            (re.compile(rf"(?<![a-zA-Z0-9]){re.escape(k).replace(r'\ ', '[ _-]+')}(?![a-zA-Z0-9])", re.IGNORECASE), v, is_trig)
            for k, v, is_trig in multi
        ]

    @staticmethod
    def _fetch_json(url: str, timeout: int = 8) -> Optional[Dict[str, Any]]:
        """Fetches JSON with standard TLS verification and unverified fallback for local proxies."""
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) XMMI-Pro/1.0"}
        for use_default_ssl in (True, False):
            ctx = ssl.create_default_context() if use_default_ssl else ssl._create_unverified_context()
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    if resp.status == 200:
                        return json.loads(resp.read().decode("utf-8"))
            except ssl.SSLError:
                continue
            except Exception:
                return None
        return None

    @staticmethod
    def _pair_encore_entries(zh_list: List[Dict], en_list: List[Dict], min_quality: int = 0) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Builds EN->CN dict and underscore variants from Encore API item lists."""
        en_by_id = {x.get("Id"): x.get("Name") for x in en_list if x.get("Id")}
        mapped: Dict[str, str] = {}
        rover_base: Dict[str, str] = {}
        for x in zh_list:
            if min_quality and x.get("QualityId", 0) < min_quality:
                continue
            en_n, cn_n = en_by_id.get(x.get("Id")), x.get("Name")
            if not en_n or not cn_n:
                continue
            en_s, cn_s = str(en_n), str(cn_n)
            if en_s.startswith("Rover:"):
                rover_base["Rover"] = "漂泊者"
            mapped[en_s] = cn_s
            if " " in en_s:
                mapped[en_s.replace(" ", "_")] = cn_s
        return mapped, rover_base

    @classmethod
    def update_from_remote(
        cls, force: bool = False, callback: Optional[Callable[[bool, str], None]] = None
    ) -> Tuple[bool, str, int]:
        """Dynamically pulls the latest Wuthering Waves EN-CN character and weapon mapping."""
        urls = [
            "https://api-v2.encore.moe/api/zh-Hans/character",
            "https://api-v2.encore.moe/api/en/character",
            "https://api-v2.encore.moe/api/zh-Hans/weapon",
            "https://api-v2.encore.moe/api/en/weapon",
        ]
        with ThreadPoolExecutor(max_workers=4) as pool:
            zh_c, en_c, zh_w, en_w = list(pool.map(cls._fetch_json, urls))

        curr_data = cls.get_name_map_data()
        if not zh_c or not en_c or "roleList" not in zh_c or "roleList" not in en_c:
            total = len(curr_data.get("characters", {})) + len(curr_data.get("weapons", {}))
            msg = f"角色对照表在线拉取跳过，当前使用本地缓存 ({total} 条词条)"
            if callback:
                callback(False, msg)
            return False, msg, total

        chars, rover_base = cls._pair_encore_entries(zh_c["roleList"], en_c["roleList"])
        chars.update(rover_base)
        merged_chars = {**curr_data.get("characters", {}), **chars}
        weapons = dict(curr_data.get("weapons", {}))
        if zh_w and en_w and "weapons" in zh_w and "weapons" in en_w:
            new_w, _ = cls._pair_encore_entries(zh_w["weapons"], en_w["weapons"], min_quality=4)
            weapons.update(new_w)

        updated = {
            "version": datetime.datetime.now().strftime("%Y.%m.%d"),
            "source": "https://api-v2.encore.moe/api",
            "characters": dict(sorted(merged_chars.items())),
            "aliases": curr_data.get("aliases", {}),
            "weapons": dict(sorted(weapons.items())),
        }
        total = len(updated["characters"]) + len(updated["weapons"])
        prev_total = len(curr_data.get("characters", {})) + len(curr_data.get("weapons", {}))
        if force or total > prev_total or updated["characters"] != curr_data.get("characters", {}):
            try:
                save_path = cls.get_cache_file_path()
                save_path.parent.mkdir(parents=True, exist_ok=True)
                save_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                log.warning(f"Failed to save wuwa_char_names.json: {e}")
        cls._cache_data = updated
        cls._rebuild_lookup()
        msg = f"鸣潮角色与武器中英文对照表已同步 (共 {len(merged_chars)} 个角色, {len(weapons)} 个武器映射)"
        if callback:
            callback(True, msg)
        return True, msg, total

    @classmethod
    def get_dynamic_character_entries(cls) -> List[Tuple[str, str, str]]:
        """Returns (char_id, cn_name, en_name) tuples for UI classification."""
        data = cls.get_name_map_data()
        entries: List[Tuple[str, str, str]] = []
        seen_cn: set = set()
        for en_n, cn_n in data.get("characters", {}).items():
            if ":" in en_n or "_" in en_n:
                continue
            cid = re.sub(r"[^a-z0-9]+", "_", en_n.lower()).strip("_")
            if cn_n not in seen_cn:
                seen_cn.add(cn_n)
                entries.append((cid, cn_n, en_n))
        return entries

    @classmethod
    def _try_stash(cls, key_low: str, stash_fn: Callable[[str], str]) -> Optional[Tuple[str, bool]]:
        """Returns (placeholder, is_trigger) if key_low exists in phrase lookup."""
        cn_val = cls._phrase_lookup.get(key_low)
        if not cn_val:
            return None
        return stash_fn(cn_val), (key_low in cls._primary_lookup or key_low in STANDALONE_TRIGGER_TERMS)

    @classmethod
    def _translate_camel_token(cls, word: str, stash_fn: Callable[[str], str]) -> Tuple[str, bool]:
        """Splits and selectively translates CamelCase compound identifiers."""
        parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|$)|\d+", word)
        if len(parts) <= 1 or "".join(parts) != word:
            return word, False
        out_parts: List[str] = []
        any_hit, trig, idx = False, False, 0
        while idx < len(parts):
            pair_hit = cls._try_stash(f"{parts[idx]} {parts[idx + 1]}".lower(), stash_fn) if idx + 1 < len(parts) else None
            if pair_hit:
                out_parts.append(pair_hit[0])
                any_hit, trig, idx = True, trig or pair_hit[1], idx + 2
                continue
            single_hit = cls._try_stash(parts[idx].lower(), stash_fn)
            if single_hit:
                out_parts.append(single_hit[0])
                any_hit, trig = True, trig or single_hit[1]
            else:
                out_parts.append(parts[idx])
            idx += 1
        return (" ".join(out_parts) if any_hit else word), trig

    @classmethod
    def translate_mod_name(cls, raw_name: str) -> str:
        """Translates mod name to Chinese only when recognized character/feature terms appear."""
        if not raw_name or not raw_name.strip():
            return raw_name
        cls.get_name_map_data()
        text, has_trigger = raw_name, False
        placeholders: Dict[str, str] = {}

        def _stash(cn_val: str) -> str:
            key = f"@@TR{len(placeholders)}@@"
            placeholders[key] = cn_val
            return key

        for pat, cn_val, is_trig in cls._multiword_patterns:
            if pat.search(text):
                has_trigger |= is_trig
                text = pat.sub(lambda _: _stash(cn_val), text)

        def _replace_word(match: re.Match) -> str:
            nonlocal has_trigger
            word = match.group(0)
            hit = cls._try_stash(word.lower(), _stash)
            if hit:
                has_trigger |= hit[1]
                return hit[0]
            out_w, trig = cls._translate_camel_token(word, _stash)
            has_trigger |= trig
            return out_w

        text = re.sub(r"[A-Za-z]+(?:'[A-Za-z]+)?", _replace_word, text)
        if not has_trigger or not placeholders:
            return raw_name
        text = re.sub(r"(?<=@@)_+|_+(?=@@)", " ", text)
        for k, v in placeholders.items():
            text = text.replace(k, v)
        return re.sub(r"\s{2,}", " ", text).strip()
