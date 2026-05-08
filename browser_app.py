"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         ISOLATED EMBEDDED BROWSER — Streamlit + Playwright                  ║
║         Streamlit Cloud–ready edition (auto-installs Chromium binary)       ║
╚══════════════════════════════════════════════════════════════════════════════╝

Deployment notes:
  • The @st.cache_resource `_ensure_chromium()` runs `playwright install chromium`
    exactly once per server process — on first cold start.
  • System-level libraries are installed from packages.txt by Streamlit Cloud
    before the Python app starts, so chromium_headless_shell will find them.
  • All browsing data lives in RAM; nothing is written to disk.
"""

import subprocess
import sys
import time
from urllib.parse import urlparse, quote_plus

import streamlit as st
from playwright.sync_api import sync_playwright

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────
HOME_URL     = "https://www.google.com"
VIEWPORT_W   = 1280
VIEWPORT_H   = 860
TIMEOUT_MS   = 25_000
MAX_LINKS    = 60
SCREENSHOT_Q = 88

# ──────────────────────────────────────────────────────────────────────────────
# Page config  (must come before any other st.* call)
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Isolated Browser",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
# CSS — dark GitHub-inspired theme
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] { background:#0d1117!important; }
.stApp { background:#0d1117; }
[data-testid="stHeader"] { background:transparent; }
#MainMenu, footer { visibility:hidden; }
.block-container { padding:0.6rem 1.1rem 0.4rem!important; max-width:100%!important; }
[data-testid="column"] { padding:0 3px!important; }

/* Nav buttons */
.stButton>button {
    background:#21262d!important; color:#c9d1d9!important;
    border:1px solid #30363d!important; border-radius:6px!important;
    font-size:17px!important; min-width:38px!important;
    height:38px!important; padding:0 9px!important; transition:all .12s;
}
.stButton>button:hover:not([disabled]) {
    background:#30363d!important; border-color:#58a6ff!important; color:#58a6ff!important;
}
.stButton>button[disabled] { opacity:.3!important; cursor:default!important; }

/* URL bar */
.stTextInput>div>div>input {
    background:#161b22!important; color:#c9d1d9!important;
    border:1px solid #30363d!important; border-radius:20px!important;
    padding:6px 18px!important; font-size:13.5px!important; height:38px!important;
}
.stTextInput>div>div>input:focus {
    border-color:#58a6ff!important;
    box-shadow:0 0 0 3px rgba(88,166,255,.18)!important; outline:none!important;
}
.stTextInput label { display:none!important; }

/* Go button */
.stFormSubmitButton>button {
    background:#1f6feb!important; color:#fff!important;
    border:1px solid #1f6feb!important; border-radius:6px!important;
    height:38px!important; padding:0 18px!important;
    font-weight:600!important; font-size:13px!important;
}
.stFormSubmitButton>button:hover { background:#388bfd!important; }

/* Browser chrome */
.browser-tab-bar {
    background:#161b22; border:1px solid #21262d;
    border-bottom:none; border-radius:8px 8px 0 0;
    padding:6px 14px; display:flex; align-items:center; gap:8px; margin-top:4px;
}
.browser-tab-dot { width:12px;height:12px;border-radius:50%;display:inline-block; }
.dot-red{background:#ff5f57;} .dot-amber{background:#febc2e;} .dot-green{background:#28c840;}
.tab-title { font-size:12.5px;color:#8b949e;margin-left:6px;
             overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:600px; }

/* Screenshot */
[data-testid="stImage"] img {
    border:1px solid #21262d; border-top:none!important;
    border-radius:0!important; display:block; width:100%!important;
}

/* Status bar */
.status-bar {
    background:#161b22; border:1px solid #21262d; border-top:none;
    border-radius:0 0 8px 8px; padding:4px 16px;
    font-size:11px; color:#8b949e; font-family:monospace;
    margin-bottom:10px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}

/* Error card */
.err-card {
    background:#160c0c; border:1px solid #f85149; border-radius:6px;
    padding:10px 16px; color:#f85149; font-size:12.5px;
    margin:4px 0; white-space:pre-wrap; font-family:monospace;
}

/* Sidebar */
[data-testid="stSidebarContent"] { background:#0d1117!important; }
.sec-hdr {
    font-size:10.5px; font-weight:700; text-transform:uppercase;
    letter-spacing:1px; color:#8b949e; margin:10px 0 3px;
}
section[data-testid="stSidebar"] .stButton>button {
    text-align:left!important; overflow:hidden!important;
    text-overflow:ellipsis!important; white-space:nowrap!important;
    width:100%!important; font-size:11.5px!important; height:26px!important;
    background:transparent!important; border-color:transparent!important;
    border-radius:4px!important; padding:0 6px!important;
}
section[data-testid="stSidebar"] .stButton>button:hover {
    background:#21262d!important; border-color:#30363d!important;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# ★  Streamlit Cloud: auto-install Chromium binary on first cold start
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="⚙️  Setting up browser engine (first run only)…")
def _ensure_chromium() -> bool:
    """
    Run `playwright install chromium` exactly once per server process.

    On Streamlit Cloud:
      • Python packages (requirements.txt) are pre-installed.
      • System libraries (packages.txt) are pre-installed via apt.
      • But the Playwright Chromium *binary* must be downloaded at runtime
        because it lives in a user-writable cache (~/.cache/ms-playwright).
      • @st.cache_resource ensures this runs once, not on every rerun.

    Returns True on success, False on failure (app will still try to run).
    """
    try:
        result = subprocess.run(
            ["playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=180,        # Up to 3 min for first download
        )
        return result.returncode == 0
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _is_valid_url(text: str) -> bool:
    try:
        r = urlparse(text)
        return r.scheme in ("http", "https") and bool(r.netloc)
    except Exception:
        return False


def resolve_input(text: str) -> str:
    """
    "https://example.com"  →  kept as-is
    "example.com"          →  "https://example.com"
    "python tutorial"      →  Google search URL
    """
    text = text.strip()
    if not text:
        return HOME_URL
    if _is_valid_url(text):
        return text
    if "." in text and " " not in text and 4 < len(text) < 80:
        candidate = f"https://{text}"
        if _is_valid_url(candidate):
            return candidate
    return f"https://www.google.com/search?q={quote_plus(text)}"


# ──────────────────────────────────────────────────────────────────────────────
# Shared Playwright browser  (one Chromium process for all sessions)
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _shared_browser():
    """
    Launch exactly one headless Chromium for the server lifetime.
    All sessions share this browser; each gets its own BrowserContext (isolated).
    Returns (playwright_handle, browser) — playwright_handle prevents GC.
    """
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--mute-audio",
        ],
    )
    return pw, browser


# ──────────────────────────────────────────────────────────────────────────────
# Per-session isolated context
# ──────────────────────────────────────────────────────────────────────────────

def init_session() -> None:
    """
    Create a BrowserContext for this Streamlit session.

    BrowserContext guarantees:
      ✓  Own cookie jar  (not shared with host browser or other sessions)
      ✓  Own localStorage / sessionStorage / IndexedDB
      ✓  Own cache partition
      ✗  Nothing written to disk  (no storage_state arg → ephemeral)
    """
    if st.session_state.get("_ready"):
        return

    _, browser = _shared_browser()

    context = browser.new_context(
        viewport            = {"width": VIEWPORT_W, "height": VIEWPORT_H},
        ignore_https_errors = True,
        java_script_enabled = True,
        accept_downloads    = False,
    )
    page = context.new_page()

    st.session_state.update(
        {
            "_ready":     True,
            "ctx":        context,
            "page":       page,
            "history":    [],
            "hist_idx":   -1,
            "cur_url":    "",
            "page_title": "New Tab",
            "screenshot": None,
            "error_msg":  None,
            "status":     "Ready",
            "links":      [],
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# Internal: capture page state
# ──────────────────────────────────────────────────────────────────────────────

def _sync() -> None:
    page = st.session_state.page
    try:
        img   = page.screenshot(type="jpeg", quality=SCREENSHOT_Q, full_page=False)
        links = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => ({
                    href: a.href,
                    text: (a.innerText||a.title||a.href).trim()
                              .replace(/\\s+/g,' ').slice(0,70)
                }))
                .filter(l => l.href.startsWith('http') && l.text.length > 2)
                .slice(0, 60);
        }""") or []

        st.session_state.screenshot = img
        st.session_state.cur_url    = page.url
        st.session_state.page_title = page.title() or page.url
        st.session_state.error_msg  = None
        st.session_state.status     = f"✓  {page.url}"
        st.session_state.links      = links

    except Exception as exc:
        st.session_state.error_msg = f"Render error: {exc}"
        st.session_state.status    = "Error"


