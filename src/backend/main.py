import io
import json
import os
import re
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, BackgroundTasks, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from sqlmodel import Session, select

from shared.models import (
    Project,
    ProjectCreate,
    ProjectList,
    ProjectStepMetrics,
    LLMProfile,
    LLMProfileCreate,
    LLMProfileUpdate,
    LLMProfileList,
    ProjectLLMConfig,
    ProjectLLMConfigItem,
    ProjectLLMConfigList,
)
from shared.constants import (
    CMD_ABORT,
    CMD_PAUSE,
    CMD_RETRY,
    CMD_RUN,
    STATUS_ABORTED,
    STATUS_STARTING,
    STEP_GAME_DESIGN,
    STATUS_RUNNING,
    STATUS_ERROR,
    STATUS_PAUSED,
    STEP_ORDER,
)
from database import engine
from graph import run_graph, run_graph_from_step


# ==========================================
# STARTUP RECOVERY
# ==========================================
_INTERRUPTION_MSG = (
    "Pipeline execution was interrupted by an unexpected service termination. "
    "The process did not shut down gracefully. "
    "Retry the project to resume from the last successfully completed step."
)


def _recover_stranded_projects() -> None:
    """On startup, mark any project left in RUNNING or STARTING as ERROR.

    Background tasks are not persisted across process restarts, so any project
    that was active at shutdown will never resume on its own. Surfacing it as
    ERROR gives the user a clear signal and unlocks the Retry button.
    """
    stranded_statuses = (STATUS_RUNNING, STATUS_STARTING)
    with Session(engine) as session:
        stranded = session.exec(
            select(Project).where(Project.status.in_(stranded_statuses))
        ).all()

        if not stranded:
            return

        print(f"[startup] Recovering {len(stranded)} stranded project(s)...")
        for proj in stranded:
            print(
                f"[startup] '{proj.name or proj.id}' "
                f"(was {proj.status}, step={proj.current_step}) "
                f"→ {STATUS_ERROR}"
            )
            proj.status = STATUS_ERROR
            session.add(proj)

            # Stamp the interruption message on the current step's metrics row
            # so it surfaces in the progress view just like any other error.
            if proj.current_step:
                metrics_row = session.exec(
                    select(ProjectStepMetrics).where(
                        ProjectStepMetrics.project_id == proj.id,
                        ProjectStepMetrics.step_name == proj.current_step,
                    )
                ).first()
                if metrics_row:
                    metrics_row.last_error = _INTERRUPTION_MSG
                    session.add(metrics_row)

        session.commit()
        print(
            f"[startup] Recovery complete — "
            f"{len(stranded)} project(s) marked as {STATUS_ERROR}."
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup hook (before yield): recover any projects that were stranded in RUNNING or STARTING status
    _recover_stranded_projects()
    yield
    # Shutdown hook (after yield): nothing needed for now


app = FastAPI(title="Prompt-N-Click", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


app.mount(
    "/static/phaser", StaticFiles(directory="/app/static/phaser"), name="phaser_static"
)
app.mount(
    "/static/projects", StaticFiles(directory="/app/projects"), name="projects_static"
)

PROJECTS_DATA_PATH = Path(os.getenv("PROJECTS_DATA_PATH", "/app/projects"))

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _validate_project_id(project_id: str) -> None:
    if not _UUID_RE.match(project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID format")


# ==========================================
# FASTAPI ROUTES
# ==========================================
ACTIVE_STATUSES = (STATUS_RUNNING, STATUS_STARTING)


@app.post("/projects/new")
def create_project(data: ProjectCreate, background_tasks: BackgroundTasks):
    with Session(engine) as session:
        running = session.exec(
            select(Project).where(Project.status.in_(ACTIVE_STATUSES))
        ).first()
        if running:
            raise HTTPException(
                status_code=409,
                detail=f"Project '{running.name or 'Unnamed AI Project'}' is already running. Only one project can run at a time.",
            )

        new_proj = Project(
            id=data.project_id,
            name=data.name,
            status=STATUS_STARTING,
            current_step=STEP_GAME_DESIGN,
            size=data.size,
            type=data.type,
            genre=data.genre,
            creativity=data.creativity,
            art_style=data.art_style,
            description=data.description,
            no_voiceover=data.no_voiceover,
            no_music=data.no_music,
        )
        session.add(new_proj)
        session.commit()

    background_tasks.add_task(run_graph, data.project_id)
    return {"status": "started", "project_id": data.project_id}


@app.get("/projects", response_model=ProjectList)
def list_projects():
    with Session(engine) as session:
        projects = session.exec(select(Project)).all()
        return {"projects": projects}


@app.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str):
    with Session(engine) as session:
        proj = session.exec(select(Project).where(Project.id == project_id)).first()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        return proj


@app.get("/projects/{project_id}/metrics", response_model=List[ProjectStepMetrics])
def get_metrics(project_id: str):
    with Session(engine) as session:
        metrics = session.exec(
            select(ProjectStepMetrics).where(
                ProjectStepMetrics.project_id == project_id
            )
        ).all()
        return metrics


@app.get("/projects/{project_id}/status")
def get_status(project_id: str):
    with Session(engine) as session:
        proj = session.exec(select(Project).where(Project.id == project_id)).first()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"status": proj.status, "current_step": proj.current_step}


@app.post("/projects/{project_id}/command")
def send_command(project_id: str, command: str, background_tasks: BackgroundTasks):
    with Session(engine) as session:
        proj = session.exec(select(Project).where(Project.id == project_id)).first()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")

        prev_status = proj.status  # Capture before any modification

        if command == CMD_RETRY:
            if proj.status not in (STATUS_ERROR, STATUS_ABORTED):
                raise HTTPException(
                    status_code=400,
                    detail=f"Can only retry a project in {STATUS_ERROR} or {STATUS_ABORTED} status. Current status: {proj.status}",
                )
            proj.status = STATUS_RUNNING
        elif command == CMD_RUN:
            proj.status = STATUS_RUNNING
        elif command == CMD_PAUSE:
            if proj.status != STATUS_RUNNING:
                raise HTTPException(
                    status_code=400,
                    detail=f"Can only pause a project in {STATUS_RUNNING} status. Current status: {proj.status}",
                )
            proj.status = STATUS_PAUSED
        elif command == CMD_ABORT:
            proj.status = STATUS_ABORTED
        else:
            raise HTTPException(status_code=400, detail=f"Unknown command: {command}")
        session.add(proj)
        session.commit()

    if command in (CMD_RUN, CMD_RETRY):  # Resume from Pause or retry after error/abort
        # Resume from checkpoint if retrying (after error/abort) or resuming from pause
        resume = command == CMD_RETRY or prev_status == STATUS_PAUSED
        background_tasks.add_task(run_graph, project_id, resume)

    return {"status": "command_received", "command": command}


@app.post("/projects/{project_id}/run-from/{step_name}")
def run_from_step(
    project_id: str,
    step_name: str,
    background_tasks: BackgroundTasks,
    single_step: bool = False,
):
    """Restart a project from a specific pipeline step with smart dependency tracking.

    Steps whose outputs have not been invalidated by step_name are automatically
    skipped (selective mode). If single_step=True, only step_name itself is
    executed and the project is then paused.
    """
    if step_name not in STEP_ORDER:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown step '{step_name}'. Valid steps: {STEP_ORDER}",
        )
    with Session(engine) as session:
        proj = session.exec(select(Project).where(Project.id == project_id)).first()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        other_running = session.exec(
            select(Project).where(
                Project.status.in_(ACTIVE_STATUSES),
                Project.id != project_id,
            )
        ).first()
        if other_running:
            raise HTTPException(
                status_code=409,
                detail=f"Project '{other_running.name}' is already running.",
            )
        # Set RUNNING synchronously so the frontend sees the updated status
        # immediately after st.rerun() — before the background task executes.
        proj.status = STATUS_RUNNING
        proj.current_step = step_name
        session.add(proj)
        session.commit()
    background_tasks.add_task(run_graph_from_step, project_id, step_name, single_step)
    return {
        "status": "started",
        "project_id": project_id,
        "from_step": step_name,
        "single_step": single_step,
    }


