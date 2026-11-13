"""
@file: src/xxmi_launcher/gui/windows/mod_browser_dialogs.py
@brief: WinForms helper dialogs for multi-site login assistant and Read Frog translation config.
@exports: show_account_helper_dialog, show_readfrog_settings_dialog
"""
from __future__ import annotations

import json
import threading
import time
from typing import Callable

from core.mod_sites import ModSiteSpec
from core.readfrog_translator import ReadFrogConfig, ReadFrogTranslator


def show_account_helper_dialog(
    winforms_mod, drawing_mod, form, site: ModSiteSpec, browser_view, webview
) -> None:
    """Shows account assistant tailored to the active mod website."""
    dlg = _make_dialog(winforms_mod, drawing_mod, f"{site.short_name} 账号助手", 500, 340)

    info_text = (
        f"当前站点：{site.name}\n"
        "💡 登录 Cookie 会在本地持久化保存，关闭窗口后下次无需重登。\n"
        f"{'⚠ 该站点下载模组通常要求先登录账号。' if site.login_required else 'ℹ 受限/成人/回复可见资源需先登录对应站点账号。'}"
    )
    _add_label(winforms_mod, drawing_mod, dlg, info_text, 18, 14, 456, 62, (203, 213, 225))
    txt_user = _add_input_row(winforms_mod, drawing_mod, dlg, "用户名 / 邮箱：", 90)
    txt_pwd = _add_input_row(winforms_mod, drawing_mod, dlg, "密码：", 128, is_password=True)

    btn_fill = _make_button(winforms_mod, drawing_mod, "🚀 填入并跳转登录页", 145, 178, 162, 32, (37, 99, 235), True)
    btn_clear = _make_button(winforms_mod, drawing_mod, "🧹 清除登录缓存", 316, 178, 130, 32, (71, 85, 105), False)

    def do_fill(s, e):
        u = txt_user.Text.strip()
        p = txt_pwd.Text.strip()
        dlg.Close()
        browser_view.load_url(site.login_url)
        if u or p:
            def _inject():
                time.sleep(2.3)
                try:
                    js = f"""(function(){{
                        var u=document.querySelector('input[name="username"],input[name="login"],input[name="email"],input[name="userid"],input[type="email"]');
                        var p=document.querySelector('input[type="password"]');
                        if(u){{u.value={json.dumps(u)};u.dispatchEvent(new Event('input',{{bubbles:true}}));}}
                        if(p){{p.value={json.dumps(p)};p.dispatchEvent(new Event('input',{{bubbles:true}}));}}
                    }})();"""
                    webview.CoreWebView2.ExecuteScriptAsync(js)
                except Exception:
                    pass
            threading.Thread(target=_inject, daemon=True).start()

    def do_clear(s, e):
        try:
            webview.CoreWebView2.CookieManager.DeleteAllCookies()
            winforms_mod.MessageBox.Show(dlg, "已清除所有站点 Cookie。", "提示", winforms_mod.MessageBoxButtons.OK, winforms_mod.MessageBoxIcon.Information)
            browser_view.load_url(site.home_url)
            dlg.Close()
        except Exception as ex:
            winforms_mod.MessageBox.Show(dlg, f"清除失败: {ex}", "错误", winforms_mod.MessageBoxButtons.OK, winforms_mod.MessageBoxIcon.Error)

    btn_fill.Click += do_fill
    btn_clear.Click += do_clear
    dlg.Controls.Add(btn_fill)
    dlg.Controls.Add(btn_clear)
    _add_label(winforms_mod, drawing_mod, dlg, "⚠ 密码仅在本地自动填表，不会上传或明文存储。", 18, 228, 450, 22, (100, 116, 139), font_size=8)
    dlg.ShowDialog(form)


