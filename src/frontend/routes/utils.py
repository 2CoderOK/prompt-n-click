"""
routes/utils.py

Shared configuration, constants, and navigation helpers used by all route modules.
Import only from here — never cross-import between route modules.
"""

import os
from pathlib import Path

import streamlit as st
import requests

from shared.constants import (
    STEP_GAME_DESIGN,
    STEP_SCRIPT_WRITER,
    STEP_ART_DIRECTOR,
    STEP_GAME_BUILDER,
    STEP_ART_GENERATION,
    STEP_ART_CLEANUP,
    STEP_VOICEOVER_GENERATION,
    STEP_VOICEOVER_COMPRESSION,
)

# ---------------------------------------------------------------------------
# Environment config — single source of truth for all route modules
# ---------------------------------------------------------------------------
API_URL = os.getenv("API_URL", "http://localhost:8000")
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8000")
PROJECTS_ROOT = Path(os.getenv("PROJECTS_DATA_PATH", "/app/projects"))

# Maps pipeline step names → which viewer page & file(s) to open
STEP_ARTIFACT_MAP: dict[str, dict] = {
    STEP_GAME_DESIGN: {"page": "artifact_md", "file": "lore.md"},
    STEP_SCRIPT_WRITER: {"page": "artifact_md", "file": "voiceover.md"},
    STEP_ART_DIRECTOR: {
        "page": "artifact_json",
        "files": ["art_jobs.json", "art_info.json"],
    },
    STEP_GAME_BUILDER: {"page": "artifact_json", "files": ["game_config.json"]},
    STEP_ART_GENERATION: {"page": "artifact_images", "jobs_file": "art_jobs.json"},
    STEP_ART_CLEANUP: {"page": "artifact_images", "jobs_file": "art_jobs.json"},
    STEP_VOICEOVER_GENERATION: {
        "page": "artifact_audio",
        "jobs_file": "voiceover_jobs.json",
    },
    STEP_VOICEOVER_COMPRESSION: {
        "page": "artifact_audio",
        "jobs_file": "voiceover_jobs.json",
    },
}


# Pages that carry project_id in the URL
_PAGES_WITH_PROJECT = frozenset(
    {
        "progress",
        "game",
        "editor",
        "artifact_md",
        "artifact_json",
        "artifact_images",
        "artifact_audio",
    }
)
# Pages that also carry artifact step in the URL
_PAGES_WITH_STEP = frozenset(
    {
        "artifact_md",
        "artifact_json",
        "artifact_images",
        "artifact_audio",
    }
)


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------
def navigate_to(page_name: str, project_id: str | None = None) -> None:
    if page_name == "settings":
        st.session_state.prev_page = st.session_state.get("page", "landing")
    st.session_state.page = page_name
    if project_id is not None:
        st.session_state.project_id = project_id

    # Sync browser URL so pages are bookmarkable and shareable
    st.query_params.clear()
    st.query_params["page"] = page_name
    if page_name in _PAGES_WITH_PROJECT:
        pid = project_id or st.session_state.get("project_id")
        if pid:
            st.query_params["project_id"] = pid
    if page_name in _PAGES_WITH_STEP:
        step = st.session_state.get("artifact_step")
        if step:
            st.query_params["step"] = step

    st.rerun()


def navigate_to_artifact(step: str, project_id: str) -> None:
    mapping = STEP_ARTIFACT_MAP.get(step)
    if not mapping:
        return
    st.session_state.artifact_step = step
    st.session_state.artifact_project_id = project_id
    navigate_to(mapping["page"])


# ---------------------------------------------------------------------------
# Shared UI components
# ---------------------------------------------------------------------------
def render_settings_button() -> None:
    _, col_gear = st.columns([10, 1])
    with col_gear:
        if st.button("⚙️", help="Settings", key="settings_btn"):
            navigate_to("settings")


def get_music_attribution(project_id: str) -> dict | None:
    """Return the selected track's attribution info, or None if not applicable.

    Reads game_config.json (music.track) and music_tracks.json to find the
    matching track entry.  Returns a dict with keys: title, page_url, license,
    attribution — or None if no track is selected or files are missing.
    """
    import json

    config_path = PROJECTS_ROOT / project_id / "game_config.json"
    tracks_path = PROJECTS_ROOT / project_id / "music_tracks.json"

    if not config_path.exists() or not tracks_path.exists():
        return None

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        selected = (config.get("music") or {}).get("track", "none")
        if not selected or selected == "none":
            return None

        data = json.loads(tracks_path.read_text(encoding="utf-8"))
        tracks = data.get("tracks", [])
        track = next((t for t in tracks if t.get("filename") == selected), None)
        if not track:
            return None

        return {
            "title": track.get("title", selected),
            "page_url": track.get("page_url", ""),
            "license": track.get("license", ""),
            "attribution": track.get("attribution", ""),
        }
    except Exception:
        return None


def rerun_from_step(project_id: str, step_name: str) -> None:
    requests.post(f"{API_URL}/projects/{project_id}/run-from/{step_name}")


def rerun_single_step(project_id: str, step_name: str) -> None:
    """Run only step_name, then pause (smart dependency reset still applies)."""
    requests.post(
        f"{API_URL}/projects/{project_id}/run-from/{step_name}",
        params={"single_step": "true"},
    )
