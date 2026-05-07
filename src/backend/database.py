import os
import time
from sqlmodel import create_engine, Session, select
from sqlalchemy import text
from shared.models import Project, ProjectStepMetrics, LLMProfile, ProjectLLMConfig

DB_PATH = os.getenv("DATABASE_URL", "sqlite:////db/studio.db")
FILE_PATH = DB_PATH.replace("sqlite:///", "")

engine = create_engine(
    DB_PATH, connect_args={"check_same_thread": False, "timeout": 5.0}
)

with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL;"))
    conn.commit()

# Create tables (no-op if already exist)
Project.metadata.create_all(engine)
ProjectStepMetrics.metadata.create_all(engine)
LLMProfile.metadata.create_all(engine)
ProjectLLMConfig.metadata.create_all(engine)

# Seed a default LLM profile if none exist
with Session(engine) as _seed_session:
    if not _seed_session.exec(select(LLMProfile)).first():
        # Seed a default profile with explicit context_size and ctx param
        default_ctx = 8192
        name = "Default Qwen3.5-35B-A3B-Q4_K_M, 14 layers"
        label = f"CONTEXT: {default_ctx // 1024}K"
        _seed_session.add(
            LLMProfile(
                name=f"{name} {label}",
                parameters=(
                    "-m /usr/local/ai/models/Qwen3.5-35B-A3B-Q4_K_M.gguf"
                    " --host 0.0.0.0 --port 8090 -ngl 12 -fa on"
                    " -np 1 -t 8 --cache-type-k q4_0 --cache-type-v q4_0"
                    f" --ctx-size {default_ctx}"
                ),
                is_default=True,
                context_size=default_ctx,
            )
        )
        _seed_session.commit()


def get_project_llm_profile(
    project_id: str, step_name: str
) -> tuple[int | None, int | None, str]:
    """Return (profile_id, context_size, parameters) for a project+step. Falls back to the default profile."""
    with Session(engine) as session:
        config = session.exec(
            select(ProjectLLMConfig).where(
                ProjectLLMConfig.project_id == project_id,
                ProjectLLMConfig.step_name == step_name,
            )
        ).first()
        if config:
            profile = session.exec(
                select(LLMProfile).where(LLMProfile.id == config.llm_profile_id)
            ).first()
            if profile:
                return profile.id, profile.context_size, profile.parameters
        # Fall back to the default profile
        default = session.exec(
            select(LLMProfile).where(LLMProfile.is_default.is_(True))
        ).first()
        if default:
            return default.id, default.context_size, default.parameters
        return None, None, ""


def get_project_llm_profile_params(project_id: str, step_name: str) -> str:
    """Return the LLM parameters for a project+step. Falls back to the default profile.
    Deprecated: prefer get_project_llm_profile() which also returns the profile id.
    """
    _, _, params = get_project_llm_profile(project_id, step_name)
    return params


def set_project_step(project_id: str, step_name: str) -> None:
    """Write current_step to Project immediately so the UI reflects live progress."""
    with Session(engine) as session:
        proj = session.exec(select(Project).where(Project.id == project_id)).first()
        if proj:
            proj.current_step = step_name
            session.add(proj)
            session.commit()


def record_step_start(project_id: str, step_name: str) -> float:
    """Insert/overwrite a metrics row and return the start timestamp."""
    started = time.time()
    with Session(engine) as session:
        existing = session.exec(
            select(ProjectStepMetrics).where(
                ProjectStepMetrics.project_id == project_id,
                ProjectStepMetrics.step_name == step_name,
            )
        ).first()
        if existing:
            existing.time_started = started
            existing.time_ended = None
            existing.duration_seconds = None
            session.add(existing)
        else:
            session.add(
                ProjectStepMetrics(
                    project_id=project_id,
                    step_name=step_name,
                    time_started=started,
                )
            )
        session.commit()
    return started


def record_step_retry(project_id: str, step_name: str, error_msg: str) -> int:
    """Increment retry_count and store last_error. Returns new retry count."""
    with Session(engine) as session:
        row = session.exec(
            select(ProjectStepMetrics).where(
                ProjectStepMetrics.project_id == project_id,
                ProjectStepMetrics.step_name == step_name,
            )
        ).first()
        if row:
            row.retry_count += 1
            row.last_error = error_msg[:500]
            session.add(row)
            session.commit()
            return row.retry_count
    return 0


def record_step_end(project_id: str, step_name: str, started: float) -> float:
    """Stamp time_ended and duration on the existing row. Returns duration."""
    ended = time.time()
    duration = ended - started
    with Session(engine) as session:
        row = session.exec(
            select(ProjectStepMetrics).where(
                ProjectStepMetrics.project_id == project_id,
                ProjectStepMetrics.step_name == step_name,
            )
        ).first()
        if row:
            row.time_ended = ended
            row.duration_seconds = duration
            session.add(row)
            session.commit()
    return duration


def record_step_skipped(project_id: str, step_name: str) -> None:
    """Mark a step as intentionally skipped (no_voiceover / no_music flags).

    Sets duration_seconds=0 and last_error='SKIPPED' as a sentinel so the UI
    can distinguish skipped steps from genuinely completed ones.
    """
    now = time.time()
    with Session(engine) as session:
        row = session.exec(
            select(ProjectStepMetrics).where(
                ProjectStepMetrics.project_id == project_id,
                ProjectStepMetrics.step_name == step_name,
            )
        ).first()
        if not row:
            row = ProjectStepMetrics(
                project_id=project_id,
                step_name=step_name,
                time_started=now,
            )
            session.add(row)
        row.time_ended = now
        row.duration_seconds = 0.0
        row.last_error = "SKIPPED"
        session.commit()
