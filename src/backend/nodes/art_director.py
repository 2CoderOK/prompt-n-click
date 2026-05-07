import json
import os

from shared.models import GraphState, Project
from shared.constants import (
    STEP_ART_DIRECTOR,
    SKILL_ART_DIRECTOR,
)
from shared.artifacts import read_skill, read_text, write_text, write_json, read_json
from docker_manager import ContainerManager
from database import (
    engine,
    record_step_start,
    record_step_end,
    record_step_retry,
    set_project_step,
    get_project_llm_profile,
)
from sqlmodel import Session, select
from llamacpp_client import llamacpp_call, llamacpp_wait_until_loaded


def art_director_node(state: GraphState) -> GraphState:
    project_id = state["project_id"]
    game_type = state["type"]
    print(f"[{project_id}, {game_type}] STEP: Writing Art Prompts...")

    set_project_step(project_id, STEP_ART_DIRECTOR)
    t_start = record_step_start(project_id, STEP_ART_DIRECTOR)

    profile_id, context_size, llm_config = get_project_llm_profile(
        project_id, STEP_ART_DIRECTOR
    )
    ContainerManager.start_llamacpp_worker(llm_config, profile_id)
    LLAMACPP_URL = os.getenv("LLAMACPP_LLM_URL", "http://llamacpp:8090")
    print(
        f"[{project_id}, {game_type}] Waiting for LLM at {LLAMACPP_URL} to be ready..."
    )

    try:
        llamacpp_wait_until_loaded(
            LLAMACPP_URL, timeout=300
        )  # Give it 5 mins for huge models
    except Exception as e:
        record_step_end(project_id, STEP_ART_DIRECTOR, t_start)
        record_step_retry(project_id, STEP_ART_DIRECTOR, str(e))
        raise

    with Session(engine) as session:
        proj = session.exec(select(Project).where(Project.id == project_id)).first()

    skill_md = read_skill(game_type, SKILL_ART_DIRECTOR)
    system_prompt = (
        f"\n--- Start of Instruction:\n {skill_md} \n--- End of Instruction ---\n"
    )
    lore_md = read_text(project_id, "lore.md")
    lore_prompt = f"\n--- Start of Lore:\n {lore_md} \n--- End of Lore ---\n"
    user_prompt = f"You need to generate ART prompts in JSON format based on the following lore:\n {lore_prompt}"

    print(f"[{project_id}, {game_type}] Sending request to LLM at {LLAMACPP_URL}...")
    try:
        art_prompts = llamacpp_call(
            LLAMACPP_URL, system_prompt, user_prompt, context_size
        )

        if not art_prompts or len(art_prompts) < 100:
            print(f"LLM response too short or empty: '{art_prompts}'")
            raise ValueError(
                f"LLM response too short or empty: '{art_prompts}'"
            )  # Trigger a retry

        write_text(project_id, "art_jobs.json", art_prompts)
        print(
            f"[{project_id}, {game_type}] art_jobs.json written ({len(art_prompts)} chars)"
        )

        art_prompts_json = read_json(project_id, "art_jobs.json")

        # write cleaned up version of art prompts that only contains the fields needed for Game Builder
        art_prompts_json.pop("global_negative_prompt", None)

        # Helper to remove 'prompt' from dictionaries inside a list
        def remove_prompt_from_list(lst):
            for item in lst:
                if isinstance(item, dict):
                    item.pop("prompt", None)

        # Process known array keys in the JSON structure
        for key in ["backgrounds", "actors", "items"]:
            if key in art_prompts_json and isinstance(art_prompts_json[key], list):
                remove_prompt_from_list(art_prompts_json[key])

        write_json(project_id, "art_info.json", art_prompts_json)
        print(
            f"[{project_id}, {game_type}] art_info.json written ({len(json.dumps(art_prompts_json))} chars)"
        )

        duration = record_step_end(project_id, STEP_ART_DIRECTOR, t_start)
        print(f"[{project_id}, {game_type}] LLM call took {duration:.1f}s")
    except Exception as e:
        record_step_end(project_id, STEP_ART_DIRECTOR, t_start)
        record_step_retry(project_id, STEP_ART_DIRECTOR, str(e))
        raise  # RetryPolicy retries the full node

    return state
