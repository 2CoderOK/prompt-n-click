import json
import time

from shared.models import GraphState, Project
from shared.constants import (
    STEP_GAME_BUILDER,
    SKILL_GAME_BUILDER,
)
from shared.artifacts import (
    cleanup_json_from_llm,
    read_json,
    read_skill,
    read_text,
    write_text,
    write_json,
)
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
from nodes.game_type_registry import (
    get_asset_config_generator,
)
import os


def game_builder_node(state: GraphState) -> GraphState:
    project_id = state["project_id"]
    game_type = state["type"]
    print(f"[{project_id}, {game_type}] Building Game Config...")

    set_project_step(project_id, STEP_GAME_BUILDER)
    t_start = record_step_start(project_id, STEP_GAME_BUILDER)

    profile_id, context_size, llm_config = get_project_llm_profile(
        project_id, STEP_GAME_BUILDER
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
        record_step_end(project_id, STEP_GAME_BUILDER, t_start)
        record_step_retry(project_id, STEP_GAME_BUILDER, str(e))
        raise

    skill_md = read_skill(game_type, SKILL_GAME_BUILDER)
    system_prompt = (
        f"\n--- Start of Instruction:\n {skill_md} \n--- End of Instruction ---\n"
    )
    lore_md = read_text(project_id, "lore.md")
    lore_prompt = f"\n--- Start of Lore:\n {lore_md} \n--- End of Lore ---\n"

    art_info_json = read_json(project_id, "art_info.json")
    art_info_prompt = f"\n--- Start of Art Info:\n {json.dumps(art_info_json)} \n--- End of Art Info ---\n"

    voiceover_md = (
        read_text(project_id, "voiceover.md") if not state.get("no_voiceover") else ""
    )

    generate_asset_config = get_asset_config_generator(game_type)

    assets_config_json = generate_asset_config(voiceover_md, art_info_json)

    write_json(project_id, "assets_config.json", assets_config_json)
    assets_config_text = json.dumps(assets_config_json)
    print(
        f"[{project_id}, {game_type}] assets_config.json written ({len(assets_config_text)} chars)"
    )

    assets_config_prompt = f"\n--- Start of Assets Config:\n {assets_config_text} \n--- End of Assets Config ---\n"

    user_prompt = f"You need to generate Game config in JSON format based on the lore and assets_config.json and art_info.json info:\n {lore_prompt} \n {assets_config_prompt} \n {art_info_prompt}"
    print(f"[{project_id}, {game_type}] Sending request to LLM at {LLAMACPP_URL}...")
    try:
        game_config_raw = llamacpp_call(
            LLAMACPP_URL, system_prompt, user_prompt, context_size
        )

        if not game_config_raw or len(game_config_raw) < 100:
            print(f"LLM response too short or empty: '{game_config_raw}'")
            raise ValueError(
                f"LLM response too short or empty: '{game_config_raw}'"
            )  # Trigger a retry

        # Clean up and parse — raise ValueError on invalid JSON to trigger retry
        game_config_cleaned = cleanup_json_from_llm(game_config_raw)
        try:
            config_dict = json.loads(game_config_cleaned)
        except json.JSONDecodeError as je:
            # save the raw output for debugging with timestamp in filename
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            debug_filename = f"invalid_raw_game_config_{timestamp}.txt"
            write_text(project_id, debug_filename, game_config_raw)
            raise ValueError(f"LLM output is not valid JSON: {je}")

        write_json(project_id, "game_config.json", config_dict)
        print(
            f"[{project_id}, {game_type}] game_config.json written ({len(game_config_cleaned)} chars)"
        )

        duration = record_step_end(project_id, STEP_GAME_BUILDER, t_start)
        print(f"[{project_id}, {game_type}] LLM call took {duration:.1f}s")
    except Exception as e:
        record_step_end(project_id, STEP_GAME_BUILDER, t_start)
        record_step_retry(project_id, STEP_GAME_BUILDER, str(e))
        raise  # RetryPolicy retries the full node

    return state
