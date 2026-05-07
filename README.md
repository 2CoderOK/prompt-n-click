<p align="center">
  <img src="https://raw.githubusercontent.com/2coderok/prompt-n-click/src/frontend/phaser/fx/logo.png" alt="Prompt-N-Click Logo" width="500">
</p>

# Prompt-N-Click — Agentic Point-and-Click Game Generator

**Prompt-N-Click** is a fully local, AI-powered pipeline that takes a short description (optional) and produces complete, playable point-and-click adventure games — including story, artwork, voice-overs, downloadable music, and a Phaser.js engine — without a single cloud API call.

A local LLM writes the design document and dialogues, ComfyUI renders every scene and character, a TTS model synthesises voice-overs, and the whole thing is assembled into a self-contained game you can play in the browser.

Bundled with a game editor (built with Phaser.js) that allows you to fine-tune the game, music, FXs and properly place game elements on the game screens.
---

[<img src="https://raw.githubusercontent.com/2coderok/prompt-n-click/main/assets/prompt-n-click_preview.jpg" alt="prompt-n-click pipeline youtube video" width="500"/>](https://youtu.be/7cUcXEtysLw)

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Pipeline Steps](#pipeline-steps)
- [Project Structure](#project-structure)
- [Game Engine](#game-engine)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Fully local** — no OpenAI, no cloud. Everything runs in Docker containers on your machine.
- **End-to-end pipeline** — from a one-sentence description to a playable browser game.
- **Pause / Resume / Retry** — each pipeline step is independently resumable.
- **Run-from-step** — re-run any single step (or all steps from a given point) with automatic dependency invalidation; unchanged steps are smart-skipped.
- **Single-step execution** — execute exactly one step then auto-pause, useful for iterating on individual outputs.
- **Configurable LLM profiles** — define profiles with raw llama.cpp CLI parameters and assign different profiles per pipeline step, per project.
- **Multiple art styles** — prompt the art director with any Stable Diffusion-compatible style.
- **Optional voice & music** — TTS voice-overs and background music can be toggled off per project.
- **Built-in Phaser editor** — tweak the assembled game directly in the browser before exporting.
- **Startup recovery** — projects interrupted by an unexpected restart are automatically surfaced as errors so you can retry from the last completed step.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Browser / User                    │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP
        ┌───────────────▼──────────────┐
        │   Streamlit Frontend (8501)  │
        └───────────────┬──────────────┘
                        │ REST API
        ┌───────────────▼──────────────┐
        │  FastAPI + LangGraph (8000)  │  ← orchestrator
        │  (backend / api_orchestrator)│
        └──┬──────────┬────────────────┘
           │          │           │
  ┌────────▼──┐  ┌────▼──────┐  ┌▼──────────────┐
  │ llama.cpp │  │ ComfyUI   │  │  VoxCPM TTS   │
  │  (8090)   │  │  (8188)   │  │    (8091)     │
  │ LLM text  │  │ image gen │  │  voice-overs  │
  └───────────┘  └───────────┘  └───────────────┘
```

The **orchestrator** runs a LangGraph state machine. Each node in the graph corresponds to one pipeline step. Worker containers (llama.cpp, ComfyUI, VoxCPM) are started/stopped on demand by the orchestrator to stay within VRAM limits on single-GPU machines.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) + FastAPI |
| Frontend | [Streamlit](https://streamlit.io/) |
| LLM inference | [llama.cpp](https://github.com/ggml-org/llama.cpp) (any GGUF model) |
| Image generation | [ComfyUI](https://github.com/comfyanonymous/ComfyUI) |
| Voice synthesis | [VoxCPM](https://pypi.org/project/voxcpm/) |
| Game engine | [Phaser 3](https://phaser.io/) |
| Database | SQLite via [SQLModel](https://sqlmodel.tiangolo.com/) |
| Containerisation | Docker Compose |

---

## Prerequisites

- **Docker Desktop** (with GPU passthrough enabled)
- **NVIDIA GPU** with CUDA 12.4+ drivers (recommended ≥ 8 GB VRAM; 12 GB+ for larger models)
- A **GGUF language model** (e.g. any Mistral, LLaMA, Qwen model)
- A **Stable Diffusion checkpoint** compatible with ComfyUI

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/2coderok/prompt-n-click.git
cd prompt-n-click
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set the two required paths:

```env
# Path to a folder containing your GGUF model files
LLM_MODELS_PATH=C:/AI/models

# Path to your ComfyUI models directory (checkpoints, VAE, etc.)
COMFYUI_MODELS_PATH=C:/AI/ComfyUI/models
```

Check `docker-compose.yml` and double-check the env variables.
Also make sure ComfyUI workflows and `opengameart_music.csv` are properly referenced.
(Copy workflows to volumes/workflows and opengameart_music.csv to volumes/data)

### 3. Build and create all containers

Build every image and create all containers (including `comfyui` and `audio_engine`) without starting them:

```bash
docker compose --profile worker up --no-start
```

> `comfyui` and `audio_engine` containers are created here but **never started manually** — the `api_orchestrator` starts and stops them on demand to stay within VRAM limits.

### 4. Start the core services

```bash
docker compose up api_orchestrator studio_ui -d
```

The orchestrator will bring up `comfyui` and `audio_engine` as needed during pipeline execution.
Also please note that `llamacpp` container will be created programmatically on the very first run.

### 5. Download models for ComfyUI workflows

The workflows are using Z-Image Turbo:
```
ComfyUI/
├── models/
│   ├── text_encoders/
│   │   └──qwen_3_4b.safetensors # https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors
│   ├── diffusion_models/
│   │   └── z_image_turbo_bf16.safetensors # https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors
│   ├── vae/
│   │   └── ae.safetensors # https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors
```

---

## Configuration

### LLM Profiles

After launching, open **Settings** in the UI to create one or more LLM profiles. Each profile stores a **raw llama.cpp CLI parameter string** (e.g. `-m /usr/local/ai/models/Qwen3.5-9B-IQ4_NL.gguf --host 0.0.0.0 --port 8090 -ngl 33 -fa on -np 1 -t 12 --cache-type-k q4_0 --cache-type-v q4_0`) and a default context size. You can assign a different profile to each pipeline step on a per-project basis.

### Recommended context 

The TINY and SMALL game variants typically need an 8K–24K context window most of the time.
However, the LLM might sometimes get a bit too creative and require a larger context size! :)

Look out for errors in failed steps, which will clearly state if you need to increase the context limit.

### Choosing a model

The quality of the generated game scales directly with the quality of the LLM. Larger, smarter models produce noticeably better results — especially for dialogue writing, branching logic, and game-config assembly. If you want good games, use a good model.

That said, smaller models that fit entirely on a single consumer GPU work perfectly well as a starting point. A model like **Qwen3-9B** (Q4/Q5 GGUF) runs on 8–12 GB VRAM and produces solid results for shorter game variants (TINY / SMALL). Step up to a 30B+ model for richer stories and more reliable JSON output on MEDIUM / LARGE games.


---

## Usage

1. Click **New Game** and fill in the game details (name, genre, size, creativity, art style, description).
2. Click **Generate** — the pipeline runs automatically, showing real-time progress.
3. Use **Pause** / **Resume** / **Retry** buttons to control execution.
4. Use **Run from step** on any completed step to re-run it (and any steps whose outputs depend on it) without restarting the whole pipeline.
5. Once complete, open the **Phaser Editor** to preview and tweak the game.
6. Click **Export** to download a self-contained ZIP ready to host or share.

---

## Pipeline Steps

| # | Step | Description |
|---|---|---|
| 1 | Game Designer | LLM writes a full game-design document (lore, scenes, characters) |
| 2 | Script Writer | LLM writes all in-game dialogues and branching _(skipped when voiceover is disabled)_ |
| 3 | Art Director | LLM produces detailed image-generation prompts per asset |
| 4 | Game Builder | LLM assembles the Phaser config JSON from all prior outputs |
| 5 | Art Generation | ComfyUI renders every scene, character and item |
| 6 | Art Cleanup | Background removal and image post-processing |
| 7 | Voiceover Generation | TTS synthesises character voice lines |
| 8 | Voiceover Compression | FFmpeg compresses audio for web delivery |
| 9 | Music Download | Fetches royalty-free background music tracks |
| 10 | Completed | Finalises project and unlocks the Phaser editor |

---

## Project Structure

```
prompt-n-click/
├── assets/ # assets
├── docs/opengameart_music.csv    # list of music tracks available on opengameart.org (as of 04.27.2026)
├── src/
│   ├── backend/          # FastAPI + LangGraph orchestrator
│   │   ├── nodes/                  # Pipeline step implementations
│   │   │   └── point_and_click/    # Game-type-specific helpers
│   │   │       ├── asset_config_generator.py
│   │   │       └── game_playability_validator.py
│   │   ├── nodes/game_type_registry.py  # Extensible game-type registry
│   │   ├── skills/       # LLM system-prompt templates per game type
│   │   ├── graph.py      # LangGraph state machine definition
│   │   └── main.py       # FastAPI entry point
│   ├── frontend/         # Streamlit UI
│   │   ├── routes/       # One file per page/route
│   │   └── phaser/       # Phaser 3 game engine (static files)
│   ├── comfyui/          # ComfyUI Docker image
│   ├── voxcpm/           # VoxCPM TTS worker
│   └── shared/           # Pydantic/SQLModel models and constants
├── volumes/              # Runtime data (gitignored)
├── workflows/            # ComfyUI workflow JSON files
├── docker-compose.yml
├── .env.example          # Copy to .env and configure
└── LICENSE
```

---

## Game Engine

Generated games run entirely in the browser with **Phaser** (WebGL, 1280 × 720). The engine is self-contained — no server calls during gameplay.

### Core features

| Feature | Details |
|---|---|
| Scenes | Boot → Preload → Logo → Game (+ in-browser Level Editor) |
| Rooms | Each room has a background image and a list of interactive clickable zones |
| Clickables | Actors, items, and invisible zones; support `render_conditions`, `auto-trigger`, flip, scale, rotation |
| Inventory | Icon strip rendered top-right; items are picked up, used, and removed via effects |
| Dialogs | Sequential multi-line text box with per-line voice playback; click to advance |
| Flags | Boolean game-state flags drive all conditional logic (render, interaction, FX) |
| Timers | Count-up or count-down timers; room-scoped or global; optional HUD display with icon |
| State effects | `set_flag`, `change_room`, `move_item_to_inventory`, `remove_from_inventory`, `reset_game_state`, `apply_fx` |
| Music | Looping background track with configurable volume; auto-resumed on first interaction |
| UI styles | Highlight colour, text panel colours/font, inventory icon scale — all config-driven |
| System rooms | `menu`, `intro`, `game_over`, `victory` — handled automatically by the engine |
| Playability check | BFS validator (`game_playability_validator.py`) confirms the game is winnable before export |

### FX system

FX are declared in `game_config.json` per room (or triggered mid-interaction via `apply_fx`). They support optional `conditions` (flag-based) and `run_once` guards.

#### Overlay FX

| Type | Description | Key parameters |
|---|---|---|
| `vignette` | Dark border overlay | `alpha` |
| `scanlines` | Horizontal scanlines | `thickness`, `alpha`, `animated`, `speed` |
| `crt_rgb_split` | RGB chromatic aberration on the background | `shift`, `alpha`, `animated` |
| `color_tint` | Full-screen colour overlay (MULTIPLY blend) | `color`, `alpha` |
| `pulse_tint` | Pulsing colour overlay (ADD blend) | `color`, `alpha`, `speed` |
| `blur` | Post-processing blur on room objects | `strength`, `quality`, `animated`, `yoyo`, `repeat`, `ease` |
| `strobe` | Repeating flash | `color`, `alpha`, `speed`, `hold`, `delay` |
| `letterbox` | Cinematic black bars that slide in | `alpha`, `duration` |
| `shadow_gradient` | Bottom-half gradient darkening | `alpha` |
| `hologram_lines` | Scrolling horizontal scan lines | `color`, `alpha` |
| `flash` | One-shot flash that fades out | `color`, `alpha`, `duration` |
| `fade_in` | Fade from a colour to transparent | `color`, `alpha`, `duration` |
| `fade_out` | Fade to a colour | `color`, `alpha`, `duration` |
| `shake` | Screen shake | `intensity`, `duration` |
| `glitch` | Jittery position/alpha distortion on the background | `speed` |
| `zoom_pan` | Slow Ken-Burns zoom and pan on the background | `startScale`, `endScale`, `panX`, `panY`, `duration` |

#### Particle FX

| Type | Description | Key parameters |
|---|---|---|
| `fog` | Drifting fog | `speedMin/Max`, `scaleStart/End`, `alpha`, `frequency`, `lifespan` |
| `snow` | Falling snowflakes | `speedMinY/MaxY`, `scaleStart/End`, `alpha`, `lifespan` |
| `rain` | Falling rain streaks (ADD blend) | `speedMinY/MaxY`, `scaleStart/End`, `alpha`, `frequency`, `lifespan` |
| `sparks` | Upward spark burst at a point | `x`, `y`, `speedMin/Max`, `scaleStart/End`, `frequency`, `lifespan` |
| `particles` | Generic configurable emitter | `speedMin/Max`, `scaleStart/End`, `alphaStart`, `frequency`, `blendMode`, `lifespan` |

Particle assets available: `fx_circle`, `fx_dot`, `fx_drop`, `fx_flake`, `fx_fog`, `fx_line`, `fx_oval`, `fx_rhombus`, `fx_smoke`, `fx_square`, `fx_star`, `fx_triangle`.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

The pipeline source code in this repository is released under the **[MIT License](LICENSE)**.

> **Third-party components have their own licences.** Running this project pulls in additional software; each component's licence governs your use of that component.

| Component | Licence | Role |
|---|---|---|
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT | LLM inference server |
| [LangGraph](https://github.com/langchain-ai/langgraph) | MIT | Pipeline orchestration |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | REST API |
| [Streamlit](https://streamlit.io/) | Apache 2.0 | Frontend UI |
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | GPL-3.0 | Image generation — run as an isolated container, called via its REST API |
| [VoxCPM](https://github.com/OpenBMB/VoxCPM) | Apache-2.0 | TTS voice synthesis |
| [Phaser 3](https://phaser.io/) | MIT | Browser game engine |
| [SQLModel](https://sqlmodel.tiangolo.com/) | MIT | Database ORM |

### Music

Background music tracks used in generated games are sourced from [OpenGameArt.org](https://opengameart.org/). Tracks are selected from freely available collections and may carry **CC0**, **CC BY**, **CC BY-SA**, or other open licences. Attribution is provided wherever the track metadata includes it. If you publish or distribute a generated game, please verify and honour the specific licence of the music track included in your project.

### Questions or concerns

If you believe this project infringes a copyright, violates a licence, or raises any other legal or ethical concern — please [open an issue](../../issues) or contact us directly. We take these matters seriously and will address them as quickly as possible.
