from database import record_step_end, record_step_start, set_project_step
from shared.models import GraphState
from shared.constants import STEP_COMPLETED
from docker_manager import ContainerManager


def completed_node(state: GraphState) -> GraphState:
    project_id = state["project_id"]
    game_type = state["type"]
    print(f"[{project_id}, {game_type}] Generation Complete!")

    set_project_step(project_id, STEP_COMPLETED)
    t_start = record_step_start(project_id, STEP_COMPLETED)

    # Final cleanup of any workers/containers
    ContainerManager.stop_workers()

    duration = record_step_end(project_id, STEP_COMPLETED, t_start)
    print(f"[{project_id}, {game_type}] Generation complete took {duration:.1f}s")
    return state
