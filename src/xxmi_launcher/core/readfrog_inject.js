(function () {
  if (window.__ReadFrog) return;

  var DONT_WALK_TAGS = new Set([
    "HEAD", "TITLE", "HR", "INPUT", "TEXTAREA", "IMG", "VIDEO", "AUDIO", "CANVAS",
    "SOURCE", "TRACK", "META", "SCRIPT", "NOSCRIPT", "STYLE", "LINK", "PRE", "CODE", "SVG", "MATH"
  ]);
  var INLINE_TAGS = new Set(["A", "BUTTON", "SELECT", "OPTION", "SPAN", "LABEL", "STRONG", "EM", "B", "I"]);
  var BLOCK_SELECTOR = "h1,h2,h3,h4,h5,h6,p,li,blockquote,td,th,dt,dd,figcaption,summary,a,button,span,div";
  var STYLE_ID = "read-frog-injected-style";

  var state = {
    enabled: false,
    mode: "bilingual", // "bilingual" | "translation_only"
    reqSeq: 1,
    pending: {},       // reqId -> Array<{el, origText, isInline}>
    queue: [],
    flushTimer: null,
    scanTimer: null,
    observer: null
  };

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = [
      ".read-frog-translated-content-wrapper{font-family:'Microsoft YaHei','PingFang SC','Segoe UI',sans-serif;overflow-wrap:anywhere;word-break:normal;}",
      ".read-frog-translated-block-content{display:block;margin:4px 0 6px 0 !important;padding:2px 0 2px 8px;border-left:3px solid #10b981;opacity:0.92;font-size:0.94em;line-height:1.45;color:inherit;}",
      ".read-frog-translated-inline-content{display:inline;opacity:0.88;font-size:0.92em;color:#34d399;font-weight:normal;}",
      "#rf-floating-badge{position:fixed;right:14px;bottom:14px;z-index:2147483647;display:none;align-items:center;gap:6px;background:rgba(15,23,42,0.92);color:#e2e8f0;border:1px solid #10b981;border-radius:999px;padding:5px 12px;font:12px 'Microsoft YaHei',sans-serif;box-shadow:0 4px 14px rgba(0,0,0,0.35);cursor:pointer;user-select:none;}",
      "#rf-floating-badge:hover{background:rgba(16,185,129,0.22);color:#fff;}"
    ].join("");
    (document.head || document.documentElement).appendChild(style);
  }

  function ensureBadge() {
    var badge = document.getElementById("rf-floating-badge");
    if (!badge && document.body) {
      badge = document.createElement("div");
      badge.id = "rf-floating-badge";
      badge.className = "notranslate";
      badge.setAttribute("data-rf-skip", "1");
      badge.onclick = function () {
        if (!state.enabled) {
          api.enable(state.mode);
        } else if (state.mode === "bilingual") {
          api.setMode("translation_only");
        } else {
          api.disable();
        }
        notifyHostState();
      };
      document.body.appendChild(badge);
    }
    if (badge) {
      badge.style.display = "inline-flex";
      badge.textContent = !state.enabled ? "🐸 陪读蛙: 原文" : (state.mode === "bilingual" ? "🐸 双语对照" : "🐸 仅译文");
    }
  }

  function notifyHostState() {
    try {
      if (window.chrome && window.chrome.webview) {
        window.chrome.webview.postMessage(JSON.stringify({
          type: "rf_state_changed",
          enabled: state.enabled,
          mode: state.mode
        }));
      }
    } catch (e) {}
  }

  function shouldTranslateText(text) {
    if (!text) return false;
    var t = text.replace(/\s+/g, " ").trim();
    if (t.length < 2 || t.length > 900) return false;
    if (/^[\d\W_]+$/.test(t)) return false;
    var zhMatches = t.match(/[\u4e00-\u9fff]/g);
    var zhCount = zhMatches ? zhMatches.length : 0;
    if (zhCount >= 2 && zhCount / t.length > 0.32) return false;
    return /[A-Za-z\uac00-\ud7af\u3040-\u30ff]/.test(t);
  }

  function isSkippedNode(el) {
    if (!el || el.nodeType !== 1) return true;
    if (DONT_WALK_TAGS.has(el.tagName)) return true;
    if (el.isContentEditable) return true;
    if (el.closest(".notranslate, .read-frog-translated-content-wrapper, [data-rf-skip='1'], pre, code, svg")) return true;
    var cs = window.getComputedStyle(el);
    if (!cs || cs.display === "none" || cs.visibility === "hidden") return true;
    return false;
  }

  function hasDirectTextContent(el) {
    if (el.tagName === "P" || /^H[1-6]$/.test(el.tagName) || el.tagName === "LI" || el.tagName === "BLOCKQUOTE") {
      return (el.innerText || "").trim().length > 0 && !el.querySelector("p, h1, h2, h3, h4, h5, h6, ul, ol");
    }
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3 && n.textContent && n.textContent.trim().length > 1) return true;
    }
    return false;
  }

  function collectCandidates() {
    if (!state.enabled || !document.body) return;
    var nodes = document.body.querySelectorAll(BLOCK_SELECTOR);
    var vh = window.innerHeight || 900;
    var prioritized = [];
    var deferred = [];

    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (el.getAttribute("data-rf-walked") === "1" || isSkippedNode(el)) continue;
      if (!hasDirectTextContent(el)) continue;
      var text = (el.innerText || "").replace(/\s+/g, " ").trim();
      if (!shouldTranslateText(text)) continue;

      el.setAttribute("data-rf-walked", "1");
      var rect = el.getBoundingClientRect();
      var item = {
        el: el,
        text: text,
        isInline: INLINE_TAGS.has(el.tagName) || (rect.height > 0 && rect.height <= 30 && rect.width < 320)
      };
      if (rect.top >= -200 && rect.top <= vh * 1.8) {
        prioritized.push(item);
      } else {
        deferred.push(item);
      }
    }

    state.queue.push.apply(state.queue, prioritized);
    if (deferred.length > 0) {
      state.queue.push.apply(state.queue, deferred.slice(0, 80));
    }
    scheduleFlush();
  }

  function scheduleFlush() {
    if (state.flushTimer || state.queue.length === 0) return;
    state.flushTimer = setTimeout(flushBatch, 90);
  }

  function flushBatch() {
    state.flushTimer = null;
    if (!state.enabled || state.queue.length === 0) return;
    var batch = state.queue.splice(0, 18);
    var reqId = String(state.reqSeq++);
    state.pending[reqId] = batch;
    var payload = {
      type: "rf_translate_batch",
      reqId: reqId,
      items: batch.map(function (b) { return b.text; })
    };
    try {
      if (window.chrome && window.chrome.webview) {
        window.chrome.webview.postMessage(JSON.stringify(payload));
      }
    } catch (e) {
      delete state.pending[reqId];
    }
    if (state.queue.length > 0) scheduleFlush();
  }

  function applyTranslation(item, translatedText) {
    var el = item.el;
    if (!el || !el.isConnected || !state.enabled) return;
    if (!translatedText || translatedText.trim() === item.text.trim()) return;

    removeElementTranslation(el, false);
    if (state.mode === "translation_only") {
      if (el.getAttribute("data-rf-orig-html") === null) {
        el.setAttribute("data-rf-orig-html", el.innerHTML);
      }
      el.setAttribute("data-rf-swapped", "1");
      el.textContent = translatedText;
      return;
    }

    var wrap = document.createElement("span");
    wrap.className = "read-frog-translated-content-wrapper notranslate";
    wrap.setAttribute("lang", "zh-Hans");

    var inner = document.createElement("span");
    if (item.isInline) {
      inner.className = "read-frog-translated-inline-content notranslate";
      inner.textContent = " (" + translatedText + ")";
    } else {
      inner.className = "read-frog-translated-block-content notranslate";
      inner.textContent = translatedText;
    }
    wrap.appendChild(inner);
    el.appendChild(wrap);
  }

  function removeElementTranslation(el, clearWalked) {
    if (el.getAttribute("data-rf-swapped") === "1") {
      var orig = el.getAttribute("data-rf-orig-html");
      if (orig !== null) el.innerHTML = orig;
      el.removeAttribute("data-rf-swapped");
    }
    var wraps = el.querySelectorAll(":scope > .read-frog-translated-content-wrapper");
    for (var i = 0; i < wraps.length; i++) wraps[i].remove();
    if (clearWalked) el.removeAttribute("data-rf-walked");
  }

  function clearAllTranslations() {
    var wrappers = document.querySelectorAll(".read-frog-translated-content-wrapper");
    for (var i = 0; i < wrappers.length; i++) wrappers[i].remove();
    var swapped = document.querySelectorAll("[data-rf-swapped='1']");
    for (var j = 0; j < swapped.length; j++) {
      var orig = swapped[j].getAttribute("data-rf-orig-html");
      if (orig !== null) swapped[j].innerHTML = orig;
      swapped[j].removeAttribute("data-rf-swapped");
    }
    var walked = document.querySelectorAll("[data-rf-walked]");
    for (var k = 0; k < walked.length; k++) walked[k].removeAttribute("data-rf-walked");
    state.queue = [];
    state.pending = {};
  }

  function startObservers() {
    if (state.observer || !document.body) return;
    state.observer = new MutationObserver(function (mutations) {
      if (!state.enabled) return;
      for (var i = 0; i < mutations.length; i++) {
        var tgt = mutations[i].target;
        if (tgt && tgt.closest && tgt.closest(".read-frog-translated-content-wrapper")) continue;
        if (!state.scanTimer) {
          state.scanTimer = setTimeout(function () {
            state.scanTimer = null;
            collectCandidates();
          }, 350);
        }
        break;
      }
    });
    state.observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("scroll", function () {
      if (!state.enabled || state.scanTimer) return;
      state.scanTimer = setTimeout(function () {
        state.scanTimer = null;
        collectCandidates();
      }, 280);
    }, { passive: true });
  }

  var api = {
    enable: function (mode) {
      injectStyles();
      state.mode = mode || state.mode || "bilingual";
      state.enabled = true;
      ensureBadge();
      startObservers();
      collectCandidates();
    },
    disable: function () {
      state.enabled = false;
      clearAllTranslations();
      ensureBadge();
    },
    setMode: function (mode) {
      var nextMode = mode || "bilingual";
      if (state.mode !== nextMode) {
        clearAllTranslations();
      }
      state.mode = nextMode;
      if (state.enabled) {
        injectStyles();
        ensureBadge();
        startObservers();
        collectCandidates();
      } else {
        ensureBadge();
      }
    },
    receiveBatch: function (reqId, translations) {
      var batch = state.pending[reqId];
      delete state.pending[reqId];
      if (!batch || !Array.isArray(translations)) return;
      for (var i = 0; i < batch.length; i++) {
        if (i < translations.length) {
          applyTranslation(batch[i], translations[i]);
        }
      }
    }
  };

  window.__ReadFrog = api;
})();
