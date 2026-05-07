import streamlit as st

from routes.styles import apply_styles, render_footer
from routes.landing import landing_page
from routes.project import new_game_page, progress_page
from routes.artifacts import (
    artifact_md_page,
    artifact_json_page,
    artifact_images_page,
    artifact_audio_page,
    artifact_music_page,
)
from routes.settings import settings_page
from routes.phaser import editor_page, game_page

st.set_page_config(page_title="Agentic Game Studio", layout="wide")

# Inject global CSS theme on every render
apply_styles()
# ---------------------------------------------------------------------------
# Session state bootstrap â€” run once per browser session
# ---------------------------------------------------------------------------
if "page" in st.query_params:
    st.session_state.page = st.query_params["page"]
elif "page" not in st.session_state:
    st.session_state.page = "landing"

if "project_id" in st.query_params:
    st.session_state.project_id = st.query_params["project_id"]
elif "project_id" not in st.session_state:
    st.session_state.project_id = None

# Artifact pages carry step + project_id in the URL for direct linking
if "step" in st.query_params:
    st.session_state.artifact_step = st.query_params["step"]
    st.session_state.artifact_project_id = st.query_params.get(
        "project_id"
    ) or st.session_state.get("project_id")

# ---------------------------------------------------------------------------
# Routing table
# ---------------------------------------------------------------------------
_ROUTES = {
    "landing": landing_page,
    "new_game": new_game_page,
    "progress": progress_page,
    "artifact_md": artifact_md_page,
    "artifact_json": artifact_json_page,
    "artifact_images": artifact_images_page,
    "artifact_audio": artifact_audio_page,
    "artifact_music": artifact_music_page,
    "settings": settings_page,
    "editor": editor_page,
    "game": game_page,
}

page_fn = _ROUTES.get(st.session_state.page, landing_page)
page_fn()

render_footer()
