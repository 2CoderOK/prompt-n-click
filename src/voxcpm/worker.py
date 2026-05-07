import json
import os
import sys
import time
import traceback
from pathlib import Path

# Disable torch compilation before importing torch or voxcpm
os.environ["TORCH_COMPILE_DISABLE"] = "1"
os.environ["TORCHDYNAMO_DISABLE"] = "1"

import soundfile as sf
import torch
import torch._dynamo
from voxcpm import VoxCPM

torch._dynamo.config.suppress_errors = True

from voice_job_models import (
    VoiceJob,
    VoiceJobCollection,
    VoiceResultCollection,
    JobResult,
)


def generate_result(result_file: str, results_list: list[JobResult]):
    """Serializes the result collection to JSON."""
    # Wrap the list in our Collection model for strict validation
    collection = VoiceResultCollection(results=results_list)
    with open(result_file, "w") as r:
        # Use .model_dump_json() if using Pydantic v2, or .json() for v1
        r.write(collection.model_dump_json(indent=4))


def process_jobs(project_id):
    # Constants
    ROOT_DIR = Path(f"/app/projects/{project_id}")
    AUDIO_DIR = ROOT_DIR / "audio"
    JOBS_FILE = ROOT_DIR / "voiceover_jobs.json"
    RESULTS_FILE = ROOT_DIR / "voiceover_results.json"

    # Ensure audio directory exists
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Check if there are instructions waiting
    if not JOBS_FILE.exists():
        print(f"No jobs file found at {JOBS_FILE}. Exiting.")
        sys.exit(0)

    # 2. Read and Validate LangGraph instructions
    try:
        with open(JOBS_FILE, "r") as f:
            jobs_json = json.load(f)

        # This parses and validates the entire JSON structure
        input_data = VoiceJobCollection(**jobs_json)
    except Exception as e:
        print(f"Failed to parse jobs.json: {e}")
        sys.exit(1)

    results = []

    print("--- LOADING VOXCPM MODEL INTO VRAM ---")
    # Note: We put this inside the check so we don't load the model
    # if there are no jobs (saves time/electricity)
    model = VoxCPM.from_pretrained(
        "openbmb/VoxCPM2",
        load_denoiser=False,
    )

    # 3. Process jobs one by one
    for job in input_data.jobs:
        # Construct the prompt with the description tags
        # VoxCPM uses (tags)Text format
        full_prompt = f"({job.voice_desc}){job.voice_prompt}"

        print(f"Processing Job ID [{job.id}]: {full_prompt[:128]}...")

        start_time = time.time()
        try:
            # Check if reference wav exists if provided
            ref_path = None
            if job.ref_wav and job.ref_wav.strip():
                # Logic: Is it an absolute path or relative to our audio dir?
                ref_path = str(AUDIO_DIR / job.ref_wav)

            # --- INFERENCE ---
            wav = model.generate(
                text=full_prompt,
                reference_wav_path=ref_path,
                cfg_value=job.cfg_value,
                inference_timesteps=job.inference_timesteps,
            )

            # --- SAVE FILE ---
            # Ensure we save into the mapped volume directory
            output_file_path = AUDIO_DIR / job.file
            sf.write(str(output_file_path), wav, model.tts_model.sample_rate)

            print(f"Success: Saved to {output_file_path}")

            # Create success result
            results.append(
                JobResult(
                    id=job.id,
                    file=job.file,
                    status="success",
                    processing_time=round(time.time() - start_time, 2),
                )
            )

        except Exception as e:
            error_msg = str(e)
            print(f"Failed Job ID [{job.id}]: {error_msg}")
            traceback.print_exc()

            # Create failure result
            results.append(
                JobResult(
                    id=job.id, file=job.file, status="failed", error_message=error_msg
                )
            )

    print("--- WRITING RESULTS ---")
    generate_result(RESULTS_FILE, results)


if __name__ == "__main__":
    project_id = None
    process_jobs(project_id)
