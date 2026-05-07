from database import (
    record_step_retry,
    set_project_step,
    record_step_start,
    record_step_end,
)
from shared.models import GraphState
from shared.constants import STEP_ART_CLEANUP
from docker_manager import ContainerManager
from shared.artifacts import get_image_path


def art_cleanup_node(state: GraphState) -> GraphState:
    from image_utils import (
        clean_asset,
    )  # local import to avoid cpu spike on startup (bgrem and numpy imports are heavy)

    project_id = state["project_id"]
    game_type = state["type"]
    print(f"[{project_id}, {game_type}] Art Cleanup...")

    set_project_step(project_id, STEP_ART_CLEANUP)
    t_start = record_step_start(project_id, STEP_ART_CLEANUP)

    ContainerManager.stop_workers()

    try:
        # Run background removal / post-processing on generated images

        IMAGES_PATH = get_image_path(project_id)
        OUTPUT_PREFIX = "_alpha"

        files_to_process = [
            f
            for f in IMAGES_PATH.glob("*.png")
            if (f.name.startswith("item_") or f.name.startswith("actor_"))
            and OUTPUT_PREFIX not in f.name
        ]

        if not files_to_process:
            raise Exception(
                "No generated item_*.png or actor_*.png files found for cleanup"
            )

        for item_path in files_to_process:
            # Create new filename: e.g., item_fuse.png -> item_fuse_alpha.png
            output_name = item_path.stem + OUTPUT_PREFIX + ".png"
            output_path = item_path.parent / output_name

            print(f"--- Cleaning: {item_path.name} -> {output_name}")

            clean_asset(item_path, output_path)

        duration = record_step_end(project_id, STEP_ART_CLEANUP, t_start)
        print(f"[{project_id}] Cleanup took {duration:.1f}s")
    except Exception as e:
        record_step_end(project_id, STEP_ART_CLEANUP, t_start)
        record_step_retry(project_id, STEP_ART_CLEANUP, str(e))
        raise  # RetryPolicy retries the full node

    return state
