from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input models — used by the orchestrator to write voiceover_jobs.json
# ---------------------------------------------------------------------------


class VoiceJob(BaseModel):
    id: int
    file: str = Field(..., description="Target filename for the generated audio")
    voice_prompt: str = Field(..., description="The text the model should speak")
    voice_desc: str = Field(..., description="Descriptive tags for the voice style")
    ref_wav: Optional[str] = Field(
        "", description="Path to a reference .wav file for cloning"
    )
    ref_prompt: Optional[str] = Field(
        "", description="Text transcript of the reference wav"
    )
    cfg_value: float
    inference_timesteps: int


class VoiceJobCollection(BaseModel):
    jobs: list[VoiceJob]


# ---------------------------------------------------------------------------
# Output models — written by the VoxCPM worker to voiceover_results.json
# ---------------------------------------------------------------------------


class JobResult(BaseModel):
    id: int
    file: str
    status: str = Field(..., pattern="^(success|failed)$")
    error_message: Optional[str] = None
    processing_time: Optional[float] = None


class VoiceResultCollection(BaseModel):
    results: list[JobResult]
