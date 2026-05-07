"""
routes/styles.py

Global theme & CSS for Agentic Game Studio.
Call apply_styles() once per page render — placed in app.py so it fires automatically.
"""

import streamlit as st

# ---------------------------------------------------------------------------
# CSS — dark, professional, Inter-based design (Vercel / Linear inspired)
# ---------------------------------------------------------------------------
_GLOBAL_CSS = """
<style>
/* ═══════════════════════════════════════════════════════════════════
   AGENTIC GAME STUDIO — Global Theme  v1.1
   Dark studio aesthetic · Inter · steel-blue accent · conservative
═══════════════════════════════════════════════════════════════════ */

/* ── Google Fonts ─────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ── CSS custom properties ────────────────────────────────────── */
:root {
  --bg-base:       #0f1117;
  --bg-surface:    #161b22;
  --bg-card:       #1c2128;
  --bg-card-hover: #21262d;
  --border:        #30363d;
  --border-hover:  #4c75c4;
  --accent:        #4c75c4;
  --accent-light:  #79a4e8;
  --accent-glow:   rgba(76,117,196,0.18);
  --accent-bg:     rgba(76,117,196,0.07);
  --sky:           #4c75c4;
  --text-1:        #e6edf3;
  --text-2:        #8b949e;
  --text-3:        #6e7681;
  --success:       #3fb950;
  --warning:       #d29922;
  --error:         #f85149;
  --info:          #58a6ff;
  --radius-sm:     6px;
  --radius-md:     10px;
  --radius-lg:     14px;
  --radius-xl:     18px;
}

/* ── Base reset ───────────────────────────────────────────────── */
html, body, [class*="css"], .stApp {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  -webkit-font-smoothing: antialiased !important;
  text-rendering: optimizeLegibility !important;
}

/* ── Hide Streamlit chrome ─────────────────────────────────────── */
#MainMenu                    { visibility: hidden; }
footer                       { visibility: hidden; }
header                       { visibility: hidden; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"]    { display: none !important; }

/* ── Main layout ──────────────────────────────────────────────── */
.block-container {
  padding: 2rem 3rem 3rem !important;
  max-width: 1280px !important;
}

/* ── Typography ───────────────────────────────────────────────── */
h1 {
  font-size: 2.1rem !important;
  font-weight: 800 !important;
  letter-spacing: -0.03em !important;
  line-height: 1.2 !important;
  background: linear-gradient(135deg, #e6edf3 40%, #79a4e8 100%);
  -webkit-background-clip: text !important;
  -webkit-text-fill-color: transparent !important;
  background-clip: text !important;
  margin-bottom: 0.2rem !important;
}
h2 {
  font-size: 1.45rem !important;
  font-weight: 700 !important;
  color: #e2e8f0 !important;
  letter-spacing: -0.02em !important;
}
h3 {
  font-size: 1.1rem !important;
  font-weight: 600 !important;
  color: #cbd5e1 !important;
  letter-spacing: -0.01em !important;
}
p, li, label {
  font-size: 1.0rem !important;
  color: var(--text-2) !important;
  line-height: 1.6 !important;
}

/* ── Captions ─────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] p,
.stCaption p, small {
  font-size: 0.84rem !important;
  color: var(--text-3) !important;
}

/* ── Divider ──────────────────────────────────────────────────── */
hr {
  border: none !important;
  border-top: 1px solid var(--border) !important;
  margin: 1.5rem 0 !important;
}

/* ═══ BUTTONS ════════════════════════════════════════════════════ */

/* Primary */
[data-testid="stButton"] button[kind="primary"],
[data-testid="stFormSubmitButton"] button {
  background: #2d333b !important;
  color: #e6edf3 !important;
  border: 1px solid #444c56 !important;
  border-radius: var(--radius-sm) !important;
  padding: 0.55rem 1.35rem !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  letter-spacing: 0.01em !important;
  box-shadow: none !important;
  transition: background 0.18s ease, border-color 0.18s ease !important;
}
[data-testid="stButton"] button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] button:hover {
  background: #373e47 !important;
  border-color: #768390 !important;
}
[data-testid="stButton"] button[kind="primary"]:active,
[data-testid="stFormSubmitButton"] button:active {
  background: #21262d !important;
  border-color: #444c56 !important;
}

/* Secondary / Default */
[data-testid="stButton"] button:not([kind="primary"]) {
  background: rgba(26,26,53,0.7) !important;
  color: #cdd9e5 !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm) !important;
  padding: 0.48rem 1rem !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 500 !important;
  font-size: 0.88rem !important;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease !important;
}
[data-testid="stButton"] button:not([kind="primary"]):hover {
  border-color: var(--accent) !important;
  color: var(--accent-light) !important;
  background: var(--accent-bg) !important;
}

/* ═══ INPUTS ══════════════════════════════════════════════════════ */

[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm) !important;
  color: var(--text-1) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 0.88rem !important;
  padding: 0.5rem 0.85rem !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-glow) !important;
  outline: none !important;
}

[data-testid="stTextArea"] textarea {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm) !important;
  color: var(--text-1) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 0.88rem !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
[data-testid="stTextArea"] textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-glow) !important;
  outline: none !important;
}

/* ═══ SELECTBOX ═══════════════════════════════════════════════════ */

[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm) !important;
  color: var(--text-1) !important;
}

/* ═══ EXPANDERS ═══════════════════════════════════════════════════ */

[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  background: var(--bg-card) !important;
  margin-bottom: 0.65rem !important;
  overflow: hidden !important;
  transition: border-color 0.2s ease !important;
}
[data-testid="stExpander"]:hover {
  border-color: var(--border-hover) !important;
}
[data-testid="stExpander"] > details > summary {
  padding: 0.8rem 1rem !important;
  font-weight: 600 !important;
  font-size: 0.9rem !important;
  color: var(--text-1) !important;
}

/* ═══ PROGRESS BAR ════════════════════════════════════════════════ */

[data-testid="stProgress"] > div {
  background: var(--border) !important;
  border-radius: 999px !important;
  height: 8px !important;
  overflow: hidden !important;
}
[data-testid="stProgress"] > div > div {
  background: linear-gradient(90deg, var(--accent) 0%, var(--sky) 100%) !important;
  border-radius: 999px !important;
  transition: width 0.4s ease !important;
}

/* ═══ ALERTS ══════════════════════════════════════════════════════ */

[data-testid="stAlert"] {
  border-radius: var(--radius-md) !important;
  border-left-width: 3px !important;
  font-size: 0.88rem !important;
}

/* ═══ CHECKBOX & RADIO ════════════════════════════════════════════ */

[data-testid="stCheckbox"] label p,
[data-testid="stRadio"]    label p {
  color: var(--text-2) !important;
  font-size: 0.88rem !important;
}

/* ═══ FORMS ═══════════════════════════════════════════════════════ */

[data-testid="stForm"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-lg) !important;
  padding: 1.5rem !important;
}

/* ═══ MARKDOWN strong / code ══════════════════════════════════════ */

strong { color: var(--text-1) !important; font-weight: 600 !important; }
code   { background: rgba(124,58,237,0.12) !important;
         color: var(--accent-light) !important;
         border-radius: 4px !important;
         padding: 0.1em 0.4em !important;
         font-size: 0.85em !important; }

/* ═══════════════════════════════════════════════════════════════════
   CUSTOM COMPONENTS
════════════════════════════════════════════════════════════════════ */

/* ── Status badges ────────────────────────────────────────────── */
.ags-badge {
  display: inline-block;
  padding: 0.22rem 0.7rem;
  border-radius: 999px;
  font-family: 'Inter', sans-serif;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  vertical-align: middle;
}
.ags-badge-running   { background:rgba(56,139,253,0.12); color:#79a4e8; border:1px solid rgba(56,139,253,0.3); }
.ags-badge-starting  { background:rgba(56,139,253,0.08); color:#58a6ff; border:1px solid rgba(56,139,253,0.2); }
.ags-badge-completed { background:rgba(63,185,80,0.12);  color:#3fb950; border:1px solid rgba(63,185,80,0.3); }
.ags-badge-paused    { background:rgba(210,153,34,0.12); color:#d29922; border:1px solid rgba(210,153,34,0.3); }
.ags-badge-error     { background:rgba(248,81,73,0.12);  color:#f85149; border:1px solid rgba(248,81,73,0.3); }
.ags-badge-aborted   { background:rgba(248,81,73,0.08);  color:#f85149; border:1px solid rgba(248,81,73,0.2); }
.ags-badge-skipped   { background:rgba(110,118,129,0.10);color:#8b949e; border:1px solid rgba(110,118,129,0.2); }
.ags-badge-pending   { background:rgba(110,118,129,0.12);color:#8b949e; border:1px solid rgba(110,118,129,0.25); }

/* ── Pulsing live dot ─────────────────────────────────────────── */
@keyframes ags-pulse {
  0%,100% { opacity:1; transform:scale(1); }
  50%      { opacity:0.45; transform:scale(1.5); }
}
.ags-live-dot {
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  background: #58a6ff;
  animation: ags-pulse 1.5s ease-in-out infinite;
  margin-right: 6px;
  vertical-align: middle;
}

/* ── Project cards (landing) ──────────────────────────────────── */
.ags-project-card {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1rem 1.25rem;
  margin-bottom: 0.75rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
  cursor: pointer;
  text-decoration: none !important;
}
.ags-project-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 16px rgba(76,117,196,0.14);
  background: var(--bg-card-hover);
}
.ags-poster-thumb {
  flex: 0 0 300px;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-surface);
  aspect-ratio: 16/9;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ags-poster-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.ags-project-info {
  flex: 1;
  min-width: 0;
}
.ags-project-name {
  font-family: 'Inter', sans-serif;
  font-size: 1.0rem;
  font-weight: 700;
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 3px;
}
.ags-project-meta {
  font-family: 'Inter', sans-serif;
  font-size: 0.78rem;
  color: var(--text-3);
  margin-bottom: 8px;
  letter-spacing: 0.01em;
}
.ags-project-actions {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  align-items: stretch;
  min-width: 110px;
}

/* ── Action link buttons (inside HTML cards) ─────────────────── */
.ags-action-btn {
  display: inline-block;
  text-align: center;
  padding: 0.42rem 0.9rem;
  border-radius: var(--radius-sm);
  font-family: 'Inter', sans-serif;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: none !important;
  transition: all 0.18s ease;
  white-space: nowrap;
}
.ags-action-btn-primary {
  background: #2d333b;
  color: #e6edf3 !important;
  border: 1px solid #444c56;
}
.ags-action-btn-primary:hover {
  background: #373e47;
  border-color: #768390;
}
.ags-action-btn-secondary {
  background: transparent;
  color: var(--text-2) !important;
  border: 1px solid var(--border);
}
.ags-action-btn-secondary:hover {
  border-color: var(--accent);
  color: var(--accent-light) !important;
  background: var(--accent-bg);
}

/* ── CSS placeholder for missing poster ──────────────────────── */
.ags-poster-placeholder {
  width: 100%; height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  background: #1c2128;
}
.ags-poster-icon {
  font-size: 1.5rem;
  opacity: 0.2;
  display: block;
}
.ags-poster-label {
  font-family: 'Inter', sans-serif;
  font-size: 0.65rem;
  color: #6e7681;
  text-align: center;
  padding: 0 6px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  max-width: 100%;
  display: block;
}

/* ── Section label ────────────────────────────────────────────── */
.ags-section-label {
  font-family: 'Inter', sans-serif;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-3);
  margin: 1.75rem 0 0.6rem;
}

/* ── Page header bar ──────────────────────────────────────────── */
.ags-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

/* ── Step timeline row ────────────────────────────────────────── */
.ags-step-done    { color: #3fb950 !important; }
.ags-step-running { color: #58a6ff !important; }
.ags-step-error   { color: #f85149 !important; }
.ags-step-pending { color: var(--text-3) !important; }

/* ── Info callout box ─────────────────────────────────────────── */
.ags-callout {
  background: var(--accent-bg);
  border: 1px solid rgba(124,58,237,0.3);
  border-radius: var(--radius-md);
  padding: 0.85rem 1.1rem;
  font-family: 'Inter', sans-serif;
  font-size: 0.88rem;
  color: var(--text-2);
  margin-bottom: 1rem;
}
.ags-callout strong { color: var(--accent-light) !important; }

/* ── Settings gear button override ───────────────────────────── */
.ags-gear [data-testid="stButton"] button {
  padding: 0.3rem 0.6rem !important;
  font-size: 1rem !important;
  border-radius: 50% !important;
  border: 1px solid var(--border) !important;
  background: var(--bg-card) !important;
  color: var(--text-3) !important;
  min-height: unset !important;
  line-height: 1 !important;
}
.ags-gear [data-testid="stButton"] button:hover {
  border-color: var(--accent) !important;
  color: var(--accent-light) !important;
  background: var(--accent-bg) !important;
}

/* ── Footer ────────────────────────────────────────── */
.ags-footer {
  margin-top: 4rem;
  padding: 1.25rem 0 0.75rem;
  border-top: 1px solid var(--border);
  text-align: center;
  font-family: 'Inter', sans-serif;
  font-size: 0.82rem;
  color: var(--text-3);
  letter-spacing: 0.01em;
}
.ags-footer-brand {
  font-weight: 700;
  color: var(--text-2);
  letter-spacing: -0.01em;
}
.ags-footer-sep {
  margin: 0 0.55rem;
  opacity: 0.35;
}
</style>
"""

