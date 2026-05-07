import os
import sqlite3
from pathlib import Path
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import RetryPolicy
from sqlmodel import Session, select

from shared.models import Project, ProjectStepMetrics, GraphState
from shared.constants import (
    CMD_ABORT,
    CMD_PAUSE,
    CMD_RUN,
    GAME_TYPE_POINT_AND_CLICK,
    STATUS_ABORTED,
    STATUS_COMPLETED,
    STATUS_ERROR,
    STATUS_PAUSED,
    STATUS_RUNNING,
    STEP_ART_CLEANUP,
    STEP_ART_DIRECTOR,
    STEP_ART_GENERATION,
    STEP_COMPLETED,
    STEP_GAME_BUILDER,
    STEP_GAME_DESIGN,
    STEP_INVALIDATES,
    STEP_MUSIC_DOWNLOADER,
    STEP_ORDER,
    STEP_SCRIPT_WRITER,
    STEP_VOICEOVER_COMPRESSION,
    STEP_VOICEOVER_GENERATION,
)
from database import engine, FILE_PATH, record_step_skipped, set_project_step
from nodes.game_designer import game_designer_node
from nodes.art_director import art_director_node
from nodes.script_writer import scriptwriter_node
from nodes.game_builder import game_builder_node
from nodes.art_generation import art_generation_node
from nodes.art_cleanup import art_cleanup_node
from nodes.voiceover_generation import voiceover_generation_node
from nodes.voiceover_compression import voiceover_compression_node
from nodes.music_downloader import music_downloader_node
from nodes.completed import completed_node


def _reset_dependent_steps(project_id: str, step_name: str) -> None:
    """Delete metrics for step_name and every step whose output depends on it.

    Steps that are NOT invalidated keep their completed metrics, so the skip
    wrapper can skip them when running in selective mode.
    """
    steps_to_reset = [step_name] + STEP_INVALIDATES.get(step_name, [])
    with Session(engine) as session:
        for step in steps_to_reset:
            row = session.exec(
                select(ProjectStepMetrics).where(
                    ProjectStepMetrics.project_id == project_id,
                    ProjectStepMetrics.step_name == step,
                )
            ).first()
            if row:
                session.delete(row)
        session.commit()
    print(f"[{project_id}] Dependency reset — cleared metrics for: {steps_to_reset}")


# ==========================================
# SKIP WRAPPER
# Wraps every node so that, in selective mode (run-from-step), steps whose
# metrics record is still intact (duration_seconds is not None) are skipped.
# When single_step mode is active, injects CMD_PAUSE into the returned state
# after the first node that actually executes, causing the router to halt.
# ==========================================

# Maps step names to the GraphState flag that causes them to be skipped.
_STEP_SKIP_FLAGS: dict[str, str] = {
    STEP_SCRIPT_WRITER: "no_voiceover",
    STEP_VOICEOVER_GENERATION: "no_voiceover",
    STEP_VOICEOVER_COMPRESSION: "no_voiceover",
    STEP_MUSIC_DOWNLOADER: "no_music",
}


def _make_skippable(step_name: str, node_fn):
    def wrapper(state: GraphState) -> GraphState:
        project_id = state["project_id"]

        # Config-driven skip (no_voiceover / no_music)
        skip_flag = _STEP_SKIP_FLAGS.get(step_name)
        if skip_flag and state.get(skip_flag, False):
            print(f"[{project_id}] Skipping {step_name} ({skip_flag}=True)")
            record_step_skipped(project_id, step_name)
            set_project_step(project_id, step_name)
            return state

        # Selective skip (run-from-step mode): step already has a valid metric
        if state.get("selective", False):
            with Session(engine) as session:
                row = session.exec(
                    select(ProjectStepMetrics).where(
                        ProjectStepMetrics.project_id == project_id,
                        ProjectStepMetrics.step_name == step_name,
                    )
                ).first()
                if row and row.duration_seconds is not None:
                    print(
                        f"[{project_id}] Skipping {step_name} (up-to-date, selective mode)"
                    )
                    return state  # Skip — state unchanged, pipeline continues

        result = node_fn(state)

        # single-step mode — pause the graph after this step executes
        if state.get("single_step", False):
            return {**result, "command": CMD_PAUSE}

        return result

    wrapper.__name__ = f"{step_name}_skippable"
    return wrapper


# ==========================================
# ROUTER
# ==========================================
def router(state: GraphState) -> str:
    if state["command"] == CMD_ABORT:
        return END
    if state["command"] == CMD_PAUSE:
        return END  # Halts until resumed via /command endpoint

    # Issue 1: also check live DB status so an external pause/abort request
    # (received while a node was running) is honoured after the node finishes,
    # even though the graph state still carries CMD_RUN.
    project_id = state.get("project_id")
    if project_id:
        with Session(engine) as session:
            proj = session.exec(select(Project).where(Project.id == project_id)).first()
            if proj and proj.status in (STATUS_PAUSED, STATUS_ABORTED):
                return END

    return "continue"


