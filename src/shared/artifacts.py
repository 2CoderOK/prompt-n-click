import json
import os
from pathlib import Path

DATA_ROOT = Path(os.getenv("PROJECTS_DATA_PATH", "/app/projects"))
SKILLS_ROOT = Path("/app/skills")
WORKFLOWS_ROOT = Path("/app/workflows")
IMAGE_PATH = "img"
AUDIO_PATH = "audio"

WORKFLOWS_NODE_MAP = {
    "bg": {
        "positive_prompt_node": "104:90",
        "negative_prompt_node": "7",
        "seed_node": "104:92",
        "save_image_node": "60",
    },
    "asset": {
        "positive_prompt_node": "104:90",
        "negative_prompt_node": "7",
        "seed_node": "104:92",
        "save_image_node": "60",
    },
}


def cleanup_json_from_llm(raw_str: str) -> str:
    # Remove newlines and tabs that may be added by the LLM
    cleaned = raw_str.replace("\n", "").replace("\t", "")
    # Sometimes LLMs add extra quotes around the JSON, remove them
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1]
    return cleaned


def project_dir(project_id: str) -> Path:
    path = DATA_ROOT / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_image_path(project_id: str) -> Path:
    path = project_dir(project_id) / IMAGE_PATH
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_audio_path(project_id: str) -> Path:
    path = project_dir(project_id) / AUDIO_PATH
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text(project_id: str, filename: str, content: str) -> None:
    (project_dir(project_id) / filename).write_text(content, encoding="utf-8")


def read_text(project_id: str, filename: str) -> str:
    return (project_dir(project_id) / filename).read_text(encoding="utf-8")


def write_json(project_id: str, filename: str, data: dict) -> None:
    write_text(project_id, filename, json.dumps(data, indent=2))


def read_json(project_id: str, filename: str) -> dict:
    return json.loads(read_text(project_id, filename))


def artifact_exists(project_id: str, filename: str) -> bool:
    return (project_dir(project_id) / filename).is_file()


def read_skill(game_type: str, skill_file_name: str) -> str:
    return (SKILLS_ROOT / game_type / skill_file_name).read_text(encoding="utf-8")


def read_workflow(workflow_file_name: str) -> dict:
    return json.loads((WORKFLOWS_ROOT / workflow_file_name).read_text(encoding="utf-8"))


def write_image(project_id: str, filename: str, image_bytes: bytes) -> None:
    path = get_image_path(project_id)  # Ensure the image directory exists
    (path / filename).write_bytes(image_bytes)


def read_image(project_id: str, filename: str) -> bytes:
    path = get_image_path(project_id)  # Ensure the image directory exists
    return (path / filename).read_bytes()