# ---------------------------------------------------------------------------
# Status badge HTML helpers
# ---------------------------------------------------------------------------
_STATUS_BADGE_CLASS = {
    "running": "ags-badge ags-badge-running",
    "starting": "ags-badge ags-badge-starting",
    "completed": "ags-badge ags-badge-completed",
    "paused": "ags-badge ags-badge-paused",
    "error": "ags-badge ags-badge-error",
    "aborted": "ags-badge ags-badge-aborted",
    "skipped": "ags-badge ags-badge-skipped",
    "pending": "ags-badge ags-badge-pending",
}


def status_badge(status: str) -> str:
    """Return an inline HTML badge for the given status string."""
    cls = _STATUS_BADGE_CLASS.get(status.lower(), "ags-badge ags-badge-pending")
    return f'<span class="{cls}">{status.upper()}</span>'


def live_dot() -> str:
    """Return an animated dot for RUNNING/STARTING states."""
    return '<span class="ags-live-dot"></span>'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def apply_styles() -> None:
    """Inject the global CSS.  Call once per page render (done in app.py)."""
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


def render_footer() -> None:
    """Render the site-wide footer.  Call once at the bottom of app.py."""
    st.markdown(
        '<div class="ags-footer">'
        '<span class="ags-footer-brand">Prompt-N-Click</span>'
        '<span class="ags-footer-sep">·</span>'
        "<span>AI-powered Point & Click games creation</span>"
        '<span class="ags-footer-sep">·</span>'
        "<span>© 2026</span>"
        "</div>",
        unsafe_allow_html=True,
    )