# ==========================================
# LLM PROFILE ROUTES
# ==========================================


@app.get("/llm-profiles", response_model=LLMProfileList)
def list_llm_profiles():
    with Session(engine) as session:
        profiles = session.exec(select(LLMProfile)).all()
        return {"profiles": profiles}


@app.get("/llm-profiles/{profile_id}", response_model=LLMProfile)
def get_llm_profile(profile_id: int):
    with Session(engine) as session:
        profile = session.exec(
            select(LLMProfile).where(LLMProfile.id == profile_id)
        ).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile


@app.post("/llm-profiles", response_model=LLMProfile)
def create_llm_profile(data: LLMProfileCreate):
    with Session(engine) as session:
        if data.is_default:
            # Clear existing default
            existing_default = session.exec(
                select(LLMProfile).where(LLMProfile.is_default == True)
            ).first()
            if existing_default:
                existing_default.is_default = False
                session.add(existing_default)
        # Normalize: ensure parameters include --ctx-size and append CONTEXT: <Nx>K to name
        params = data.parameters or ""
        params = re.sub(r"--ctx-size\s+\d+", "", params)
        params = (params.strip() + f" --ctx-size {data.context_size}").strip()
        base_name = re.sub(r"\s*CONTEXT:\s*\d+K", "", data.name or "").strip()
        label = f"CONTEXT: {data.context_size // 1024}K"
        final_name = f"{base_name} {label}" if base_name else label

        profile = LLMProfile(
            name=final_name,
            parameters=params,
            is_default=data.is_default,
            context_size=data.context_size,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile


@app.put("/llm-profiles/{profile_id}", response_model=LLMProfile)
def update_llm_profile(profile_id: int, data: LLMProfileUpdate):
    with Session(engine) as session:
        profile = session.exec(
            select(LLMProfile).where(LLMProfile.id == profile_id)
        ).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        # Handle updates with normalization
        if data.name is not None:
            # remove existing CONTEXT: ...K suffix if user provides a new base name
            base = re.sub(r"\s*CONTEXT:\s*\d+K", "", data.name).strip()
            profile.name = base

        if data.context_size is not None:
            profile.context_size = data.context_size

        if data.parameters is not None:
            # Use provided parameters; try to extract ctx-size if present
            params = data.parameters
            m = re.search(r"--ctx-size\s+(\d+)", params)
            if m:
                profile.context_size = int(m.group(1))
            # remove any existing --ctx-size and we'll re-append normalized value below
            params = re.sub(r"--ctx-size\s+\d+", "", params).strip()
            profile.parameters = params

        # Ensure parameters include the selected context_size
        if profile.parameters is None:
            profile.parameters = ""
        profile.parameters = (
            profile.parameters.strip() + f" --ctx-size {profile.context_size}"
        ).strip()

        # Ensure profile name includes CONTEXT label
        base_name = re.sub(r"\s*CONTEXT:\s*\d+K", "", profile.name or "").strip()
        label = f"CONTEXT: {profile.context_size // 1024}K"
        profile.name = f"{base_name} {label}" if base_name else label
        if data.is_default is True:
            # Clear existing default (if it's a different profile)
            existing_default = session.exec(
                select(LLMProfile).where(
                    LLMProfile.is_default == True,
                    LLMProfile.id != profile_id,
                )
            ).first()
            if existing_default:
                existing_default.is_default = False
                session.add(existing_default)
            profile.is_default = True
        elif data.is_default is False and profile.is_default:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove default status directly. Set another profile as default first.",
            )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile


