import base64
import html as html_lib

import streamlit as st
import requests

from shared.constants import STATUS_RUNNING, STATUS_STARTING
from routes.styles import status_badge, live_dot
from routes.utils import (
    API_URL,
    PROJECTS_ROOT,
    navigate_to,
    render_settings_button,
    get_music_attribution,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _poster_img_html(proj_id: str, name: str) -> str:
    """Return an <img> base64 tag if the poster exists, or a pure-CSS placeholder div.

    The placeholder deliberately avoids base64 / data-URIs because long base64
    strings inside src attributes can corrupt Streamlit's markdown HTML parser,
    causing the rest of the card to render as raw text.
    """
    poster_path = PROJECTS_ROOT / proj_id / "img" / "bg_poster.png"

    if not poster_path.exists():
        poster_path = PROJECTS_ROOT / proj_id / "img" / "bg_game_poster.png"

    if poster_path.exists():
        try:
            b64 = base64.b64encode(poster_path.read_bytes()).decode("ascii")
            return f'<img src="data:image/png;base64,{b64}" class="ags-poster-img" />'
        except Exception:
            pass

    # Pure CSS placeholder — no base64, safe for Streamlit's markdown renderer
    safe_name = html_lib.escape(name)[:22]
    return (
        '<div class="ags-poster-placeholder">'
        '<span class="ags-poster-icon">&#127918;</span>'
        f'<span class="ags-poster-label">{safe_name}</span>'
        "</div>"
    )


def _project_card_html(proj: dict) -> str:
    """Render a single project as a self-contained styled HTML card."""
    proj_id = proj["id"]
    status = proj.get("status", "pending").lower()
    name = html_lib.escape(proj.get("name", "Unnamed Project"))
    genre = html_lib.escape(proj.get("genre") or "N/A")
    size = html_lib.escape(proj.get("size") or "N/A")

    poster_html = _poster_img_html(proj_id, proj.get("name", ""))
    badge_html = status_badge(status)
    dot_html = live_dot() if status in ("running", "starting") else ""

    # Music attribution snippet (only if track selected and attribution present)
    music_html = ""
    music_info = get_music_attribution(proj_id)
    if music_info and music_info.get("attribution"):
        track_title = html_lib.escape(music_info["title"])
        page_url = music_info.get("page_url", "")
        attribution_text = html_lib.escape(music_info["attribution"])
        track_link = (
            f'<a href="{html_lib.escape(page_url)}" target="_blank" '
            f'style="color:#0af;text-decoration:none;" onclick="event.stopPropagation()">'
            f"{track_title}</a>"
            if page_url
            else track_title
        )
        music_html = (
            f'<div style="margin-top:8px;font-size:0.72rem;color:#64748b;line-height:1.4;">'
            f"\u266a {track_link}"
            f'<br><span style="font-size:0.68rem;">{attribution_text}</span>'
            f"</div>"
        )

    # Primary action button
    if status == "completed":
        primary_btn = (
            f'<a href="?page=game&project_id={proj_id}" '
            f'onclick="event.stopPropagation()" '
            f'class="ags-action-btn ags-action-btn-primary">▶ Play</a>'
        )
    elif status in ("running", "starting"):
        primary_btn = (
            f'<a href="?page=progress&project_id={proj_id}" '
            f'onclick="event.stopPropagation()" '
            f'class="ags-action-btn ags-action-btn-primary">⟳ View Progress</a>'
        )
    else:
        primary_btn = ""

    details_btn = (
        f'<a href="?page=progress&project_id={proj_id}" '
        f'onclick="event.stopPropagation()" '
        f'class="ags-action-btn ags-action-btn-secondary">Details \u2192</a>'
    )

    # Build actions block — no newlines so an empty primary_btn never leaves
    # a blank line inside the div (blank lines break Streamlit's HTML parser).
    actions = primary_btn + details_btn

    poster_href = (
        f"?page=game&project_id={proj_id}"
        if status == "completed"
        else f"?page=progress&project_id={proj_id}"
    )
    return (
        f'<div class="ags-project-card" onclick="location.href=\'?page=progress&project_id={proj_id}\'">'
        f'<a href="{poster_href}" class="ags-poster-thumb" onclick="event.stopPropagation()" style="text-decoration:none;">{poster_html}</a>'
        f'<div class="ags-project-info">'
        f'<div class="ags-project-name">{name}</div>'
        f'<div class="ags-project-meta">{genre}&nbsp;&nbsp;\u00b7&nbsp;&nbsp;{size}</div>'
        f'<div style="margin-top:10px;">{dot_html}{badge_html}</div>'
        f"{music_html}"
        f"</div>"
        f'<div class="ags-project-actions">{actions}</div>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


def landing_page() -> None:
    render_settings_button()

    # Studio logo
    try:
        logo_resp = requests.get(f"{API_URL}/static/phaser/fx/logo.png", timeout=3)
        if logo_resp.status_code == 200:
            st.image(logo_resp.content, width=200)
    except Exception:
        pass

    st.title("Prompt-N-Click")
    st.markdown(
        '<p style="color:#64748b;font-size:0.93rem;margin-top:-0.5rem;margin-bottom:0;">'
        "Build Point & Click games with autonomous AI agents — text, design, art, voice &amp; configuration."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Fetch projects ──────────────────────────────────────────
    try:
        projects = requests.get(f"{API_URL}/projects").json().get("projects", [])
    except Exception as e:
        st.error(f"Failed to load projects: {e}")
        projects = []

    running = next(
        (p for p in projects if p["status"] in (STATUS_RUNNING, STATUS_STARTING)),
        None,
    )

    st.divider()

    # ── CTA / running banner ────────────────────────────────────
    if running:
        st.markdown(
            f'<div class="ags-callout">'
            f"<strong>⚡ {html_lib.escape(running['name'])}</strong> is currently running. "
            f"Wait for it to complete before starting a new project.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Open Running Project", type="primary"):
            navigate_to("progress", project_id=running["id"])
    else:
        if st.button("✨ Start New Project", type="primary"):
            navigate_to("new_game")

    # ── Project cards ───────────────────────────────────────────
    if not projects:
        st.markdown(
            '<p style="color:#64748b;text-align:center;padding:3rem 0;">'
            "No projects yet. Click <strong>Start New Project</strong> to begin."
            "</p>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        '<div class="ags-section-label">Your Projects</div>',
        unsafe_allow_html=True,
    )
    cards_html = "\n".join(_project_card_html(p) for p in projects)
    st.markdown(cards_html, unsafe_allow_html=True)