# ==========================================
# GRAPH DEFINITION
# Edges are the single source of truth for execution order.
# Nodes must NOT set current_step to control routing — they
# set it to their own step name for UI/DB progress tracking only.
# ==========================================
# One shared policy applied to every node.
# RetryPolicy handles scheduling, backoff, and max attempts.
# Nodes only need to record failures to DB before re-raising.
DEFAULT_RETRY = RetryPolicy(max_attempts=3)

workflow = StateGraph(GraphState)


workflow.add_node(
    STEP_GAME_DESIGN,
    _make_skippable(STEP_GAME_DESIGN, game_designer_node),
    retry=DEFAULT_RETRY,
)
workflow.add_node(
    STEP_ART_DIRECTOR,
    _make_skippable(STEP_ART_DIRECTOR, art_director_node),
    retry=DEFAULT_RETRY,
)
workflow.add_node(
    STEP_SCRIPT_WRITER,
    _make_skippable(STEP_SCRIPT_WRITER, scriptwriter_node),
    retry=DEFAULT_RETRY,
)
workflow.add_node(
    STEP_GAME_BUILDER,
    _make_skippable(STEP_GAME_BUILDER, game_builder_node),
    retry=DEFAULT_RETRY,
)
workflow.add_node(
    STEP_ART_GENERATION,
    _make_skippable(STEP_ART_GENERATION, art_generation_node),
    retry=DEFAULT_RETRY,
)
workflow.add_node(
    STEP_ART_CLEANUP,
    _make_skippable(STEP_ART_CLEANUP, art_cleanup_node),
    retry=DEFAULT_RETRY,
)
workflow.add_node(
    STEP_VOICEOVER_GENERATION,
    _make_skippable(STEP_VOICEOVER_GENERATION, voiceover_generation_node),
    retry=DEFAULT_RETRY,
)
workflow.add_node(
    STEP_VOICEOVER_COMPRESSION,
    _make_skippable(STEP_VOICEOVER_COMPRESSION, voiceover_compression_node),
    retry=DEFAULT_RETRY,
)
workflow.add_node(
    STEP_MUSIC_DOWNLOADER,
    _make_skippable(STEP_MUSIC_DOWNLOADER, music_downloader_node),
    retry=DEFAULT_RETRY,
)
workflow.add_node(STEP_COMPLETED, _make_skippable(STEP_COMPLETED, completed_node))


workflow.set_entry_point(STEP_GAME_DESIGN)

workflow.add_conditional_edges(
    STEP_GAME_DESIGN, router, {"continue": STEP_SCRIPT_WRITER, END: END}
)
workflow.add_conditional_edges(
    STEP_SCRIPT_WRITER, router, {"continue": STEP_ART_DIRECTOR, END: END}
)
workflow.add_conditional_edges(
    STEP_ART_DIRECTOR, router, {"continue": STEP_GAME_BUILDER, END: END}
)
workflow.add_conditional_edges(
    STEP_GAME_BUILDER, router, {"continue": STEP_ART_GENERATION, END: END}
)
workflow.add_conditional_edges(
    STEP_ART_GENERATION, router, {"continue": STEP_ART_CLEANUP, END: END}
)
workflow.add_conditional_edges(
    STEP_ART_CLEANUP, router, {"continue": STEP_VOICEOVER_GENERATION, END: END}
)
workflow.add_conditional_edges(
    STEP_VOICEOVER_GENERATION,
    router,
    {"continue": STEP_VOICEOVER_COMPRESSION, END: END},
)
workflow.add_conditional_edges(
    STEP_VOICEOVER_COMPRESSION,
    router,
    {"continue": STEP_MUSIC_DOWNLOADER, END: END},
)
workflow.add_conditional_edges(
    STEP_MUSIC_DOWNLOADER, router, {"continue": STEP_COMPLETED, END: END}
)
workflow.add_conditional_edges(STEP_COMPLETED, router, {"continue": END, END: END})


# ==========================================
# SHARED STREAMING LOOP
# ==========================================
def _stream_graph(project_id: str, graph, config: dict, stream_input) -> None:
    """Stream the compiled graph and sync completion/pause/abort state to the DB."""
    last_executed_node = None
    try:
        should_stop = False
        for output in graph.stream(stream_input, config):
            for node_name, _ in output.items():
                last_executed_node = node_name
                with Session(engine) as session:
                    proj = session.exec(
                        select(Project).where(Project.id == project_id)
                    ).first()
                    if proj:
                        if node_name == STEP_COMPLETED:
                            proj.status = STATUS_COMPLETED
                            session.add(proj)
                            session.commit()
                        # Refresh to pick up any status change written by the API
                        # (e.g. CMD_PAUSE or CMD_ABORT received while node was running)
                        session.refresh(proj)
                        if proj.status in (STATUS_PAUSED, STATUS_ABORTED):
                            should_stop = True
            if should_stop:
                break
    except Exception as e:
        print(f"[{project_id}] Pipeline error: {e}")
        with Session(engine) as session:
            proj = session.exec(select(Project).where(Project.id == project_id)).first()
            if proj:
                proj.status = STATUS_ERROR
                session.add(proj)
                session.commit()
        raise

    # Post-loop: when the pipeline paused (user-requested pause, single-step mode,
    # or selective-skip mode), advance current_step to the NEXT step so the UI
    # correctly shows the just-completed step as done (✅) and the next step as
    # pending — not the already-finished step as "current / running".
    # Applies to both STATUS_PAUSED (set by the API before the loop ended) and
    # STATUS_RUNNING (single-step mode: CMD_PAUSE was only in state, not in DB).
    with Session(engine) as session:
        proj = session.exec(select(Project).where(Project.id == project_id)).first()
        if proj and proj.status in (STATUS_PAUSED, STATUS_RUNNING):
            advance_from = last_executed_node or proj.current_step
            if advance_from in STEP_ORDER:
                step_idx = STEP_ORDER.index(advance_from)
                if step_idx + 1 < len(STEP_ORDER):
                    proj.current_step = STEP_ORDER[step_idx + 1]
            if proj.status == STATUS_RUNNING:
                proj.status = STATUS_PAUSED
                print(
                    f"[{project_id}] Graph stream ended with RUNNING status → set to PAUSED"
                )
            session.add(proj)
            session.commit()


