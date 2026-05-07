import os
import re

from shared.models import GraphState, Project
from shared.constants import (
    SKILL_SCRIPT_WRITER,
    STEP_SCRIPT_WRITER,
)
from shared.artifacts import read_skill, read_text, write_text, write_json
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


def scriptwriter_node(state: GraphState) -> GraphState:
    project_id = state["project_id"]
    game_type = state["type"]
    print(f"[{project_id}, {game_type}] STEP: Writing Script...")

    set_project_step(project_id, STEP_SCRIPT_WRITER)
    t_start = record_step_start(project_id, STEP_SCRIPT_WRITER)

    profile_id, context_size, llm_config = get_project_llm_profile(
        project_id, STEP_SCRIPT_WRITER
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
        record_step_end(project_id, STEP_SCRIPT_WRITER, t_start)
        record_step_retry(project_id, STEP_SCRIPT_WRITER, str(e))
        raise

    with Session(engine) as session:
        proj = session.exec(select(Project).where(Project.id == project_id)).first()

    skill_md = read_skill(game_type, SKILL_SCRIPT_WRITER)
    system_prompt = (
        f"\n--- Start of Instruction:\n {skill_md} \n--- End of Instruction ---\n"
    )
    lore_md = read_text(project_id, "lore.md")
    lore_prompt = f"\n--- Start of Lore:\n {lore_md} \n--- End of Lore ---\n"
    user_prompt = f"You need to generate Voiceover prompts based on the following lore:\n {lore_prompt}"

    print(f"[{project_id}, {game_type}] Sending request to LLM at {LLAMACPP_URL}...")
    try:
        voiceover_md = llamacpp_call(
            LLAMACPP_URL, system_prompt, user_prompt, context_size
        )

        if not voiceover_md or len(voiceover_md) < 100:
            print(f"LLM response too short or empty: '{voiceover_md}'")
            raise ValueError(
                f"LLM response too short or empty: '{voiceover_md}'"
            )  # Trigger a retry

        write_text(project_id, "voiceover.md", voiceover_md)
        print(
            f"[{project_id}, {game_type}] voiceover.md written ({len(voiceover_md)} chars)"
        )

        # convert voiceover.md to voiceover.json format expected by TTS system

        jobs = []
        actor_references = {}
        job_id = 1

        # Match every block: Actor / Voice Desc / File ID / one-or-more Line(s).
        # Handles both:
        #   **Line:**   (reference format — no number)
        #   **Line N:** (dialog format — numbered)
        block_pattern = re.compile(
            r"\*\s*\*\*Actor:\*\*\s*(.*?)\n"
            r"\s*\*\s*\*\*Voice Desc:\*\*\s*(.*?)\n"
            r"\s*\*\s*\*\*File ID:\*\*\s*(\S+)\n"
            r"((?:\s*\*\s*\*\*Line(?:\s+\d+)?:\*\*\s*\"[^\"]*\"\n?)+)",
            re.IGNORECASE,
        )
        line_re = re.compile(r'\*\*Line(?:\s+\d+)?:\*\*\s*"([^"]+)"', re.IGNORECASE)

        for actor, voice_desc, file_id, lines_block in block_pattern.findall(
            voiceover_md
        ):
            actor_clean = actor.strip()
            voice_desc_clean = voice_desc.strip()
            file_id_clean = file_id.strip()
            lines = line_re.findall(lines_block)

            if not lines:
                continue

            is_ref = "_ref" in file_id_clean.lower()
            search_key = actor_clean.lower()

            if is_ref:
                # Store reference for TTS conditioning of later lines
                actor_references[search_key] = {
                    "file": f"{file_id_clean}.wav",
                    "prompt": lines[0],
                }
                # Single job for the reference recording itself
                jobs.append(
                    {
                        "id": job_id,
                        "ref_wav": "",
                        "ref_prompt": "",
                        "file": f"{file_id_clean}.wav",
                        "voice_desc": voice_desc_clean,
                        "voice_prompt": lines[0],
                        "cfg_value": 2.0,
                        "inference_timesteps": 10,
                    }
                )
                job_id += 1
            else:
                # Smart actor reference lookup
                ref_data = {"file": "", "prompt": ""}
                if search_key in actor_references:
                    ref_data = actor_references[search_key]
                else:
                    for key, data in actor_references.items():
                        if search_key in key or key in search_key:
                            ref_data = data
                            break

                # One TTS job per line; file name carries a 0-based index suffix
                for idx, line_text in enumerate(lines):
                    jobs.append(
                        {
                            "id": job_id,
                            "ref_wav": ref_data["file"],
                            "ref_prompt": ref_data["prompt"],
                            "line_number": idx + 1,
                            "file": f"{file_id_clean}_{idx}.wav",
                            "voice_desc": voice_desc_clean,
                            "voice_prompt": line_text,
                            "cfg_value": 2.0,
                            "inference_timesteps": 10,
                        }
                    )
                    job_id += 1

        # 2. Output the payload
        payload = {"jobs": jobs}
        write_json(project_id, "voiceover_jobs.json", payload)
        print(
            f"[{project_id}, {game_type}] voiceover_jobs.json written ({len(jobs)} jobs), ({len(payload)} chars)"
        )

        duration = record_step_end(project_id, STEP_SCRIPT_WRITER, t_start)
        print(f"[{project_id}, {game_type}] LLM call took {duration:.1f}s")
    except Exception as e:
        record_step_end(project_id, STEP_SCRIPT_WRITER, t_start)
        record_step_retry(project_id, STEP_SCRIPT_WRITER, str(e))
        raise  # RetryPolicy retries the full node

    return state