@app.post("/llm-profiles/{profile_id}/set-default", response_model=LLMProfile)
def set_default_llm_profile(profile_id: int):
    with Session(engine) as session:
        profile = session.exec(
            select(LLMProfile).where(LLMProfile.id == profile_id)
        ).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        # Clear existing default
        existing_default = session.exec(
            select(LLMProfile).where(
                LLMProfile.is_default == True,
                LLMProfile.id != profile_id,
            )
        ).first()
        if existing_default:
            existing_default.is_default = False
            session.add(existing_default)
        profile.is_default = True
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return profile


@app.delete("/llm-profiles/{profile_id}")
def delete_llm_profile(profile_id: int):
    with Session(engine) as session:
        profile = session.exec(
            select(LLMProfile).where(LLMProfile.id == profile_id)
        ).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        if profile.is_default:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the default profile. Set another profile as default first.",
            )
        session.delete(profile)
        session.commit()
        return {"status": "deleted", "profile_id": profile_id}


# ==========================================
# PROJECT LLM CONFIG ROUTES
# ==========================================


@app.get("/projects/{project_id}/llm-configs", response_model=ProjectLLMConfigList)
def get_project_llm_configs(project_id: str):
    with Session(engine) as session:
        configs = session.exec(
            select(ProjectLLMConfig).where(ProjectLLMConfig.project_id == project_id)
        ).all()
        return {
            "configs": [
                {"step_name": c.step_name, "llm_profile_id": c.llm_profile_id}
                for c in configs
            ]
        }