def show_readfrog_settings_dialog(
    winforms_mod, drawing_mod, form, cfg: ReadFrogConfig, on_apply: Callable[[ReadFrogConfig], None]
) -> None:
    """Shows Read Frog webpage translation plugin configuration dialog."""
    dlg = _make_dialog(winforms_mod, drawing_mod, "🐸 陪读蛙 (Read Frog) 网页翻译插件设置", 520, 415)
    _add_label(
        winforms_mod, drawing_mod, dlg,
        "参考 github.com/mengxi-ream/read-frog 实现：支持双语对照/仅译文切换，英文站自动启用。",
        18, 14, 476, 36, (148, 163, 184), font_size=9,
    )

    chk_enabled = winforms_mod.CheckBox()
    chk_enabled.Text = "启用 Read Frog 网页翻译插件"
    chk_enabled.Checked = cfg.enabled
    chk_enabled.Location = drawing_mod.Point(18, 56)
    chk_enabled.AutoSize = True
    chk_enabled.Font = drawing_mod.Font("Microsoft YaHei", 9)
    dlg.Controls.Add(chk_enabled)

    chk_auto = winforms_mod.CheckBox()
    chk_auto.Text = "访问英文/韩文模组站时自动开启翻译"
    chk_auto.Checked = cfg.auto_translate_foreign
    chk_auto.Location = drawing_mod.Point(240, 56)
    chk_auto.AutoSize = True
    chk_auto.Font = drawing_mod.Font("Microsoft YaHei", 9)
    dlg.Controls.Add(chk_auto)

    cmb_mode = _add_combo_row(winforms_mod, drawing_mod, dlg, "显示模式：", 94, ["双语对照 (Bilingual)", "仅译文 (Translation Only)"], 0 if cfg.mode == "bilingual" else 1)
    providers = ["microsoft", "google", "openai"]
    prov_labels = ["Microsoft Edge 免费翻译 (推荐/免代理)", "Google 网页翻译 (需外网环境)", "AI 大模型翻译 (OpenAI / DeepSeek BYOK)"]
    prov_idx = providers.index(cfg.provider) if cfg.provider in providers else 0
    cmb_prov = _add_combo_row(winforms_mod, drawing_mod, dlg, "翻译引擎：", 132, prov_labels, prov_idx)

    txt_base = _add_input_row(winforms_mod, drawing_mod, dlg, "AI Base URL：", 176, default_val=cfg.ai_base_url)
    txt_key = _add_input_row(winforms_mod, drawing_mod, dlg, "AI API Key：", 214, is_password=True, default_val=cfg.ai_api_key)
    txt_model = _add_input_row(winforms_mod, drawing_mod, dlg, "AI 模型名称：", 252, default_val=cfg.ai_model)

    btn_save = _make_button(winforms_mod, drawing_mod, "✅ 保存并立即应用", 145, 306, 155, 34, (16, 185, 129), True)
    btn_cache = _make_button(winforms_mod, drawing_mod, "🧹 清空译文缓存", 312, 306, 134, 34, (71, 85, 105), False)

    def do_save(s, e):
        next_cfg = ReadFrogConfig(
            enabled=bool(chk_enabled.Checked),
            auto_translate_foreign=bool(chk_auto.Checked),
            mode="bilingual" if cmb_mode.SelectedIndex == 0 else "translation_only",
            provider=providers[max(0, cmb_prov.SelectedIndex)],
            target_lang="zh-Hans",
            ai_base_url=txt_base.Text.strip() or "https://api.deepseek.com/v1",
            ai_api_key=txt_key.Text.strip(),
            ai_model=txt_model.Text.strip() or "deepseek-chat",
        )
        next_cfg.save()
        dlg.Close()
        on_apply(next_cfg)

    def do_clear_cache(s, e):
        ReadFrogTranslator.clear_cache()
        winforms_mod.MessageBox.Show(dlg, "已清空内存译文缓存。", "提示", winforms_mod.MessageBoxButtons.OK, winforms_mod.MessageBoxIcon.Information)

    btn_save.Click += do_save
    btn_cache.Click += do_clear_cache
    dlg.Controls.Add(btn_save)
    dlg.Controls.Add(btn_cache)
    dlg.ShowDialog(form)