# ──────────────────────────────────────────────────────────────────────────────
# Browser actions
# ──────────────────────────────────────────────────────────────────────────────

def act_navigate(text: str) -> None:
    url  = resolve_input(text)
    page = st.session_state.page
    try:
        st.session_state.status = f"Loading  {url}…"
        page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        time.sleep(0.35)

        hist = st.session_state.history[: st.session_state.hist_idx + 1]
        hist.append(page.url)
        st.session_state.history  = hist
        st.session_state.hist_idx = len(hist) - 1

    except Exception as exc:
        st.session_state.error_msg = (
            f"⚠️  Could not load:\n{url}\n\n{type(exc).__name__}: {exc}"
        )
    finally:
        _sync()


def act_back() -> None:
    if st.session_state.hist_idx > 0:
        try:
            st.session_state.page.go_back(timeout=TIMEOUT_MS)
            st.session_state.hist_idx -= 1
            time.sleep(0.3)
        except Exception as exc:
            st.session_state.error_msg = str(exc)
        _sync()


def act_forward() -> None:
    if st.session_state.hist_idx < len(st.session_state.history) - 1:
        try:
            st.session_state.page.go_forward(timeout=TIMEOUT_MS)
            st.session_state.hist_idx += 1
            time.sleep(0.3)
        except Exception as exc:
            st.session_state.error_msg = str(exc)
        _sync()


