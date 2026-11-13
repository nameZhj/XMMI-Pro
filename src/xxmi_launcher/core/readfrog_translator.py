"""
@file: src/xxmi_launcher/core/readfrog_translator.py
@brief: Read Frog inspired webpage batch translator supporting Microsoft, Google, and AI engines.
@exports: ReadFrogConfig, ReadFrogTranslator
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass
import html
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
import requests

log = logging.getLogger(__name__)

_MS_URL = "https://edge.microsoft.com/translate/translatetext"
_GOOGLE_URL = "https://translate-pa.googleapis.com/v1/translateHtml"
_GOOGLE_API_KEY = "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520"
_GOOGLE_CLIENT = "wt_lib"
_BATCH_SEP = "\n%%\n"
_CACHE_LIMIT = 4000
_MAX_BATCH_ITEMS = 20
_THINK_RE = re.compile(r"</think>([\s\S]*)")
_WUWA_GLOSSARY_HINTS = (
    "Wuthering Waves=鸣潮, WuWa=鸣潮, WWMI=鸣潮模型导入器, Toggle=可切换状态, "
    "Mesh=网格模型, Texture=贴图材质, Shader=着色器, NSFW=成人向, Endorse=点赞支持, "
    "Manual Download=手动下载, Slow Download=免费慢速下载"
)


@dataclass
class ReadFrogConfig:
    enabled: bool = True
    auto_translate_foreign: bool = True
    mode: str = "bilingual"  # "bilingual" | "translation_only"
    provider: str = "microsoft"  # "microsoft" | "google" | "openai"
    target_lang: str = "zh-Hans"
    ai_base_url: str = "https://api.deepseek.com/v1"
    ai_api_key: str = ""
    ai_model: str = "deepseek-chat"

    @classmethod
    def config_path(cls) -> Path:
        cfg_dir = Path.home() / ".xxmi_launcher"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        return cfg_dir / "readfrog_config.json"

    @classmethod
    def load(cls) -> "ReadFrogConfig":
        p = cls.config_path()
        if not p.exists():
            return cls()
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            defaults = asdict(cls())
            defaults.update({k: v for k, v in raw.items() if k in defaults})
            return cls(**defaults)
        except Exception as e:
            log.warning(f"Failed loading ReadFrogConfig: {e}")
            return cls()

    def save(self) -> None:
        try:
            self.config_path().write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning(f"Failed saving ReadFrogConfig: {e}")


class ReadFrogTranslator:
    """Batch webpage text translator modeled after mengxi-ream/read-frog."""

    _cache: "OrderedDict[str, str]" = OrderedDict()

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()

    @classmethod
    def _cache_get(cls, key: str) -> Optional[str]:
        val = cls._cache.get(key)
        if val is not None:
            cls._cache.move_to_end(key)
        return val

    @classmethod
    def _cache_put(cls, key: str, value: str) -> None:
        cls._cache[key] = value
        cls._cache.move_to_end(key)
        while len(cls._cache) > _CACHE_LIMIT:
            cls._cache.popitem(last=False)

    @classmethod
    def translate_batch(cls, texts: List[str], config: Optional[ReadFrogConfig] = None) -> List[str]:
        """Translates a list of webpage text snippets into Chinese using configured provider + cache."""
        if not texts:
            return []
        cfg = config or ReadFrogConfig.load()
        results: List[Optional[str]] = [None] * len(texts)
        miss_indices: List[int] = []
        miss_texts: List[str] = []

        for idx, raw in enumerate(texts):
            clean = (raw or "").strip()
            if not clean:
                results[idx] = raw
                continue
            cache_key = f"{cfg.provider}:{cfg.target_lang}:{clean}"
            hit = cls._cache_get(cache_key)
            if hit is not None:
                results[idx] = hit
            else:
                miss_indices.append(idx)
                miss_texts.append(clean)

        if not miss_texts:
            return [r if r is not None else t for r, t in zip(results, texts)]

        for offset in range(0, len(miss_texts), _MAX_BATCH_ITEMS):
            chunk = miss_texts[offset:offset + _MAX_BATCH_ITEMS]
            idx_chunk = miss_indices[offset:offset + _MAX_BATCH_ITEMS]
            translated_chunk = cls._dispatch_provider(chunk, cfg)
            for idx, src_text, tr_text in zip(idx_chunk, chunk, translated_chunk):
                final_tr = cls._normalize_output(src_text, tr_text)
                results[idx] = final_tr
                cls._cache_put(f"{cfg.provider}:{cfg.target_lang}:{src_text}", final_tr)

        return [r if r is not None else t for r, t in zip(results, texts)]

    @classmethod
    def _dispatch_provider(cls, texts: List[str], cfg: ReadFrogConfig) -> List[str]:
        if cfg.provider == "openai" and cfg.ai_api_key.strip():
            try:
                return cls._translate_openai_batch(texts, cfg)
            except Exception as e:
                log.warning(f"ReadFrog OpenAI fallback to Microsoft: {e}")
        if cfg.provider == "google":
            try:
                return cls._translate_google_batch(texts, cfg.target_lang)
            except Exception as e:
                log.warning(f"ReadFrog Google fallback to Microsoft: {e}")
        try:
            return cls._translate_microsoft_batch(texts, cfg.target_lang)
        except Exception as e:
            log.warning(f"ReadFrog Microsoft translate failed: {e}")
            return list(texts)

    @classmethod
    def _translate_microsoft_batch(cls, texts: List[str], to_lang: str) -> List[str]:
        resp = requests.post(
            f"{_MS_URL}?from=&to={requests.utils.quote(to_lang)}&isEnterpriseClient=false",
            json=texts,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list) or len(data) != len(texts):
            raise ValueError("Unexpected Microsoft response shape")
        out: List[str] = []
        for i, item in enumerate(data):
            trs = item.get("translations") if isinstance(item, dict) else None
            txt = trs[0].get("text") if trs and isinstance(trs[0], dict) else None
            out.append(str(txt) if txt is not None else texts[i])
        return out

    @classmethod
    def _translate_google_batch(cls, texts: List[str], to_lang: str) -> List[str]:
        escaped = [html.escape(t) for t in texts]
        resp = requests.post(
            _GOOGLE_URL,
            headers={"X-Goog-Api-Key": _GOOGLE_API_KEY, "Content-Type": "application/json+protobuf"},
            json=[[escaped, "auto", to_lang], _GOOGLE_CLIENT],
            timeout=6,
        )
        resp.raise_for_status()
        payload = resp.json()
        flat = payload[0] if isinstance(payload, list) and payload and isinstance(payload[0], list) else []
        if len(flat) != len(texts):
            raise ValueError("Unexpected Google translateHtml response length")
        return [html.unescape(str(item)) for item in flat]

    @classmethod
    def _translate_openai_batch(cls, texts: List[str], cfg: ReadFrogConfig) -> List[str]:
        endpoint = cfg.ai_base_url.rstrip("/") + "/chat/completions"
        glossary_hint = cls._build_wuwa_glossary_hint(texts)
        sys_prompt = (
            "You are a concise translator like Read Frog translating Wuthering Waves mod community pages into Simplified Chinese.\n"
            f"Terminology: {_WUWA_GLOSSARY_HINTS}{glossary_hint}\n"
            "Keep technical tags/URLs intact. When inputs contain standalone '%%' separator lines, "
            "output the EXACT same number of segments separated by standalone '%%' lines with no extra commentary."
        )
        user_content = _BATCH_SEP.join(texts)
        resp = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {cfg.ai_api_key.strip()}", "Content-Type": "application/json"},
            json={
                "model": cfg.ai_model.strip() or "deepseek-chat",
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_content},
                ],
            },
            timeout=25,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        match = _THINK_RE.search(raw)
        clean = (match.group(1) if match else raw).strip()
        if len(texts) == 1:
            return [clean]
        parts = [p.strip() for p in re.split(r"\n?\s*%%\s*\n?", clean)]
        if len(parts) != len(texts):
            raise ValueError(f"AI batch count mismatch: expected {len(texts)}, got {len(parts)}")
        return parts

    @staticmethod
    def _build_wuwa_glossary_hint(texts: List[str]) -> str:
        try:
            from core.wuwa_char_translator import WuwaCharTranslator
            joined = " ".join(texts)
            chars = WuwaCharTranslator.get_dynamic_character_entries()
            hits = [f"{en}={cn}" for en, cn in chars[:80] if en.lower() in joined.lower()]
            return (", " + ", ".join(hits[:15])) if hits else ""
        except Exception:
            return ""

    @staticmethod
    def _normalize_output(source_text: str, translated_text: str) -> str:
        out = html.unescape((translated_text or "").strip())
        return out if out else source_text