# ==========================================
# BACKGROUND RUNNER
# ==========================================
def run_graph(project_id: str, resume: bool = False) -> None:
    Path(FILE_PATH).parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(FILE_PATH, check_same_thread=False) as conn:
        memory = SqliteSaver(conn)
        graph = workflow.compile(checkpointer=memory)
        config = {"configurable": {"thread_id": project_id}}

        game_type = GAME_TYPE_POINT_AND_CLICK
        with Session(engine) as session:
            proj = session.exec(select(Project).where(Project.id == project_id)).first()
            if proj:
                proj.status = STATUS_RUNNING
                if proj.type:
                    game_type = proj.type
                session.add(proj)
                session.commit()

        if resume:
            print(f"[{project_id}] Resuming graph from last checkpoint...")
            graph.update_state(config, {"command": CMD_RUN})
            stream_input = None
        else:
            print(f"[{project_id}, {game_type}] Starting graph execution...")
            with Session(engine) as session:
                proj = session.exec(
                    select(Project).where(Project.id == project_id)
                ).first()
                no_voiceover = proj.no_voiceover if proj else False
                no_music = proj.no_music if proj else False
            stream_input: GraphState = {
                "project_id": project_id,
                "type": game_type,
                "command": CMD_RUN,
                "current_step": STEP_GAME_DESIGN,
                "no_voiceover": no_voiceover,
                "no_music": no_music,
            }

        _stream_graph(project_id, graph, config, stream_input)


def run_graph_from_step(
    project_id: str, step_name: str, single_step: bool = False
) -> None:
    """Run the pipeline starting from step_name with smart dependency tracking.

    - Resets metrics for step_name and every step that depends on its output,
      so those steps will execute again.
    - Steps NOT in the dependency chain keep their completed metrics and are
      automatically skipped (selective / smart-skip mode).
    - If single_step=True, only step_name itself executes, then the project
      is paused (useful for debugging a single pipeline stage).

    Works even when no checkpoint exists — injects one via update_state.
    """
    Path(FILE_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Issue 3: reset metrics for step_name + its downstream dependents so the
    # skip wrapper knows which steps need to actually run vs. which can be skipped.
    _reset_dependent_steps(project_id, step_name)

    with sqlite3.connect(FILE_PATH, check_same_thread=False) as conn:
        memory = SqliteSaver(conn)
        graph = workflow.compile(checkpointer=memory)
        config = {"configurable": {"thread_id": project_id}}

        game_type = GAME_TYPE_POINT_AND_CLICK
        with Session(engine) as session:
            proj = session.exec(select(Project).where(Project.id == project_id)).first()
            if proj:
                proj.status = STATUS_RUNNING
                proj.current_step = step_name
                if proj.type:
                    game_type = proj.type
                session.add(proj)
                session.commit()

        with Session(engine) as session:
            proj = session.exec(select(Project).where(Project.id == project_id)).first()
            no_voiceover = proj.no_voiceover if proj else False
            no_music = proj.no_music if proj else False

        base_state: GraphState = {
            "project_id": project_id,
            "type": game_type,
            "command": CMD_RUN,
            "current_step": step_name,
            "selective": True,  # Smart-skip steps not invalidated by step_name
            "single_step": single_step,  # Pause after this one step executes
            "no_voiceover": no_voiceover,
            "no_music": no_music,
        }

        if step_name == STEP_GAME_DESIGN:
            print(
                f"[{project_id}] Running from first step ({step_name}), single_step={single_step}"
            )
            stream_input = base_state
        else:
            step_idx = STEP_ORDER.index(step_name)
            prev_step = STEP_ORDER[step_idx - 1]
            print(
                f"[{project_id}] Running from '{step_name}' (after '{prev_step}'), single_step={single_step}"
            )
            graph.update_state(config, base_state, as_node=prev_step)
            stream_input = None

        _stream_graph(project_id, graph, config, stream_input)
