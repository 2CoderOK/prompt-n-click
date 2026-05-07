# --- Project Statuses ---
STATUS_STARTING = "starting"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"
STATUS_ABORTED = "aborted"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"  # per-step sentinel stored in last_error

# --- Graph Commands ---
CMD_RUN = "run"
CMD_PAUSE = "pause"
CMD_ABORT = "abort"
CMD_RETRY = "retry"

# --- Pipeline Steps ---
STEP_INIT = "init"
STEP_GAME_DESIGN = "game_designer"
STEP_ART_DIRECTOR = "art_director"
STEP_SCRIPT_WRITER = "script_writer"
STEP_GAME_BUILDER = "game_builder"
STEP_ART_GENERATION = "art_generation"
STEP_ART_CLEANUP = "art_cleanup"
STEP_VOICEOVER_GENERATION = "voiceover_generation"
STEP_VOICEOVER_COMPRESSION = "voiceover_compression"
STEP_MUSIC_DOWNLOADER = "music_downloader"
STEP_COMPLETED = "completed"

# --- Worker Container Names ---
WORKER_LLAMACPP = "game_studio_llamacpp"
WORKER_VOICEOVER = "game_studio_audio"
WORKER_GFX = "game_studio_comfyui"

ALL_WORKERS = [WORKER_LLAMACPP, WORKER_VOICEOVER, WORKER_GFX]

GAME_TYPE_POINT_AND_CLICK = "point_and_click"
GAME_TYPE_VISUAL_NOVEL = "visual_novel"
GAME_TYPE_DECKBUILDER = "deckbuilder"

GAME_TYPES = [
    GAME_TYPE_POINT_AND_CLICK
]  # , GAME_TYPE_VISUAL_NOVEL, GAME_TYPE_DECKBUILDER]

GAME_TYPE_NAMES = {
    GAME_TYPE_POINT_AND_CLICK: "Point-and-Click Adventure",
    GAME_TYPE_VISUAL_NOVEL: "Visual Novel",
    GAME_TYPE_DECKBUILDER: "Deckbuilder",
}

# --- Game Genres ---
GAME_GENRES = [
    "Action",
    "Adventure",
    "Comedy",
    "Crime",
    "Drama",
    "Fantasy",
    "Historical",
    "Horror",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Thriller",
    "Western",
]

# --- PIPELINE STEPS ---
PIPELINE_STEPS = [
    {"id": 1, "name": STEP_GAME_DESIGN, "desc": "Game Design (Markdown)"},
    {"id": 2, "name": STEP_SCRIPT_WRITER, "desc": "Scriptwriter (Dialogues)"},
    {"id": 3, "name": STEP_ART_DIRECTOR, "desc": "Art Director (Prompts)"},
    {"id": 4, "name": STEP_GAME_BUILDER, "desc": "Game Builder (Config JSON)"},
    {"id": 5, "name": STEP_ART_GENERATION, "desc": "Art Generation (Images)"},
    {"id": 6, "name": STEP_ART_CLEANUP, "desc": "Art Cleanup (Actor & Item Images)"},
    {
        "id": 7,
        "name": STEP_VOICEOVER_GENERATION,
        "desc": "Voiceover Generation (Audio)",
    },
    {
        "id": 8,
        "name": STEP_VOICEOVER_COMPRESSION,
        "desc": "Voiceover Compression (Audio)",
    },
    {
        "id": 9,
        "name": STEP_MUSIC_DOWNLOADER,
        "desc": "Music Selection & Download",
    },
    {"id": 10, "name": STEP_COMPLETED, "desc": "Completed"},
]

# Execution order — must stay in sync with the edges above.
# Used by run_graph_from_step to compute which node precedes a given step.
STEP_ORDER = [
    STEP_GAME_DESIGN,
    STEP_SCRIPT_WRITER,
    STEP_ART_DIRECTOR,
    STEP_GAME_BUILDER,
    STEP_ART_GENERATION,
    STEP_ART_CLEANUP,
    STEP_VOICEOVER_GENERATION,
    STEP_VOICEOVER_COMPRESSION,
    STEP_MUSIC_DOWNLOADER,
    STEP_COMPLETED,
]

# ==========================================
# DEPENDENCY MAP
# Which downstream steps must be re-run (invalidated) when a given step re-runs.
# Determined by actual data-flow: Y is invalidated by X if Y reads X's output.
# ==========================================
STEP_INVALIDATES: dict[str, list[str]] = {
    STEP_GAME_DESIGN: [
        STEP_SCRIPT_WRITER,
        STEP_ART_DIRECTOR,
        STEP_GAME_BUILDER,
        STEP_ART_GENERATION,
        STEP_ART_CLEANUP,
        STEP_VOICEOVER_GENERATION,
        STEP_VOICEOVER_COMPRESSION,
        STEP_MUSIC_DOWNLOADER,
        STEP_COMPLETED,
    ],
    STEP_SCRIPT_WRITER: [
        STEP_VOICEOVER_GENERATION,
        STEP_VOICEOVER_COMPRESSION,
        STEP_COMPLETED,
    ],
    STEP_ART_DIRECTOR: [
        STEP_GAME_BUILDER,
        STEP_ART_GENERATION,
        STEP_ART_CLEANUP,
        STEP_COMPLETED,
    ],
    STEP_GAME_BUILDER: [STEP_COMPLETED],
    STEP_ART_GENERATION: [STEP_ART_CLEANUP, STEP_COMPLETED],
    STEP_ART_CLEANUP: [STEP_COMPLETED],
    STEP_VOICEOVER_GENERATION: [STEP_VOICEOVER_COMPRESSION, STEP_COMPLETED],
    STEP_VOICEOVER_COMPRESSION: [STEP_COMPLETED],
    STEP_MUSIC_DOWNLOADER: [STEP_COMPLETED],
    STEP_COMPLETED: [],
}

# skill file names

SKILL_GAME_DESIGNER = "GAME_DESIGNER.md"
SKILL_ART_DIRECTOR = "ART_DIRECTOR.md"
SKILL_SCRIPT_WRITER = "SCRIPT_WRITER.md"
SKILL_GAME_BUILDER = "GAME_BUILDER.md"


# COMFYUI IMAGE GENERATION RETRY
COMFYUI_MAX_RETRIES = 3
COMFYUI_TIMEOUT = 300  # seconds
COMFYUI_GENERATION_DELAY = 5  # seconds

# Artifact mapping for frontend display and retrieval
STEP_ARTIFACT_MAP = {
    STEP_GAME_DESIGN: {"page": "artifact_md", "file": "lore.md"},
    STEP_SCRIPT_WRITER: {"page": "artifact_md", "file": "voiceover.md"},
    STEP_ART_DIRECTOR: {
        "page": "artifact_json",
        "files": ["art_jobs.json", "art_info.json"],
    },
    STEP_GAME_BUILDER: {
        "page": "artifact_json",
        "files": ["game_config.json", "assets_config.json"],
    },
    STEP_ART_GENERATION: {"page": "artifact_images", "jobs_file": "art_jobs.json"},
    STEP_ART_CLEANUP: {"page": "artifact_images", "jobs_file": "art_jobs.json"},
    STEP_VOICEOVER_GENERATION: {
        "page": "artifact_audio",
        "jobs_file": "voiceover_jobs.json",
    },
    STEP_VOICEOVER_COMPRESSION: {
        "page": "artifact_audio",
        "jobs_file": "voiceover_jobs.json",
    },
    STEP_MUSIC_DOWNLOADER: {
        "page": "artifact_music",
        "jobs_file": "music_tracks.json",
    },
}
