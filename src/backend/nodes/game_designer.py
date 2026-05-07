import os

from shared.models import GraphState, Project
from shared.constants import (
    STEP_GAME_DESIGN,
    SKILL_GAME_DESIGNER,
)
from shared.artifacts import read_skill, write_text
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


def game_designer_node(state: GraphState) -> GraphState:
    project_id = state["project_id"]
    game_type = state["type"]

    print(f"[{project_id}, {game_type}] Designing Game...")

    set_project_step(project_id, STEP_GAME_DESIGN)
    t_start = record_step_start(project_id, STEP_GAME_DESIGN)

    profile_id, context_size, llm_config = get_project_llm_profile(
        project_id, STEP_GAME_DESIGN
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
        record_step_end(project_id, STEP_GAME_DESIGN, t_start)
        record_step_retry(project_id, STEP_GAME_DESIGN, str(e))
        raise

    with Session(engine) as session:
        proj = session.exec(select(Project).where(Project.id == project_id)).first()

    skill_md = read_skill(game_type, SKILL_GAME_DESIGNER)
    system_prompt = (
        f"\n--- Start of Instruction:\n {skill_md} \n--- End of Instruction ---\n"
    )
    project_info = (
        f"Game Name: {proj.name}\n"
        f"Game Size: {proj.size}\n"
        f"Genre: {proj.genre}\n"
        f"Creativity: {proj.creativity}\n"
        f"Art Style: {proj.art_style}\n"
        f"Description: {proj.description}"
    )
    user_prompt = f"You need to generate a game design document based on the following project information:\n{project_info}"

    print(f"[{project_id}, {game_type}] Sending request to LLM at {LLAMACPP_URL}...")
    try:
        lore_md = llamacpp_call(LLAMACPP_URL, system_prompt, user_prompt, context_size)

        if not lore_md or len(lore_md) < 100:
            print(f"LLM response too short or empty: '{lore_md}'")
            raise ValueError(
                f"LLM response too short or empty: '{lore_md}'"
            )  # Trigger a retry
        write_text(project_id, "lore.md", lore_md)
        print(f"[{project_id}, {game_type}] lore.md written ({len(lore_md)} chars)")

        # update project with lore information if user has not provided game name, genre, art style, or description
        with Session(engine) as session:
            proj = session.exec(select(Project).where(Project.id == project_id)).first()
            updated = False
            if not proj.name:
                # look for "* **Title:** "
                for line in lore_md.splitlines():
                    if line.startswith("* **Title:**"):
                        proj.name = line.replace("* **Title:**", "").strip()
                        updated = True
                        break
                proj.name = proj.name.strip('"')
            if not proj.genre:
                for line in lore_md.splitlines():
                    if line.startswith("* **Genre:** "):
                        proj.genre = line.replace("* **Genre:** ", "").strip()
                        updated = True
                        break

            if not proj.art_style:
                for line in lore_md.splitlines():
                    if line.startswith("* **Global Art Style:** "):
                        proj.art_style = line.replace(
                            "* **Global Art Style:** ", ""
                        ).strip()
                        updated = True
                        break

            if not proj.description:
                # extract text between "## 2. WORLD LORE & STORY" and "## 3. TIMERS"
                in_lore_section = False
                description_lines = []
                for line in lore_md.splitlines():
                    if line.startswith("## 2. WORLD LORE & STORY"):
                        in_lore_section = True
                        continue
                    if line.startswith("## 3. TIMERS"):
                        in_lore_section = False
                        continue
                    if in_lore_section:
                        description_lines.append(line)
                proj.description = "\n".join(description_lines).strip()
                updated = True

            if updated:
                session.add(proj)
                session.commit()

        duration = record_step_end(project_id, STEP_GAME_DESIGN, t_start)
        print(f"[{project_id}, {game_type}] LLM call took {duration:.1f}s")
    except Exception as e:
        record_step_end(project_id, STEP_GAME_DESIGN, t_start)
        record_step_retry(project_id, STEP_GAME_DESIGN, str(e))
        raise  # RetryPolicy retries the full node

    return state
