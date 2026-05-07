import subprocess
from pathlib import Path

from docker_manager import ContainerManager
from database import (
    record_step_end,
    record_step_retry,
    record_step_start,
    set_project_step,
)
from shared.models import GraphState
from shared.constants import STEP_VOICEOVER_COMPRESSION
from shared.artifacts import project_dir, read_json, AUDIO_PATH


# EBU R128 loudness target: -16 LUFS integrated, -1.5 dBTP true peak, 11 LU range.
# -q:a 2 → ~190 kbps VBR MP3 (good quality / small size tradeoff).
_LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
_FFMPEG_ARGS = ["-filter:a", _LOUDNORM, "-ar", "44100", "-q:a", "2"]


def _normalize_to_mp3(src: Path, dst: Path) -> None:
    """Run ffmpeg loudnorm + mp3 encode on src, writing result to dst."""
    cmd = ["ffmpeg", "-y", "-i", str(src)] + _FFMPEG_ARGS + [str(dst)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {src.name}:\n{result.stderr[-500:]}")


def voiceover_compression_node(state: GraphState) -> GraphState:
    project_id = state["project_id"]
    game_type = state["type"]
    print(f"[{project_id}, {game_type}] Normalizing & compressing voiceovers...")

    set_project_step(project_id, STEP_VOICEOVER_COMPRESSION)
    t_start = record_step_start(project_id, STEP_VOICEOVER_COMPRESSION)

    ContainerManager.stop_workers()
    try:
        audio_dir: Path = project_dir(project_id) / AUDIO_PATH
        jobs_data = read_json(project_id, "voiceover_jobs.json")
        jobs: list[dict] = jobs_data.get("jobs", [])

        updated = 0
        errors = 0
        for job in jobs:
            src_filename: str = job.get("file", "")
            if not src_filename:
                continue

            src_path = audio_dir / src_filename
            if not src_path.exists():
                print(f"[{project_id}] Skipping missing audio: {src_filename}")
                errors += 1
                continue

            # Replace extension with .mp3
            dst_filename = Path(src_filename).with_suffix(".mp3").name
            dst_path = audio_dir / dst_filename

            try:
                _normalize_to_mp3(src_path, dst_path)
                updated += 1
                print(f"[{project_id}] Normalized → {dst_filename}")
            except RuntimeError as e:
                print(f"[{project_id}] Error processing {src_filename}: {e}")
                errors += 1

        duration = record_step_end(project_id, STEP_VOICEOVER_COMPRESSION, t_start)
        print(
            f"[{project_id}] Compression done in {duration:.1f}s "
            f"({updated} converted, {errors} errors)"
        )
    except Exception as e:
        record_step_end(project_id, STEP_VOICEOVER_COMPRESSION, t_start)
        record_step_retry(project_id, STEP_VOICEOVER_COMPRESSION, str(e))
        raise

    return state
