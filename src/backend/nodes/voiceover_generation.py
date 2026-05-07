import os
import time
import requests

from database import (
    record_step_retry,
    record_step_start,
    set_project_step,
    record_step_end,
)
from shared.models import GraphState
from shared.constants import STEP_VOICEOVER_GENERATION, WORKER_VOICEOVER
from docker_manager import ContainerManager

AUDIO_URL = os.getenv("AUDIO_URL", "http://audio_engine:8091")
VOXCPM_POLL_INTERVAL = 5  # seconds between status checks
VOXCPM_CALL_TIMEOUT = 10  # seconds for API call timeouts
VOXCPM_STARTUP_TIMEOUT = (
    120  # seconds to wait for the container API to become reachable
)


def _wait_for_api(timeout: int) -> None:
    """Block until the audio engine API responds or timeout is reached."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(f"{AUDIO_URL}/status", timeout=3)
            return
        except requests.RequestException:
            time.sleep(3)
    raise TimeoutError(f"Audio engine did not become reachable within {timeout}s")


def voiceover_generation_node(state: GraphState) -> GraphState:
    project_id = state["project_id"]
    game_type = state["type"]
    print(f"[{project_id}, {game_type}] Generating Voiceovers...")

    set_project_step(project_id, STEP_VOICEOVER_GENERATION)
    t_start = record_step_start(project_id, STEP_VOICEOVER_GENERATION)

    ContainerManager.start_worker(WORKER_VOICEOVER)

    try:
        print(f"[{project_id}] Waiting for audio engine at {AUDIO_URL}...")
        _wait_for_api(VOXCPM_STARTUP_TIMEOUT)

        resp = requests.post(
            f"{AUDIO_URL}/run/{project_id}", timeout=VOXCPM_CALL_TIMEOUT
        )
        resp.raise_for_status()
        print(f"[{project_id}] Voiceover job started, polling for completion...")

        while True:
            time.sleep(VOXCPM_POLL_INTERVAL)
            status_resp = requests.get(
                f"{AUDIO_URL}/status", timeout=VOXCPM_CALL_TIMEOUT
            )
            status_resp.raise_for_status()
            if not status_resp.json().get("running", False):
                break
            print(f"[{project_id}] Voiceover still running...")

        duration = record_step_end(project_id, STEP_VOICEOVER_GENERATION, t_start)
        print(f"[{project_id}, {game_type}] Voiceover generation took {duration:.1f}s")
    except Exception as e:
        record_step_end(project_id, STEP_VOICEOVER_GENERATION, t_start)
        record_step_retry(project_id, STEP_VOICEOVER_GENERATION, str(e))
        raise

    return state
