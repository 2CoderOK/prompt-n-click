import json
import html as html_lib
from pathlib import Path

import streamlit as st

from shared.constants import (
    PIPELINE_STEPS,
    STEP_ART_GENERATION,
    STEP_ART_CLEANUP,
    STEP_VOICEOVER_COMPRESSION,
)
from routes.utils import (
    PROJECTS_ROOT,
    STEP_ARTIFACT_MAP,
    navigate_to,
    render_settings_button,
)


def _artifact_guard(page_key: str = "artifact"):
    """Return (project_id, step) from session state or URL params, or render a warning."""
    project_id = st.session_state.get("artifact_project_id") or st.query_params.get(
        "project_id"
    )
    step = st.session_state.get("artifact_step") or st.query_params.get("step")
    if not project_id or not step:
        st.warning("No artifact selected.")
        if st.button("← Back"):
            navigate_to("landing")
        return None, None
    # Ensure session state is always populated (covers direct URL access)
    st.session_state.artifact_project_id = project_id
    st.session_state.artifact_step = step
    return project_id, step


def artifact_md_page() -> None:
    render_settings_button()
    project_id, step = _artifact_guard()
    if not project_id:
        return

    mapping = STEP_ARTIFACT_MAP.get(step, {})
    filename = mapping.get("file", "")
    filepath = PROJECTS_ROOT / project_id / filename
    step_label = next((s["desc"] for s in PIPELINE_STEPS if s["name"] == step), step)

    st.markdown(f"<h1>📄 {html_lib.escape(step_label)}</h1>", unsafe_allow_html=True)
    st.caption(f"File: `{filename}`  |  Project: `{project_id[:8]}...`")

    if not filepath.exists():
        st.error(f"Artifact not found: `{filename}`")
    else:
        content = filepath.read_text(encoding="utf-8")
        view_mode = st.radio(
            "View mode",
            ["Rendered", "Raw text"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if st.button("← Back to Project"):
            navigate_to("progress")

        st.divider()
        if view_mode == "Rendered":
            st.markdown(content)
        else:
            st.text_area(
                "Raw content", value=content, height=600, label_visibility="collapsed"
            )

    st.divider()
    if st.button("← Back to Project", key="back_to_progress_from_md"):
        navigate_to("progress")


def artifact_json_page() -> None:
    render_settings_button()
    project_id, step = _artifact_guard()
    if not project_id:
        return

    mapping = STEP_ARTIFACT_MAP.get(step, {})
    filenames = mapping.get("files", [])
    step_label = next((s["desc"] for s in PIPELINE_STEPS if s["name"] == step), step)

    st.markdown(f"<h1>📋 {html_lib.escape(step_label)}</h1>", unsafe_allow_html=True)
    st.caption(f"Project: `{project_id[:8]}...`")

    view_mode = st.radio(
        "View mode",
        ["Interactive", "Raw text"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if st.button("← Back to Project"):
        navigate_to("progress")

    st.divider()

    for filename in filenames:
        filepath = PROJECTS_ROOT / project_id / filename
        st.subheader(f"`{filename}`")
        if not filepath.exists():
            st.warning(f"File not found: `{filename}`")
            continue
        content = filepath.read_text(encoding="utf-8")
        if view_mode == "Interactive":
            try:
                st.json(json.loads(content))
            except json.JSONDecodeError:
                st.error("Invalid JSON — showing raw text")
                st.code(content, language="json")
        else:
            st.text_area(
                f"Raw: {filename}",
                value=content,
                height=400,
                label_visibility="collapsed",
            )
        st.divider()

    if st.button("← Back to Project", key="back_to_progress_from_json"):
        navigate_to("progress")


def artifact_images_page() -> None:
    render_settings_button()
    project_id, step = _artifact_guard()
    if not project_id:
        return

    mapping = STEP_ARTIFACT_MAP.get(step, {})
    jobs_file = mapping.get("jobs_file", "art_jobs.json")
    jobs_path = PROJECTS_ROOT / project_id / jobs_file
    step_label = next((s["desc"] for s in PIPELINE_STEPS if s["name"] == step), step)

    st.markdown(f"<h1>🖼️ {html_lib.escape(step_label)}</h1>", unsafe_allow_html=True)
    st.caption(f"Project: `{project_id[:8]}...`")

    if not jobs_path.exists():
        st.error(f"Jobs file not found: `{jobs_file}`")
        if st.button("← Back to Project"):
            navigate_to("progress")
        return

    if st.button("← Back to Project"):
        navigate_to("progress")

    art_jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    project_img_path = PROJECTS_ROOT / project_id / "img"

    sections = []
    if step == STEP_ART_GENERATION:
        sections.append(("Backgrounds", art_jobs.get("backgrounds", [])))
    sections.append(("Actors", art_jobs.get("actors", [])))
    sections.append(("Items", art_jobs.get("items", [])))

    for section_label, assets in sections:
        if not assets:
            continue
        st.subheader(section_label)
        cols = st.columns(3)
        for idx, asset in enumerate(assets):
            asset_id = asset.get("id", f"asset_{idx}")
            prompt = asset.get("prompt", "")
            img_path = project_img_path / f"{asset_id}.png"
            if step == STEP_ART_CLEANUP and section_label != "Backgrounds":
                img_path = project_img_path / f"{asset_id}_alpha.png"
            with cols[idx % 3]:
                if img_path.exists():
                    st.image(img_path)
                else:
                    st.warning(f"Missing: `{img_path.name}`")
                st.caption(f"`{asset_id}`")
                with st.expander("Show prompt"):
                    st.text(prompt)
        st.divider()

    if st.button("← Back to Project", key="back_to_progress_from_images"):
        navigate_to("progress")


def artifact_audio_page() -> None:
    render_settings_button()
    project_id, step = _artifact_guard()
    if not project_id:
        return

    mapping = STEP_ARTIFACT_MAP.get(step, {})
    jobs_file = mapping.get("jobs_file", "voiceover_jobs.json")
    jobs_path = PROJECTS_ROOT / project_id / jobs_file
    step_label = next((s["desc"] for s in PIPELINE_STEPS if s["name"] == step), step)

    st.markdown(f"<h1>🔊 {html_lib.escape(step_label)}</h1>", unsafe_allow_html=True)
    st.caption(f"Project: `{project_id[:8]}...`")

    if not jobs_path.exists():
        st.error(f"Jobs file not found: `{jobs_file}`")
        if st.button("← Back to Project"):
            navigate_to("progress")
        return

    vo_data = json.loads(jobs_path.read_text(encoding="utf-8"))
    audio_path = PROJECTS_ROOT / project_id / "audio"
    jobs = vo_data.get("jobs", [])

    if not jobs:
        st.info("No voiceover jobs found in file.")
    else:
        if st.button("← Back to Project"):
            navigate_to("progress")

        for job in jobs:
            filename = job.get("file", "")
            if step == STEP_VOICEOVER_COMPRESSION:
                filename = Path(filename).with_suffix(".mp3").name
            file_path = audio_path / filename
            st.subheader(f"🎙️ `{filename}`")
            if filename and file_path.exists():
                st.audio(file_path.read_bytes(), format="audio/wav")
            else:
                st.warning(f"Audio file not found: `{filename}`")
            with st.expander("Show info"):
                st.markdown(f"**Voice Desc:** {job.get('voice_desc', 'N/A')}")
                st.markdown(f"**Line:** {job.get('voice_prompt', 'N/A')}")
                if job.get("ref_wav"):
                    st.markdown(
                        f"**Reference file:** `{job.get('ref_wav')}` — _{job.get('ref_prompt', '')}_"
                    )
            st.divider()

    if st.button("← Back to Project", key="back_to_progress_from_audio"):
        navigate_to("progress")


def artifact_music_page() -> None:
    render_settings_button()
    project_id, step = _artifact_guard()
    if not project_id:
        return

    tracks_path = PROJECTS_ROOT / project_id / "music_tracks.json"
    audio_path = PROJECTS_ROOT / project_id / "audio"

    st.markdown("<h1>🎵 Music Selection & Download</h1>", unsafe_allow_html=True)
    st.caption(f"Project: `{project_id[:8]}...`")

    if not tracks_path.exists():
        st.error("music_tracks.json not found — run the Music Downloader step first.")
        if st.button("← Back to Project"):
            navigate_to("progress")
        return

    if st.button("← Back to Project"):
        navigate_to("progress")

    data = json.loads(tracks_path.read_text(encoding="utf-8"))
    tracks = data.get("tracks", [])

    if not tracks:
        st.info("No music tracks were selected for this project.")
    else:
        st.markdown(f"**{len(tracks)} track(s) downloaded**")
        st.divider()
        for track in tracks:
            title = track.get("title", "Unknown")
            filename = track.get("filename", "")
            page_url = track.get("page_url", "")
            license_text = track.get("license", "")
            attribution = track.get("attribution", "")
            description = track.get("description", "")
            file_path = audio_path / filename

            col_info, col_play = st.columns([3, 1])
            with col_info:
                if page_url:
                    st.markdown(f"### [{html_lib.escape(title)}]({page_url})")
                else:
                    st.markdown(f"### {html_lib.escape(title)}")
                st.caption(f"`{filename}`")
                if description:
                    st.markdown(description)
                meta_parts = []
                if license_text:
                    meta_parts.append(f"**License:** {html_lib.escape(license_text)}")
                if attribution:
                    meta_parts.append(
                        f"**Attribution:** {html_lib.escape(attribution)}"
                    )
                if meta_parts:
                    st.markdown("  \n".join(meta_parts))
            with col_play:
                if filename and file_path.exists():
                    st.audio(file_path.read_bytes(), format="audio/ogg")
                else:
                    st.warning("File missing")
            st.divider()

    if st.button("← Back to Project", key="back_to_progress_from_music"):
        navigate_to("progress")