def act_refresh() -> None:
    try:
        st.session_state.page.reload(wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        time.sleep(0.3)
    except Exception as exc:
        st.session_state.error_msg = str(exc)
    _sync()


def act_home() -> None:
    act_navigate(HOME_URL)


# ──────────────────────────────────────────────────────────────────────────────
# UI: Sidebar
# ──────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🌐 Browser")
        st.divider()

        st.markdown('<p class="sec-hdr">Links on this page</p>', unsafe_allow_html=True)
        links = st.session_state.links
        if links:
            for i, lnk in enumerate(links[:MAX_LINKS]):
                label = lnk["text"][:46] + ("…" if len(lnk["text"]) > 46 else "")
                if st.button(label, key=f"lnk_{i}", help=lnk["href"],
                             use_container_width=True):
                    act_navigate(lnk["href"])
                    st.rerun()
        else:
            st.caption("*Load a page to see links.*")

        st.divider()

        st.markdown('<p class="sec-hdr">Session history</p>', unsafe_allow_html=True)
        hist = st.session_state.history
        idx  = st.session_state.hist_idx
        if hist:
            for i, url in enumerate(reversed(hist[-15:])):
                pos   = len(hist) - 1 - i
                pfx   = "▶ " if pos == idx else "   "
                short = url.replace("https://","").replace("http://","")[:44]
                st.caption(f"{pfx}`{short}`")
        else:
            st.caption("*No history yet.*")

        st.divider()

        st.markdown('<p class="sec-hdr">Session info</p>', unsafe_allow_html=True)
        st.caption(f"**Pages loaded:** {len(hist)}")
        st.caption("**Cookie scope:** this session only")
        st.caption("**Disk writes:** none")
        st.caption("**Extensions:** none")

        st.divider()
        with st.expander("📖 Isolation explained", expanded=False):
            st.markdown("""
**BrowserContext vs normal tab**

| Property | Normal Tab | This App |
|---|---|---|
| Cookies | Disk, shared | RAM only |
| localStorage | Shared | Isolated |
| History | Disk | Never written |
| Login state | Persistent | Cleared on close |
| Extensions | Active | None |

Pages render as JPEG screenshots of a real headless Chromium viewport — bypassing
`X-Frame-Options: DENY` which would block an iframe approach.
Use the **Links** panel above or type URLs directly to navigate.
            """)


# ──────────────────────────────────────────────────────────────────────────────
# UI: Navigation bar
# ──────────────────────────────────────────────────────────────────────────────

def render_nav() -> None:
    can_back    = st.session_state.hist_idx > 0
    can_forward = st.session_state.hist_idx < len(st.session_state.history) - 1

    cb, cf, cr, ch, _ = st.columns([1, 1, 1, 1, 28])
    with cb:
        if st.button("◀", key="btn_back",    disabled=not can_back,    help="Back"):
            act_back();    st.rerun()
    with cf:
        if st.button("▶", key="btn_fwd",     disabled=not can_forward, help="Forward"):
            act_forward(); st.rerun()
    with cr:
        if st.button("⟳", key="btn_refresh",                          help="Refresh"):
            act_refresh(); st.rerun()
    with ch:
        if st.button("⌂", key="btn_home",                             help="Home"):
            act_home();    st.rerun()

    with st.form("url_form", clear_on_submit=False, border=False):
        cu, cg = st.columns([26, 2])
        with cu:
            url_val = st.text_input(
                "url",
                value            = st.session_state.cur_url,
                placeholder      = "Enter a URL or search term and press Enter…",
                label_visibility = "collapsed",
            )
        with cg:
            submitted = st.form_submit_button("Go →", use_container_width=True)

    if submitted and url_val.strip():
        act_navigate(url_val)
        st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── 1. Install Chromium binary if needed (runs once per server process) ───
    _ensure_chromium()

    # ── 2. Isolated BrowserContext for this session ───────────────────────────
    init_session()

    # ── 3. Load home on very first render ─────────────────────────────────────
    if st.session_state.screenshot is None:
        act_navigate(HOME_URL)

    # ── 4. Sidebar ────────────────────────────────────────────────────────────
    render_sidebar()

    # ── 5. Tab / title bar ────────────────────────────────────────────────────
    title = (st.session_state.page_title or "New Tab")[:110]
    st.markdown(
        f"""<div class="browser-tab-bar">
            <span class="browser-tab-dot dot-red"></span>
            <span class="browser-tab-dot dot-amber"></span>
            <span class="browser-tab-dot dot-green"></span>
            <span class="tab-title">🌐 &nbsp;{title}</span>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── 6. Navigation toolbar ─────────────────────────────────────────────────
    render_nav()

    # ── 7. Error banner ───────────────────────────────────────────────────────
    if st.session_state.error_msg:
        st.markdown(
            f'<div class="err-card">{st.session_state.error_msg}</div>',
            unsafe_allow_html=True,
        )

    # ── 8. Viewport screenshot ────────────────────────────────────────────────
    if st.session_state.screenshot:
        st.image(
            st.session_state.screenshot,
            use_container_width=True,
            output_format="JPEG",
        )
    else:
        st.info("⏳  Loading…")

    # ── 9. Status bar ─────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="status-bar">{st.session_state.status}</div>',
        unsafe_allow_html=True,
    )


main()
