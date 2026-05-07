from sqlmodel import Field, SQLModel
from typing import Optional, TypedDict, NotRequired


class ProjectCreate(SQLModel):
    project_id: str
    size: str
    type: str
    creativity: str
    # Optional field (defaults to None or a string)
    genre: Optional[str] = None
    name: Optional[str] = None
    art_style: Optional[str] = None
    description: Optional[str] = None
    no_voiceover: bool = False
    no_music: bool = False


class Project(SQLModel, table=True):
    id: str = Field(primary_key=True)
    status: str  # Uses STATUS_* constants
    current_step: str  # Uses STEP_* constants
    size: str  # SMALL, MEDIUM, LARGE
    type: str  # Uses GAME_TYPE_* constants
    name: Optional[str] = None
    genre: Optional[str] = None
    creativity: Optional[str] = None
    art_style: Optional[str] = None
    description: Optional[str] = None
    no_voiceover: bool = Field(default=False)
    no_music: bool = Field(default=False)


class ProjectStepMetrics(SQLModel, table=True):
    project_id: str = Field(primary_key=True)
    step_name: str = Field(primary_key=True)  # Uses STEP_* constants
    time_started: float  # Unix timestamp (time.time())
    time_ended: Optional[float] = None  # Unix timestamp
    duration_seconds: Optional[float] = None  # time_ended - time_started
    retry_count: int = 0  # How many retries were attempted
    last_error: Optional[str] = None  # Last error message (capped at 500 chars)


class ProjectListItem(SQLModel):
    id: str
    name: Optional[str] = None
    genre: Optional[str] = None
    size: Optional[str] = None
    status: str
    current_step: str


class ProjectList(SQLModel):
    projects: list[ProjectListItem]


class GraphState(TypedDict):
    project_id: str
    type: str  # Uses GAME_TYPE_* constants
    command: str  # Uses CMD_* constants
    current_step: str  # Uses STEP_* constants
    selective: NotRequired[
        bool
    ]  # True → smart-skip unchanged steps (run-from-step mode)
    single_step: NotRequired[
        bool
    ]  # True → pause after the first non-skipped step executes
    no_voiceover: NotRequired[bool]  # True → skip script_writer + voiceover steps
    no_music: NotRequired[bool]  # True → skip music_downloader step


# ==========================================
# LLM PROFILES
# ==========================================


class LLMProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    parameters: str  # Raw llamacpp CLI parameter string
    is_default: bool = Field(default=False)
    context_size: int = Field(default=8192)


class LLMProfileCreate(SQLModel):
    name: str
    parameters: str
    is_default: bool = False
    context_size: int = 8192


class LLMProfileUpdate(SQLModel):
    name: Optional[str] = None
    parameters: Optional[str] = None
    is_default: Optional[bool] = None
    context_size: Optional[int] = None


class LLMProfileList(SQLModel):
    profiles: list[LLMProfile]


# ==========================================
# PROJECT LLM STEP CONFIGS
# ==========================================


class ProjectLLMConfig(SQLModel, table=True):
    """Maps a project's pipeline step to a specific LLM profile."""

    project_id: str = Field(primary_key=True)
    step_name: str = Field(primary_key=True)  # e.g. STEP_GAME_DESIGN
    llm_profile_id: int = Field(foreign_key="llmprofile.id")


class ProjectLLMConfigItem(SQLModel):
    step_name: str
    llm_profile_id: int


class ProjectLLMConfigList(SQLModel):
    configs: list[ProjectLLMConfigItem]