@app.post("/projects/{project_id}/llm-configs")
def save_project_llm_configs(project_id: str, configs: List[ProjectLLMConfigItem]):
    """Upsert step→profile mappings for a project."""
    with Session(engine) as session:
        for item in configs:
            existing = session.exec(
                select(ProjectLLMConfig).where(
                    ProjectLLMConfig.project_id == project_id,
                    ProjectLLMConfig.step_name == item.step_name,
                )
            ).first()
            if existing:
                existing.llm_profile_id = item.llm_profile_id
                session.add(existing)
            else:
                session.add(
                    ProjectLLMConfig(
                        project_id=project_id,
                        step_name=item.step_name,
                        llm_profile_id=item.llm_profile_id,
                    )
                )
        session.commit()
    return {"status": "saved"}


# ==========================================
# PROJECT FILE / ASSET ROUTES (for Editor)
# ==========================================

_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+$")


@app.get("/projects/{project_id}/game-config")
def get_game_config(project_id: str):
    """Return the project's game_config.json as a parsed JSON object."""
    _validate_project_id(project_id)
    config_path = PROJECTS_DATA_PATH / project_id / "game_config.json"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="game_config.json not found")
    content = config_path.read_text(encoding="utf-8")
    parsed = json.loads(content)
    # Handle double-encoded JSON (stored as a JSON string value)
    if isinstance(parsed, str):
        parsed = json.loads(parsed)
    return JSONResponse(content=parsed)


@app.post("/projects/{project_id}/game-config")
def update_game_config(project_id: str, payload: dict = Body(...)):
    """
    Receives the updated JSON from the Phaser editor, backs up the existing
    config with a timestamp, and then saves the new payload.
    """
    project_dir = PROJECTS_DATA_PATH / project_id

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    config_path = project_dir / "game_config.json"

    # ==========================================
    # THE BACKUP LOGIC
    # ==========================================
    if config_path.exists():
        # Generate a clean timestamp: e.g., 20260424_153045
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"game_config.json.backup_{timestamp}"
        backup_path = project_dir / backup_filename

        # Rename the existing file to the backup name
        config_path.rename(backup_path)
    # ==========================================

    # Write the new configuration
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)

    return {
        "status": "success",
        "message": "Config updated and previous version backed up.",
    }


# ==========================================
# GAME EXPORT ROUTE
# ==========================================

PHASER_STATIC_DIR = Path("/app/static/phaser")


