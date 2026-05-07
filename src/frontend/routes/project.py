import time
import uuid

import streamlit as st
import requests

from shared.constants import (
    STATUS_RUNNING,
    STATUS_STARTING,
    STATUS_PAUSED,
    STATUS_COMPLETED,
    STATUS_ABORTED,
    STATUS_ERROR,
    GAME_TYPE_NAMES,
    GAME_TYPE_POINT_AND_CLICK,
    GAME_TYPES,
    GAME_GENRES,
    STEP_COMPLETED,
    PIPELINE_STEPS,
    CMD_ABORT,
    CMD_RETRY,
    CMD_PAUSE,
    CMD_RUN,
)
from routes.styles import status_badge, live_dot
from routes.utils import (
    API_URL,
    PUBLIC_API_URL,
    PROJECTS_ROOT,
    STEP_ARTIFACT_MAP,
    navigate_to,
    navigate_to_artifact,
    render_settings_button,
    rerun_from_step,
    rerun_single_step,
    get_music_attribution,
)


def _fmt_elapsed(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s"


def new_game_page() -> None:
    render_settings_button()
    st.title("🛠️ Project Configuration")

    try:
        _profiles_res = requests.get(f"{API_URL}/llm-profiles")
        _profiles = _profiles_res.json().get("profiles", [])
    except Exception:
        _profiles = []

    _profile_names = [p["name"] for p in _profiles]
    _default_idx = next((i for i, p in enumerate(_profiles) if p["is_default"]), 0)
    _profile_id_by_name = {p["name"]: p["id"] for p in _profiles}

    _LLAMACPP_STEPS = [
        ("game_designer", "Game Designer"),
        ("script_writer", "Script Writer"),
        ("art_director", "Art Director"),
        ("game_builder", "Game Builder"),
        ("music_downloader", "Music Downloader"),
    ]

    with st.form("game_config_form"):
        st.write("Leave text fields empty to let the Agent generate ideas for you!")

        name = st.text_input("Game Name", help="Leave empty for Agent to generate.")

        size = st.selectbox(
            "Game Size",
            ["Tiny", "Small", "Medium", "Large"],
            help="Tiny: ~6KB+ lore. Small: ~9KB+. Medium: ~15KB+. Large: ~25KB+.",
            index=1,
        )

        creativity = st.selectbox(
            "Creativity Mode",
            ["Grounded Mode", "Full Creativity"],
            index=0,
        )

        _ = st.selectbox(
            "Game Type",
            [GAME_TYPE_NAMES[gt] for gt in GAME_TYPES],
            index=0,
        )

        genres = st.multiselect("Genre(s)", GAME_GENRES)

        art_style = st.text_input(
            "Art Style",
            placeholder="e.g. 16-bit pixel art, dark fantasy watercolor...",
        )

        desc = st.text_area(
            "Game Description & Instructions",
            height=150,
            placeholder="e.g. A mystery game set on an abandoned space station...",
        )

        col_nv, col_nm = st.columns(2)
        with col_nv:
            no_voiceover = st.checkbox(
                "No Voiceover",
                value=False,
                help="Skip script writing and voice generation. No character dialogue audio.",
                disabled=True,  # Voiceover is currently required for the pipeline; this is a placeholder for future flexibility
            )
        with col_nm:
            no_music = st.checkbox(
                "No Music",
                value=False,
                help="Skip background music selection and download.",
                disabled=True,  # Music is currently required for the pipeline; this is a placeholder for future flexibility
            )

        with st.expander("⚙️ Advanced: LLM Profile per Step", expanded=False):
            if _profile_names:
                st.caption("Select the LLM profile for each AI step.")
                _step_profile_sel = {}
                for _step_name, _step_label in _LLAMACPP_STEPS:
                    _step_profile_sel[_step_name] = st.selectbox(
                        _step_label,
                        options=_profile_names,
                        index=_default_idx,
                        key=f"llm_prof_{_step_name}",
                    )
            else:
                st.warning("No LLM profiles found. Go to ⚙️ Settings to add one.")
                _step_profile_sel = {}

        submitted = st.form_submit_button("🚀 Start Generation", type="primary")
        st.divider()

        if submitted:
            project_id = str(uuid.uuid4())
            try:
                res = requests.post(
                    f"{API_URL}/projects/new",
                    json={
                        "project_id": project_id,
                        "name": name,
                        "size": size,
                        "type": GAME_TYPE_POINT_AND_CLICK,
                        "genre": ",".join(genres) if genres else "",
                        "creativity": creativity,
                        "art_style": art_style,
                        "description": desc,
                        "no_voiceover": no_voiceover,
                        "no_music": no_music,
                    },
                )
                res.raise_for_status()

                if _step_profile_sel:
                    requests.post(
                        f"{API_URL}/projects/{project_id}/llm-configs",
                        json=[
                            {
                                "step_name": step_name,
                                "llm_profile_id": _profile_id_by_name[profile_name],
                            }
                            for step_name, profile_name in _step_profile_sel.items()
                        ],
                    )

                st.query_params["project_id"] = project_id
                navigate_to("progress", project_id=project_id)

            except Exception as e:
                st.error(f"Failed to connect to backend: {e}")

    if st.button("← Back", key="back_to_landing_from_config"):
        navigate_to("landing")


def progress_page() -> None:
    render_settings_button()

    if "project_id" in st.query_params:
        st.session_state.project_id = st.query_params["project_id"]
    else:
        st.query_params["project_id"] = st.session_state.project_id

    if not st.session_state.project_id:
        st.warning("No project selected.")
        if st.button("Go Back"):
            navigate_to("landing")
        return

    project_id = st.session_state.project_id

    try:
        proj_res = requests.get(f"{API_URL}/projects/{project_id}")
        proj_res.raise_for_status()
        proj = proj_res.json()
        current_status = proj["status"]
        current_step = proj["current_step"]
    except Exception as e:
        st.error(f"Failed to fetch project: {e}")
        return

    try:
        metrics_list = requests.get(f"{API_URL}/projects/{project_id}/metrics").json()
    except Exception:
        metrics_list = []
    metrics_by_step = {m["step_name"]: m for m in (metrics_list or [])}

    proj_name = proj.get("name", "Unnamed AI Project")
    st.markdown(
        f"<h1 style='margin-bottom:0.1rem;'>{proj_name}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"{status_badge(current_status)} "
        f"<span style='color:#64748b;font-size:0.82rem;margin-left:8px;'>Progress Tracker</span>",
        unsafe_allow_html=True,
    )

    # Game poster (if generated)
    poster_path = PROJECTS_ROOT / project_id / "img" / "bg_poster.png"
    if not poster_path.exists():
        poster_path = PROJECTS_ROOT / project_id / "img" / "bg_game_poster.png"
    if poster_path.exists():
        col_poster, col_spacer = st.columns([2, 3])
        with col_poster:
            st.image(str(poster_path), use_container_width=True)

    with st.expander("Project Details"):
        st.markdown(f"- **Project ID:** `{proj.get('id', '')}`")
        st.markdown(f"- **Status:** {current_status.upper()}")
        st.markdown(f"- **Size:** {proj.get('size') or 'N/A'}")
        st.markdown(
            f"- **Type:** {GAME_TYPE_NAMES.get(proj.get('type', GAME_TYPE_POINT_AND_CLICK), 'N/A')}"
        )
        st.markdown(f"- **Genre:** {proj.get('genre') or 'N/A'}")
        st.markdown(f"- **Creativity:** {proj.get('creativity') or 'N/A'}")
        st.markdown(f"- **Art Style:** {proj.get('art_style') or 'N/A'}")
        st.markdown(f"- **Description:** {proj.get('description') or 'N/A'}")

    if st.button("← Back", key="back_to_landing_from_progress"):
        navigate_to("landing")

    # Music attribution (if a track is selected and has attribution)
    music_info = get_music_attribution(project_id)
    if music_info and music_info.get("attribution"):
        with st.expander("🎵 Music Attribution", expanded=False):
            title = music_info["title"]
            page_url = music_info.get("page_url", "")
            if page_url:
                st.markdown(f"**Track:** [{title}]({page_url})")
            else:
                st.markdown(f"**Track:** {title}")
            if music_info.get("license"):
                st.caption(f"License: {music_info['license']}")
            st.text(music_info["attribution"])

    st.divider()

    step_names = [s["name"] for s in PIPELINE_STEPS]
    n_steps = len(step_names)
    try:
        current_step_idx = step_names.index(current_step)
    except ValueError:
        current_step_idx = n_steps if current_status == STATUS_COMPLETED else 0

    completed_count = (
        n_steps if current_status == STATUS_COMPLETED else current_step_idx
    )
    overall_pct = completed_count / n_steps

    st.markdown(
        f'<div class="ags-section-label">Overall Progress — {int(overall_pct * 100)}% '
        f"({completed_count}/{n_steps} steps)</div>",
        unsafe_allow_html=True,
    )
    st.progress(overall_pct)

    st.divider()
    st.markdown(
        '<div class="ags-section-label">Pipeline Steps</div>', unsafe_allow_html=True
    )

    now = time.time()

    for i, step in enumerate(PIPELINE_STEPS):
        step_name = step["name"]
        step_desc = step["desc"]
        m = metrics_by_step.get(step_name, {})

        is_done = current_status == STATUS_COMPLETED or i < current_step_idx
        is_current = i == current_step_idx and current_status != STATUS_COMPLETED
        has_artifact = step_name in STEP_ARTIFACT_MAP

        if has_artifact:
            col_s, col_d, col_single, col_v = st.columns([7, 0.6, 0.6, 1])
        else:
            col_s, col_d, col_single = st.columns([7, 0.6, 0.6])
            col_v = None

        if is_done:
            dur = m.get("duration_seconds")
            is_skipped = m.get("last_error") == "SKIPPED"
            retries = m.get("retry_count", 0)
            retry_str = (
                f" | \u26a0\ufe0f {retries} retr{'y' if retries == 1 else 'ies'}"
                if retries > 0
                else ""
            )
            with col_s:
                if is_skipped:
                    st.markdown(f"\u23ed\ufe0f **{step_desc}** *(skipped)*")
                else:
                    dur_str = f" *(took {_fmt_elapsed(int(dur))})*" if dur else ""
                    st.markdown(f"\u2705 **{step_desc}**{dur_str}{retry_str}")

        elif is_current:
            retry_count = m.get("retry_count", 0)
            last_error = m.get("last_error") or ""
            t_started = m.get("time_started")
            elapsed = int(now - t_started) if t_started else 0

            if current_status in (STATUS_ERROR, STATUS_ABORTED):
                icon = "❌"
            elif retry_count > 0:
                icon = "🔄"
            else:
                icon = "➡️"

            elapsed_str = f" ⏱ {_fmt_elapsed(elapsed)} elapsed" if elapsed else ""
            retry_str = f" &nbsp;⚠️ Retry {retry_count}/3" if retry_count > 0 else ""
            running_dot = (
                live_dot()
                if current_status in (STATUS_RUNNING, STATUS_STARTING)
                else ""
            )
            with col_s:
                st.markdown(
                    f"{running_dot}{icon} **{step_desc}** &nbsp;{status_badge(current_status)}"
                    f"<span style='font-size:0.8rem;color:#64748b;'>{retry_str}{elapsed_str}</span>",
                    unsafe_allow_html=True,
                )
                if (
                    current_status != STATUS_COMPLETED
                    and last_error
                    and retry_count > 0
                ):
                    st.caption(f"Last error: {last_error}")
                if current_status in (STATUS_ERROR, STATUS_ABORTED) and last_error:
                    st.error(f"Step failed: {last_error}")
        else:
            with col_s:
                st.markdown(f"⏳ **{step_desc}** — *PENDING*")

        with col_d:
            if step_name != STEP_COMPLETED:
                if st.button("🏍️", key=f"debug_{step_name}", help="Run from this step"):
                    rerun_from_step(project_id, step_name)
                    st.session_state["_transitioning"] = True
                    st.rerun()

        with col_single:
            if step_name != STEP_COMPLETED:
                if st.button(
                    "🎯",
                    key=f"single_{step_name}",
                    help="Run only this step, then pause",
                ):
                    rerun_single_step(project_id, step_name)
                    st.session_state["_transitioning"] = True
                    st.rerun()

        if col_v is not None:
            with col_v:
                if st.button("🖼️", key=f"artifact_{step_name}"):
                    navigate_to_artifact(step_name, project_id)

    st.divider()
    st.markdown('<div class="ags-section-label">Controls</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        if current_status in (STATUS_STARTING, STATUS_RUNNING, STATUS_PAUSED):
            if st.button("🛑 Abort"):
                requests.post(
                    f"{API_URL}/projects/{project_id}/command",
                    params={"command": CMD_ABORT},
                )
                st.rerun()
        elif current_status in (STATUS_ABORTED, STATUS_ERROR):
            if st.button("🔄 Retry"):
                requests.post(
                    f"{API_URL}/projects/{project_id}/command",
                    params={"command": CMD_RETRY},
                )
                st.session_state["_transitioning"] = True
                st.rerun()
        elif current_status == STATUS_COMPLETED:
            st.success("🎉 Generation Complete!")
            if st.button("▶️ Play"):
                navigate_to("game")
            if st.button("🗺️ Level Editor", type="primary"):
                navigate_to("editor")
            st.link_button(
                "📦 Export Game (.zip)",
                f"{PUBLIC_API_URL}/projects/{project_id}/export",
            )

    with c2:
        if current_status == STATUS_RUNNING:
            if st.button("⏸️ Pause before next step"):
                requests.post(
                    f"{API_URL}/projects/{project_id}/command",
                    params={"command": CMD_PAUSE},
                )
                st.rerun()
        elif current_status == STATUS_PAUSED:
            if st.button("▶️ Resume"):
                requests.post(
                    f"{API_URL}/projects/{project_id}/command",
                    params={"command": CMD_RUN},
                )
                st.session_state["_transitioning"] = True
                st.rerun()

    if st.button("Home"):
        navigate_to("landing")

    # Auto-refresh logic:
    # - When RUNNING or STARTING: poll every 10 s (normal pipeline progress)
    # - When _transitioning: the user just triggered an action; poll every 2 s
    #   until the backend confirms RUNNING/STARTING, then switch to normal polling
    if current_status in (STATUS_RUNNING, STATUS_STARTING):
        st.session_state.pop("_transitioning", None)  # No longer needed
        time.sleep(10)
        st.rerun()
    elif st.session_state.get("_transitioning"):
        time.sleep(2)
        st.rerun()
