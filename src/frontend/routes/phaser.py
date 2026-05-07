import streamlit as st
import streamlit.components.v1 as components

from routes.utils import (
    PROJECTS_ROOT,
    PUBLIC_API_URL,
    navigate_to,
    get_music_attribution,
)


def _phaser_guard(project_id: str | None) -> bool:
    """Return True if we can proceed; otherwise render error and return False."""
    if not project_id:
        st.warning("No project selected.")
        if st.button("← Home"):
            navigate_to("landing")
        return False

    config_path = PROJECTS_ROOT / project_id / "game_config.json"
    if not config_path.exists():
        st.error(
            "game_config.json not found for this project. "
            "Complete the Game Builder step first."
        )
        if st.button("← Home"):
            navigate_to("landing")
        return False

    return True


def editor_page() -> None:
    project_id = st.session_state.get("project_id")
    if not _phaser_guard(project_id):
        return

    # Override the global max-width/padding so the editor iframe has enough
    # horizontal room for the 1280px game canvas + 300px inspector panel.
    st.markdown(
        "<style>"
        ".block-container { max-width: 100% !important; padding-left: 8rem !important; padding-right: 4rem !important; }"
        "</style>",
        unsafe_allow_html=True,
    )

    if st.button("← Home", key="back_from_game"):
        navigate_to("landing")

    st.caption(f"Project: `{project_id}`  |  Editor powered by Phaser 3")
    PROJECT_TYPE = st.session_state.get("project_type", "point_and_click")
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Level Editor</title>
    <script src="https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js"></script>
    <style>
        body {{ margin: 0; background: #111; overflow-x: visible; overflow-y: hidden; min-width: 1580px; }}
        #game-container {{ width: 1280px; height: 920px; position: relative; }}
    </style>
</head>
<body>
    <div id="game-container"></div>
    <script>
        window.EDITOR_PROJECT_ID = "{project_id}";
        window.EDITOR_API_URL = "{PUBLIC_API_URL}";
        window.IS_EDITOR = true;
    </script>
    <script src="{PUBLIC_API_URL}/static/phaser/{PROJECT_TYPE}/init.js"></script>
    <script src="{PUBLIC_API_URL}/static/phaser/fx_system.js"></script>
    <script src="{PUBLIC_API_URL}/static/phaser/{PROJECT_TYPE}/editor.js"></script>
</body>
</html>"""

    components.html(html_content, height=960, scrolling=True)


def game_page() -> None:
    project_id = st.session_state.get("project_id")
    if not _phaser_guard(project_id):
        return

    if st.button("← Home", key="back_from_game"):
        navigate_to("landing")

    PROJECT_TYPE = st.session_state.get("project_type", "point_and_click")
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Game Player</title>
    <script src="https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js"></script>
    <style>
        body {{ margin: 0; background: #111; overflow: hidden; }}
        #game-container {{ width: 1280px; height: 720px; position: relative; }}
    </style>
</head>
<body>
    <div id="game-container"></div>
    <script>
        window.GAME_PROJECT_ID = "{project_id}";
        window.GAME_API_URL = "{PUBLIC_API_URL}";
        window.IS_EDITOR = false;
    </script>
    <script src="{PUBLIC_API_URL}/static/phaser/{PROJECT_TYPE}/init.js"></script>
    <script src="{PUBLIC_API_URL}/static/phaser/fx_system.js"></script>
    <script src="{PUBLIC_API_URL}/static/phaser/{PROJECT_TYPE}/game.js"></script>    
</body>
</html>"""

    components.html(html_content, height=760, scrolling=False)

    # Music attribution
    music_info = get_music_attribution(project_id)
    if music_info and music_info.get("attribution"):
        title = music_info["title"]
        page_url = music_info.get("page_url", "")
        license_text = music_info.get("license", "")
        attribution = music_info["attribution"]
        st.divider()
        st.caption(
            f"♪ Music: [{title}]({page_url})" if page_url else f"♪ Music: {title}"
        )
        if license_text:
            st.caption(f"License: {license_text}")
        st.caption(attribution)
