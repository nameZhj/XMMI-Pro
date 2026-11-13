"""
@file: src/xxmi_launcher/core/mod_sites.py
@brief: Wuthering Waves mod site catalog, login URL routing, and site-aware download JS builders.
@exports: ModSiteSpec, MOD_SITE_CATALOG, get_site_by_id, detect_site_from_url, build_login_check_js, build_site_download_js
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class ModSiteSpec:
    site_id: str
    name: str
    short_name: str
    home_url: str
    login_url: str
    login_required: bool
    lang: str
    auto_translate: bool
    domain_keywords: tuple
    description: str


MOD_SITE_CATALOG: List[ModSiteSpec] = [
    ModSiteSpec(
        site_id="gamebanana",
        name="GameBanana (香蕉网 · 鸣潮主站)",
        short_name="GameBanana",
        home_url="https://gamebanana.com/games/20357",
        login_url="https://gamebanana.com/members/account/login",
        login_required=False,
        lang="en",
        auto_translate=True,
        domain_keywords=("gamebanana.com",),
        description="全球最全鸣潮模型/材质/工具社区；常规免费直连下载，18+/受限模组需先登录。",
    ),
    ModSiteSpec(
        site_id="nexusmods",
        name="Nexus Mods (N网 · 鸣潮专区)",
        short_name="NexusMods",
        home_url="https://www.nexusmods.com/wutheringwaves/mods/",
        login_url="https://users.nexusmods.com/auth/sign_in",
        login_required=True,
        lang="en",
        auto_translate=True,
        domain_keywords=("nexusmods.com",),
        description="老牌综合模组站（优化/画质/功能补丁）；下载前必须先登录 Nexus 账号。",
    ),
    ModSiteSpec(
        site_id="nahida",
        name="Nahida.live (二游直链库)",
        short_name="Nahida.live",
        home_url="https://nahida.live/mods",
        login_url="https://nahida.live/login",
        login_required=False,
        lang="en",
        auto_translate=True,
        domain_keywords=("nahida.live",),
        description="二游角色外观分流与打包直链站；支持一键下载，加密包导入时自动提示输入密码。",
    ),
    ModSiteSpec(
        site_id="arca",
        name="Arca.live (韩网鸣潮频道)",
        short_name="Arca.live",
        home_url="https://arca.live/b/thingzyoa",
        login_url="https://arca.live/u/login",
        login_required=False,
        lang="ko",
        auto_translate=True,
        domain_keywords=("arca.live",),
        description="韩区高阶角色皮肤交流板；支持韩语双语翻译与 Base64 隐藏下载链接自动解析。",
    ),
    ModSiteSpec(
        site_id="modwu",
        name="MOD实验室 (国内二游站)",
        short_name="MOD实验室",
        home_url="https://www.modwu.com/",
        login_url="https://www.modwu.com/login",
        login_required=True,
        lang="zh",
        auto_translate=False,
        domain_keywords=("modwu.com",),
        description="中文原创二次元模组社区；部分资源需登录后解锁评论/积分附件或网盘链接。",
    ),
    ModSiteSpec(
        site_id="github",
        name="GitHub (开源模组/工具)",
        short_name="GitHub",
        home_url="https://github.com/topics/wuthering-waves-mods",
        login_url="https://github.com/login",
        login_required=False,
        lang="en",
        auto_translate=True,
        domain_keywords=("github.com",),
        description="开源修复工具、材质脚本与社区合集；支持 Releases 压缩包一键下载自动导入。",
    ),
]

_SITE_BY_ID: Dict[str, ModSiteSpec] = {s.site_id: s for s in MOD_SITE_CATALOG}


def get_site_by_id(site_id: str) -> ModSiteSpec:
    """Returns ModSiteSpec by id, defaulting to GameBanana."""
    return _SITE_BY_ID.get(site_id, MOD_SITE_CATALOG[0])


def detect_site_from_url(url: str) -> Optional[ModSiteSpec]:
    """Detects matching ModSiteSpec from a full page URL."""
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    for site in MOD_SITE_CATALOG:
        if any(kw in host for kw in site.domain_keywords):
            return site
    return None


def build_login_check_js(site: ModSiteSpec) -> str:
    """Returns JS evaluating whether current page blocks actions behind login."""
    if site.site_id == "nexusmods":
        return r"""(function(){
            var txt = (document.body && document.body.innerText || "").toLowerCase();
            if (txt.indexOf("you need to be logged in") >= 0 || txt.indexOf("log in to download") >= 0) return "NEED_LOGIN";
            var loginLink = document.querySelector("a[href*='users.nexusmods.com/auth/sign_in'], #login-button");
            var userBtn = document.querySelector("[data-testid='user-menu'], .rj-user-menu, a[href*='/users/myaccount']");
            if (loginLink && !userBtn) return "NEED_LOGIN";
            return "OK";
        })();"""
    if site.site_id == "gamebanana":
        return r"""(function(){
            var bodyTxt = (document.body && document.body.innerText || "").toLowerCase();
            if (bodyTxt.indexOf("adults only") >= 0 && bodyTxt.indexOf("log in") >= 0) return "NEED_LOGIN";
            var restricted = document.querySelector(".RestrictedNotice, #MatureContentGate");
            if (restricted && bodyTxt.indexOf("login") >= 0) return "NEED_LOGIN";
            return "OK";
        })();"""
    if site.site_id == "modwu":
        return r"""(function(){
            var hasGuest = document.querySelector("a[href*='tab-sign-in'], .signin-loader");
            var bodyTxt = (document.body && document.body.innerText || "");
            if (hasGuest && (bodyTxt.indexOf("登录后下载") >= 0 || bodyTxt.indexOf("请登录") >= 0)) return "NEED_LOGIN";
            return "OK";
        })();"""
    return r"(function(){ return 'OK'; })();"


def build_site_download_js(site: ModSiteSpec) -> str:
    """Builds DOM script to locate and trigger mod download per platform."""
    if site.site_id == "gamebanana":
        return _GB_DOWNLOAD_JS
    if site.site_id == "nexusmods":
        return _NEXUS_DOWNLOAD_JS
    if site.site_id == "arca":
        return _ARCA_DOWNLOAD_JS
    return _GENERIC_DOWNLOAD_JS


_GB_DOWNLOAD_JS = r"""(function() {
    var dl = document.querySelector("a[href*='files.gamebanana.com'], a[href*='gamebanana.com/dl/'], a[href*='gamebanana.com/mmdl/']");
    if (dl) { dl.click(); return "direct_download_clicked:" + dl.href; }
    var manualBtn = document.querySelector("a[href*='/mods/download/']");
    if (manualBtn) { window.location.href = manualBtn.href; return "navigating_to_download_page:" + manualBtn.href; }
    var btns = document.querySelectorAll("a, button");
    for (var i = 0; i < btns.length; i++) {
        var t = (btns[i].innerText || "").trim().toLowerCase();
        if (t === "download" || t === "manual download" || t === "下载") {
            btns[i].click();
            return "button_clicked:" + (btns[i].href || "button");
        }
    }
    return "no_download_button_found";
})();"""

_NEXUS_DOWNLOAD_JS = r"""(function() {
    var txt = (document.body && document.body.innerText || "").toLowerCase();
    if (txt.indexOf("you need to be logged in") >= 0 || txt.indexOf("log in to download") >= 0) return "NEED_LOGIN";
    var slow = document.querySelector("#slowDownloadButton, button[data-download-url]");
    if (slow) { slow.click(); return "nexus_slow_download_clicked"; }
    var manual = document.querySelector("a[href*='file_id='], a[data-tracking*='Manual'], .btn-download-manual");
    if (manual) { manual.click(); return "nexus_manual_clicked:" + (manual.href || ""); }
    var filesTab = document.querySelector("#mod-page-tab-files a, a[href*='tab=files']");
    if (filesTab && location.href.indexOf("tab=files") < 0) {
        filesTab.click();
        return "nexus_switched_to_files_tab";
    }
    var loginEl = document.querySelector("a[href*='users.nexusmods.com/auth/sign_in'], #login-button");
    if (loginEl) return "NEED_LOGIN";
    return "no_download_button_found";
})();"""

_ARCA_DOWNLOAD_JS = r"""(function() {
    var hosts = ["nahida.live", "kiosk.ac", "pixeldrain.com", "mega.nz", "drive.google.com", "gofile.io", "anonfiles", "gamebanana.com"];
    var links = document.querySelectorAll(".article-content a, article a, .fr-view a, a");
    for (var i = 0; i < links.length; i++) {
        var href = links[i].href || "";
        for (var h = 0; h < hosts.length; h++) {
            if (href.toLowerCase().indexOf(hosts[h]) >= 0) {
                return "resolved_external_url:" + href;
            }
        }
    }
    var content = document.querySelector(".article-content, .fr-view, article") || document.body;
    var raw = content ? (content.innerText || "") : "";
    var b64s = raw.match(/aHR0cHM6Ly9[A-Za-z0-9+/=]{8,}/g);
    if (b64s && b64s.length > 0) {
        try {
            var decoded = atob(b64s[0]);
            if (decoded.indexOf("http") === 0) return "resolved_external_url:" + decoded;
        } catch (e) {}
    }
    return "no_download_button_found";
})();"""

_GENERIC_DOWNLOAD_JS = r"""(function() {
    var dl = document.querySelector("a[download], a[href*='.zip'], a[href*='.7z'], a[href*='.rar'], a[href*='/releases/download/'], a[href*='download']");
    if (dl && dl.href && dl.href.indexOf("javascript:") < 0) {
        dl.click();
        return "direct_download_clicked:" + dl.href;
    }
    var btns = document.querySelectorAll("a, button");
    for (var i = 0; i < btns.length; i++) {
        var t = (btns[i].innerText || "").trim().toLowerCase();
        if (t === "download" || t === "download all" || t === "下载" || t === "立即下载" || t.indexOf("download zip") >= 0) {
            btns[i].click();
            return "button_clicked:" + (btns[i].href || "button");
        }
    }
    return "no_download_button_found";
})();"""
