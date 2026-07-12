"""PWA (Progressive Web App) head injection for Equi-AI / 智马."""

from __future__ import annotations

import streamlit as st

PWA_THEME_COLOR = "#0a1628"
PWA_BG_COLOR = "#0a1628"
PWA_MANIFEST = "/app/static/pwa/manifest.webmanifest"
PWA_SW = "/app/static/sw.js"
PWA_ICON_192 = "/app/static/pwa/icon-192.png"
PWA_APPLE_ICON = "/app/static/pwa/apple-touch-icon.png"


def inject_pwa_head() -> None:
    """Inject manifest, icons, iOS/Android meta tags, and service worker registration."""
    if st.session_state.get("_pwa_head_injected"):
        return
    st.session_state["_pwa_head_injected"] = True

    st.markdown(
        f"""
<script>
(function () {{
  if (window.__equiAiPwaReady) return;
  window.__equiAiPwaReady = true;
  var head = document.head || document.getElementsByTagName("head")[0];
  var tags = [
    ["link", {{ rel: "manifest", href: "{PWA_MANIFEST}" }}],
    ["link", {{ rel: "icon", type: "image/png", sizes: "192x192", href: "{PWA_ICON_192}" }}],
    ["link", {{ rel: "apple-touch-icon", sizes: "180x180", href: "{PWA_APPLE_ICON}" }}],
    ["meta", {{ name: "viewport", content: "width=device-width, initial-scale=1, viewport-fit=cover" }}],
    ["meta", {{ name: "theme-color", content: "{PWA_THEME_COLOR}" }}],
    ["meta", {{ name: "mobile-web-app-capable", content: "yes" }}],
    ["meta", {{ name: "apple-mobile-web-app-capable", content: "yes" }}],
    ["meta", {{ name: "apple-mobile-web-app-status-bar-style", content: "black-translucent" }}],
    ["meta", {{ name: "apple-mobile-web-app-title", content: "智马" }}],
    ["meta", {{ name: "application-name", content: "Equi-AI" }}],
    ["meta", {{ name: "msapplication-TileColor", content: "{PWA_THEME_COLOR}" }}],
    ["meta", {{ name: "msapplication-TileImage", content: "{PWA_ICON_192}" }}],
  ];
  tags.forEach(function (pair) {{
    var el = document.createElement(pair[0]);
    Object.keys(pair[1]).forEach(function (key) {{
      el.setAttribute(key, pair[1][key]);
    }});
    head.appendChild(el);
  }});
  document.documentElement.style.backgroundColor = "{PWA_BG_COLOR}";
  if ("serviceWorker" in navigator) {{
    window.addEventListener("load", function () {{
      navigator.serviceWorker.register("{PWA_SW}", {{ scope: "/" }}).catch(function () {{
        navigator.serviceWorker.register("{PWA_SW}").catch(function () {{}});
      }});
    }});
  }}
}})();
</script>
""",
        unsafe_allow_html=True,
    )


def render_pwa_install_hint(lang: str = "zh") -> None:
    """Mobile hint for Add to Home Screen (iOS Safari / Android Chrome)."""
    title = "添加到主屏幕 · 智马" if lang == "zh" else "Add to Home Screen · Equi-AI"
    ios_body = (
        "Safari：点底部分享按钮 →「添加到主屏幕」，即可像 App 一样打开。"
        if lang == "zh"
        else "Safari: tap Share → Add to Home Screen for an app-like icon."
    )
    android_body = (
        "Chrome：点右上角菜单 →「添加到主屏幕」或「安装应用」。"
        if lang == "zh"
        else "Chrome: Menu → Add to Home screen / Install app."
    )
    close_label = "知道了" if lang == "zh" else "Got it"

    st.markdown(
        f"""
<div id="equi-pwa-hint" style="display:none;position:fixed;bottom:16px;left:12px;right:12px;z-index:999999;
  background:linear-gradient(135deg,#0a1628 0%,#1a2744 100%);color:#e8f4ff;
  border:1px solid rgba(0,229,255,0.35);border-radius:14px;padding:12px 14px;
  font-size:14px;line-height:1.45;box-shadow:0 8px 32px rgba(0,0,0,0.35);">
  <div style="font-weight:700;margin-bottom:4px;">{title}</div>
  <div id="equi-pwa-hint-body"></div>
  <button id="equi-pwa-hint-close" style="margin-top:10px;background:rgba(0,229,255,0.15);color:#00e5ff;
    border:1px solid rgba(0,229,255,0.4);border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px;">
    {close_label}
  </button>
</div>
<script>
(function () {{
  if (window.matchMedia("(display-mode: standalone)").matches) return;
  if (window.navigator.standalone === true) return;
  try {{ if (localStorage.getItem("equi_pwa_hint_dismissed")) return; }} catch (e) {{}}
  var ua = navigator.userAgent || "";
  var isIOS = /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var isAndroid = /Android/i.test(ua);
  if (!isIOS && !isAndroid) return;
  var box = document.getElementById("equi-pwa-hint");
  if (!box) return;
  document.getElementById("equi-pwa-hint-body").textContent = isIOS
    ? {ios_body!r}
    : {android_body!r};
  box.style.display = "block";
  document.getElementById("equi-pwa-hint-close").onclick = function () {{
    box.style.display = "none";
    try {{ localStorage.setItem("equi_pwa_hint_dismissed", "1"); }} catch (e) {{}}
  }};
}})();
</script>
""",
        unsafe_allow_html=True,
    )