@app.get("/projects/{project_id}/export")
def export_game(project_id: str):
    """Build a self-contained zip of the completed game and stream it to the client.

    Zip layout (extract anywhere, open index.html — no server needed):
      index.html
      init.js            game-type scene initialiser
      game.js            game-type main scene
      fx_system.js
      favicon.ico
      fx/<sprites + logo>
      sfx/click.mp3
      game_config.json
      assets_config.json
      music_tracks.json  (if present)
      <image>.png        images at root — standalone assetBase is ''
      <track>.ogg        music track at root — standalone audioAssetBase is ''
      <voice>.mp3        voice lines at root
    """
    _validate_project_id(project_id)
    project_dir = PROJECTS_DATA_PATH / project_id
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    config_path = project_dir / "game_config.json"
    if not config_path.exists():
        raise HTTPException(
            status_code=404,
            detail="game_config.json not found — complete the pipeline first",
        )

    # Determine game type and name from project record
    with Session(engine) as session:
        proj = session.exec(select(Project).where(Project.id == project_id)).first()
        game_type = (proj.type if proj else None) or "point_and_click"
        game_name = (proj.name if proj else None) or project_id

    game_type_dir = PHASER_STATIC_DIR / game_type

    # Parse game_config for title and music track reference
    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(config_data, str):
            config_data = json.loads(config_data)
    except Exception:
        config_data = {}

    # Parse assets_config to collect voice filenames (voices live in dialogs section)
    assets_config_path = project_dir / "assets_config.json"
    try:
        assets_data = json.loads(assets_config_path.read_text(encoding="utf-8"))
        if isinstance(assets_data, str):
            assets_data = json.loads(assets_data)
    except Exception:
        assets_data = {}

    def _collect_audio_files(obj) -> set[str]:
        """Recursively collect voice/play_voice/audio_file values from any config."""
        files: set[str] = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                if (
                    k in ("voice", "play_voice", "audio_file")
                    and isinstance(v, str)
                    and v
                ):
                    files.add(v)
                else:
                    files |= _collect_audio_files(v)
        elif isinstance(obj, list):
            for item in obj:
                files |= _collect_audio_files(item)
        return files

    voice_files = _collect_audio_files(assets_data)
    music_track = (config_data.get("music") or {}).get("track", "none")
    if music_track == "none":
        music_track = None
    safe_title = re.sub(r"[^\w\-]", "_", config_data.get("game_title", game_name))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # -- index.html --
        index_html = (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="UTF-8">\n'
            '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"  <title>{config_data.get('game_title', game_name)}</title>\n"
            '  <link rel="icon" href="favicon.ico">\n'
            '  <script src="https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js"></script>\n'
            "  <style>\n"
            "    body { margin: 0; background-color: #111; display: flex;"
            " justify-content: center; align-items: center; height: 100vh;"
            " color: white; font-family: sans-serif; }\n"
            "    canvas { border: 2px solid #444; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            '  <script src="fx_system.js"></script>\n'
            '  <script src="init.js"></script>\n'
            '  <script src="game.js"></script>\n'
            "</body>\n"
            "</html>\n"
        )
        zf.writestr("index.html", index_html)

        # -- Phaser scripts: init.js + game.js (game-type), fx_system.js (root) --
        for script, candidates in (
            ("init.js", [game_type_dir / "init.js"]),
            ("game.js", [game_type_dir / "game.js"]),
            ("fx_system.js", [PHASER_STATIC_DIR / "fx_system.js"]),
        ):
            for c in candidates:
                if c.exists():
                    zf.write(c, script)
                    break

        # -- favicon --
        favicon = PHASER_STATIC_DIR / "favicon.ico"
        if favicon.exists():
            zf.write(favicon, "favicon.ico")

        # -- FX sprites (including logo) --
        fx_dir = PHASER_STATIC_DIR / "fx"
        if fx_dir.exists():
            for fx_file in fx_dir.iterdir():
                if fx_file.is_file():
                    zf.write(fx_file, f"fx/{fx_file.name}")

        # -- SFX click (at sfx/ — matches standalone sfxBase = 'sfx/') --
        sfx_click = PHASER_STATIC_DIR / "sfx" / "click.mp3"
        if sfx_click.exists():
            zf.write(sfx_click, "sfx/click.mp3")

        # -- game_config.json + assets_config.json --
        zf.write(config_path, "game_config.json")
        if assets_config_path.exists():
            zf.write(assets_config_path, "assets_config.json")

        # -- music_tracks.json (attribution metadata, optional) --
        music_tracks_path = project_dir / "music_tracks.json"
        if music_tracks_path.exists():
            zf.write(music_tracks_path, "music_tracks.json")

        # -- Project images at zip root (standalone assetBase is '') --
        img_dir = project_dir / "img"
        if img_dir.exists():
            for img_file in img_dir.iterdir():
                if img_file.is_file() and img_file.suffix.lower() == ".png":
                    zf.write(img_file, img_file.name)

        # -- Music track at zip root (standalone audioAssetBase is '') --
        audio_dir = project_dir / "audio"
        if music_track and audio_dir.exists():
            music_path = audio_dir / music_track
            if music_path.exists():
                zf.write(music_path, music_track)

        # -- Voice lines at zip root --
        if audio_dir.exists():
            for vf in voice_files:
                vpath = audio_dir / vf
                if vpath.exists():
                    zf.write(vpath, vf)

    buf.seek(0)
    filename = f"{safe_title}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