def _make_dialog(winforms_mod, drawing_mod, title: str, width: int, height: int):
    dlg = winforms_mod.Form()
    dlg.Text = title
    dlg.Size = drawing_mod.Size(width, height)
    dlg.StartPosition = winforms_mod.FormStartPosition.CenterParent
    dlg.FormBorderStyle = winforms_mod.FormBorderStyle.FixedDialog
    dlg.MaximizeBox = False
    dlg.MinimizeBox = False
    dlg.BackColor = drawing_mod.Color.FromArgb(24, 30, 46)
    dlg.ForeColor = drawing_mod.Color.White
    return dlg


def _add_label(winforms_mod, drawing_mod, parent, text: str, x: int, y: int, w: int, h: int, rgb: tuple, font_size: int = 9):
    lbl = winforms_mod.Label()
    lbl.Text = text
    lbl.Font = drawing_mod.Font("Microsoft YaHei", font_size)
    lbl.ForeColor = drawing_mod.Color.FromArgb(*rgb)
    lbl.Location = drawing_mod.Point(x, y)
    lbl.Size = drawing_mod.Size(w, h)
    parent.Controls.Add(lbl)
    return lbl


def _add_input_row(winforms_mod, drawing_mod, parent, label_text: str, y: int, is_password: bool = False, default_val: str = ""):
    lbl = winforms_mod.Label()
    lbl.Text = label_text
    lbl.Font = drawing_mod.Font("Microsoft YaHei", 9)
    lbl.Location = drawing_mod.Point(18, y + 3)
    lbl.AutoSize = True
    parent.Controls.Add(lbl)

    txt = winforms_mod.TextBox()
    txt.Location = drawing_mod.Point(145, y)
    txt.Size = drawing_mod.Size(320, 24)
    txt.BackColor = drawing_mod.Color.FromArgb(13, 18, 30)
    txt.ForeColor = drawing_mod.Color.White
    txt.Font = drawing_mod.Font("Segoe UI", 9)
    txt.BorderStyle = winforms_mod.BorderStyle.FixedSingle
    txt.Text = default_val
    if is_password:
        txt.PasswordChar = "●"
    parent.Controls.Add(txt)
    return txt


def _add_combo_row(winforms_mod, drawing_mod, parent, label_text: str, y: int, items: list, selected: int):
    lbl = winforms_mod.Label()
    lbl.Text = label_text
    lbl.Font = drawing_mod.Font("Microsoft YaHei", 9)
    lbl.Location = drawing_mod.Point(18, y + 4)
    lbl.AutoSize = True
    parent.Controls.Add(lbl)

    cmb = winforms_mod.ComboBox()
    cmb.DropDownStyle = winforms_mod.ComboBoxStyle.DropDownList
    cmb.Location = drawing_mod.Point(145, y)
    cmb.Size = drawing_mod.Size(320, 26)
    cmb.BackColor = drawing_mod.Color.FromArgb(13, 18, 30)
    cmb.ForeColor = drawing_mod.Color.White
    cmb.Font = drawing_mod.Font("Microsoft YaHei", 9)
    for item in items:
        cmb.Items.Add(item)
    cmb.SelectedIndex = max(0, min(selected, len(items) - 1))
    parent.Controls.Add(cmb)
    return cmb


def _make_button(winforms_mod, drawing_mod, text: str, x: int, y: int, w: int, h: int, rgb: tuple, bold: bool):
    btn = winforms_mod.Button()
    btn.Text = text
    btn.Size = drawing_mod.Size(w, h)
    btn.Location = drawing_mod.Point(x, y)
    btn.FlatStyle = winforms_mod.FlatStyle.Flat
    btn.FlatAppearance.BorderSize = 0
    btn.BackColor = drawing_mod.Color.FromArgb(*rgb)
    btn.ForeColor = drawing_mod.Color.White
    btn.Font = drawing_mod.Font("Microsoft YaHei", 9, drawing_mod.FontStyle.Bold if bold else drawing_mod.FontStyle.Regular)
    return btn
