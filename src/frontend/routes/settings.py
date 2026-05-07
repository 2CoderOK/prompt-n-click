import streamlit as st
import requests

from routes.utils import API_URL, navigate_to


def settings_page() -> None:
    _, col_back = st.columns([10, 1])
    with col_back:
        if st.button("✖", help="Close Settings"):
            navigate_to(st.session_state.get("prev_page", "landing"))

    st.title("⚙️ Settings")
    st.markdown(
        '<div class="ags-section-label">Text LLM Profiles</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Manage llamacpp parameter profiles. The **default** profile is used when no "
        "specific profile is selected and cannot be deleted."
    )

    try:
        res = requests.get(f"{API_URL}/llm-profiles")
        res.raise_for_status()
        profiles = res.json().get("profiles", [])
    except Exception as e:
        st.error(f"Failed to load profiles: {e}")
        profiles = []

    st.divider()

    if profiles:
        for prof in profiles:
            pid = prof["id"]
            is_default = prof["is_default"]
            badge = " ⭐ DEFAULT" if is_default else ""
            with st.expander(f"**{prof['name']}**{badge}  (id: {pid})", expanded=False):
                edit_name = st.text_input("Name", value=prof["name"], key=f"name_{pid}")
                edit_params = st.text_area(
                    "Parameters",
                    value=prof["parameters"],
                    height=120,
                    key=f"params_{pid}",
                    help="Full llamacpp CLI parameter string.",
                )
                # Context size dropdown
                CONTEXT_OPTIONS = [8192, 16384, 24576, 32768, 65536, 131072]
                try:
                    current_ctx = int(prof.get("context_size", 8192))
                except Exception:
                    current_ctx = 8192
                ctx_labels = [f"{v // 1024}K" for v in CONTEXT_OPTIONS]
                idx = (
                    CONTEXT_OPTIONS.index(current_ctx)
                    if current_ctx in CONTEXT_OPTIONS
                    else 0
                )
                edit_context = st.selectbox(
                    "Context Size", ctx_labels, index=idx, key=f"ctx_{pid}"
                )
                # convert back to int
                edit_context_val = CONTEXT_OPTIONS[ctx_labels.index(edit_context)]
                st.caption(
                    "Selected context will be appended automatically to the command; do NOT include --ctx-size manually."
                )
                col_save, col_default, col_del = st.columns([2, 2, 1])

                with col_save:
                    if st.button("💾 Save", key=f"save_{pid}"):
                        try:
                            r = requests.put(
                                f"{API_URL}/llm-profiles/{pid}",
                                json={
                                    "name": edit_name,
                                    "parameters": edit_params,
                                    "context_size": edit_context_val,
                                },
                            )
                            r.raise_for_status()
                            st.success("Saved.")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Error: {ex}")

                with col_default:
                    if not is_default:
                        if st.button("⭐ Set as Default", key=f"default_{pid}"):
                            try:
                                r = requests.post(
                                    f"{API_URL}/llm-profiles/{pid}/set-default"
                                )
                                r.raise_for_status()
                                st.success("Default updated.")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Error: {ex}")
                    else:
                        st.info("This is the default profile.")

                with col_del:
                    if not is_default:
                        if st.button("🗑️ Delete", key=f"del_{pid}", type="secondary"):
                            try:
                                r = requests.delete(f"{API_URL}/llm-profiles/{pid}")
                                r.raise_for_status()
                                st.success("Deleted.")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Error: {ex}")
                    else:
                        st.caption("(default — protected)")
    else:
        st.info("No profiles found.")

    st.divider()
    st.markdown(
        '<div class="ags-section-label">➕ Add New Profile</div>',
        unsafe_allow_html=True,
    )
    with st.form("new_profile_form", clear_on_submit=True):
        new_name = st.text_input(
            "Profile Name",
            placeholder="e.g. Qwen3.5-35B-A3B-Q4_K_M, 14 layers, 8K context",
        )
        new_params = st.text_area(
            "Parameters",
            height=120,
            placeholder=(
                "-m /usr/local/ai/models/Qwen3.5-35B-A3B-Q4_K_M.gguf"
                " --host 0.0.0.0 --port 8090 -ngl 12 -fa on"
                " -np 1 -t 8 --cache-type-k q4_0 --cache-type-v q4_0"
            ),
            help="Full llamacpp CLI parameter string.",
        )
        CONTEXT_OPTIONS = [8192, 16384, 24576, 32768, 65536, 131072]
        ctx_labels = [f"{v // 1024}K" for v in CONTEXT_OPTIONS]
        new_context_idx = 0
        new_context = st.selectbox(
            "Context Size", ctx_labels, index=new_context_idx, key="new_ctx"
        )
        new_context_val = CONTEXT_OPTIONS[ctx_labels.index(new_context)]
        st.caption(
            "Selected context will be appended automatically to the command; do NOT include --ctx-size manually."
        )
        new_default = st.checkbox("Set as default", value=False)
        submitted = st.form_submit_button("Add Profile", type="primary")
        if submitted:
            if not new_name.strip():
                st.error("Profile name is required.")
            elif not new_params.strip():
                st.error("Parameters are required.")
            else:
                try:
                    r = requests.post(
                        f"{API_URL}/llm-profiles",
                        json={
                            "name": new_name.strip(),
                            "parameters": new_params.strip(),
                            "is_default": new_default,
                            "context_size": new_context_val,
                        },
                    )
                    r.raise_for_status()
                    st.success(f"Profile '{new_name}' created.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error: {ex}")
