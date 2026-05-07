from shared.models import GraphState, Project
from shared.constants import (
    COMFYUI_GENERATION_DELAY,
    COMFYUI_TIMEOUT,
    STEP_ART_GENERATION,
    WORKER_GFX,
    COMFYUI_MAX_RETRIES,
)
from shared.artifacts import read_workflow, read_json, write_image, WORKFLOWS_NODE_MAP
from docker_manager import ContainerManager
from database import (
    engine,
    record_step_start,
    record_step_end,
    record_step_retry,
    set_project_step,
)
from sqlmodel import Session, select
from comfyui_client import (
    comfyui_wait_until_loaded,
    queue_prompt,
    wait_for_image,
    download_image,
)
import os
import time
import random


def art_generation_node(state: GraphState) -> GraphState:
    project_id = state["project_id"]
    game_type = state["type"]
    print(f"[{project_id}, {game_type}] Generating Art...")

    set_project_step(project_id, STEP_ART_GENERATION)
    t_start = record_step_start(project_id, STEP_ART_GENERATION)

    ContainerManager.start_worker(WORKER_GFX)

    COMFYUI_URL = os.getenv("COMFYUI_URL", "http://comfyui:8188")
    print(
        f"[{project_id}, {game_type}] Waiting for ComfyUI at {COMFYUI_URL} to be ready..."
    )

    try:
        comfyui_wait_until_loaded(
            COMFYUI_URL, timeout=120
        )  # Give it 2 mins for huge models
    except Exception as e:
        record_step_end(project_id, STEP_ART_GENERATION, t_start)
        record_step_retry(project_id, STEP_ART_GENERATION, str(e))
        raise

    print(f"[{project_id}, {game_type}] ComfyUI is up and running at {COMFYUI_URL}...")
    try:
        workflow_asset_json = read_workflow("api_workflow_asset.json")
        workflow_bg_json = read_workflow("api_workflow_bg.json")
        art_jobs_json = read_json(project_id, "art_jobs.json")

        print("\n--- GENERATING BACKGROUNDS ---")
        for bg in art_jobs_json.get("backgrounds", []):
            retries = 0

            while retries < COMFYUI_MAX_RETRIES:
                print(f"[{project_id}, {game_type}] Processing: {bg['id']}")

                # Inject data into the Background Workflow
                wf = workflow_bg_json.copy()

                # Inject Prompts
                wf[WORKFLOWS_NODE_MAP["bg"]["positive_prompt_node"]]["inputs"][
                    "text"
                ] = bg["prompt"]

                wf[WORKFLOWS_NODE_MAP["bg"]["seed_node"]]["inputs"]["seed"] = (
                    random.randint(1, 1125899906842624)
                )

                # Force the filename prefix so we know what it is
                wf[WORKFLOWS_NODE_MAP["bg"]["save_image_node"]]["inputs"][
                    "filename_prefix"
                ] = bg["id"]

                try:
                    # Send to ComfyUI
                    prompt_id = queue_prompt(COMFYUI_URL, wf)
                    if prompt_id:
                        filename = wait_for_image(
                            COMFYUI_URL, prompt_id, COMFYUI_TIMEOUT
                        )
                        image_data = download_image(COMFYUI_URL, filename)
                        write_image(project_id, f"{bg['id']}.png", image_data)

                    time.sleep(
                        COMFYUI_GENERATION_DELAY
                    )  # wait for workflow to unload (slow hardware adjustment ;) )

                    break  # Break out of retry loop if successful
                except Exception as e:
                    retries += 1
                    print(
                        f"[{project_id}, {game_type}] Error processing {bg['id']}: {e}. Retry {retries}/{COMFYUI_MAX_RETRIES}"
                    )
                    if retries >= COMFYUI_MAX_RETRIES:
                        raise Exception(
                            f"Failed to generate {bg['id']} after {COMFYUI_MAX_RETRIES} retries."
                        )

        # 3. Process Actors and Items (1024x1024 Workflow)
        print(f"\n[{project_id}, {game_type}] --- GENERATING ACTORS & ITEMS ---")
        assets = art_jobs_json.get("actors", []) + art_jobs_json.get("items", [])

        for asset in assets:
            retries = 0

            while retries < COMFYUI_MAX_RETRIES:
                try:
                    print(f"[{project_id}, {game_type}] Processing: {asset['id']}")

                    # Inject data into the Asset Workflow
                    wf = workflow_asset_json.copy()

                    # Inject Prompts
                    wf[WORKFLOWS_NODE_MAP["asset"]["positive_prompt_node"]]["inputs"][
                        "text"
                    ] = asset["prompt"]

                    wf[WORKFLOWS_NODE_MAP["asset"]["seed_node"]]["inputs"]["seed"] = (
                        random.randint(1, 1125899906842624)
                    )

                    # Force the filename prefix
                    wf[WORKFLOWS_NODE_MAP["asset"]["save_image_node"]]["inputs"][
                        "filename_prefix"
                    ] = asset["id"]

                    # Send to ComfyUI
                    prompt_id = queue_prompt(COMFYUI_URL, wf)
                    if prompt_id:
                        filename = wait_for_image(
                            COMFYUI_URL, prompt_id, COMFYUI_TIMEOUT
                        )
                        image_data = download_image(COMFYUI_URL, filename)
                        write_image(project_id, f"{asset['id']}.png", image_data)

                    time.sleep(
                        COMFYUI_GENERATION_DELAY
                    )  # wait for workflow to unload (slow hardware adjustment ;) )

                    break  # Break out of retry loop if successful
                except Exception as e:
                    retries += 1
                    print(
                        f"[{project_id}, {game_type}] Error processing {asset['id']}: {e}. Retry {retries}/{COMFYUI_MAX_RETRIES}"
                    )
                    if retries >= COMFYUI_MAX_RETRIES:
                        raise Exception(
                            f"Failed to generate {asset['id']} after {COMFYUI_MAX_RETRIES} retries."
                        )

        duration = record_step_end(project_id, STEP_ART_GENERATION, t_start)
        print(f"[{project_id}, {game_type}] LLM call took {duration:.1f}s")
    except Exception as e:
        record_step_end(project_id, STEP_ART_GENERATION, t_start)
        record_step_retry(project_id, STEP_ART_GENERATION, str(e))
        raise  # RetryPolicy retries the full node

    return state
