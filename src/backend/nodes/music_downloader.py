"""
music_downloader_node
─────────────────────
Reads a CSV catalogue of royalty-free music tracks (title, href, ogg_url),
uses a small LLM (llamacpp) to pick candidates that match the game's lore,
then downloads the OGG files into the project's audio folder.

CSV format expected:
    title,href,ogg_url
    Battle Theme A,/content/battle-theme-a,https://…/battleThemeA.ogg

The CSV path is configured via the MUSIC_CSV_PATH environment variable
(default: /app/data/music_tracks.csv).

Selection logic — why batching with a small LLM works well here:
  - We don't need reasoning, just relevance matching.
  - A 7B model handles 60 titles + 800 chars of lore in one short prompt.
  - Batching keeps every request well within context limits.
  - JSON-mode output makes parsing reliable.
"""

import csv
import json
import os
import re

import requests
from bs4 import BeautifulSoup
from sqlmodel import Session, select

from database import (
    engine,
    get_project_llm_profile,
    record_step_end,
    record_step_retry,
    record_step_start,
    set_project_step,
)
from docker_manager import ContainerManager
from llamacpp_client import llamacpp_call, llamacpp_wait_until_loaded
from shared.artifacts import get_audio_path, read_text, write_json
from shared.constants import STEP_MUSIC_DOWNLOADER
from shared.models import GraphState, Project

# ── Configuration ────────────────────────────────────────────────────────────
MUSIC_CSV_PATH = os.getenv("MUSIC_CSV_PATH", "/app/data/openart_music.csv")
MUSIC_BATCH_SIZE = 100  # track titles sent to LLM per request
MUSIC_MAX_CANDIDATES = 5  # hard cap on tracks to actually download
DOWNLOAD_TIMEOUT = 30  # seconds per file

_SYSTEM_PROMPT = (
    "You are a music supervisor for video games. "
    "Given a short game description and a numbered list of music track titles, "
    "select the tracks that best match the game's theme and atmosphere. "
    'Return ONLY a JSON object with a single key "indices" whose value is an '
    "array of integers (0-based positions from the list). "
    "Pick 1-5 tracks per batch that are a genuinely good fit. "
    'If none fit, return {"indices": []}. '
    'Example: {"indices": [2, 5, 11]}'
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_csv(path: str) -> list[dict]:
    """Return all rows that have an ogg_url."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if row.get("ogg_url", "").strip()]


def _select_batch(
    llamacpp_url: str,
    context_size: int,
    lore_md_lite: str,
    batch: list[dict],
) -> list[int]:
    """Ask the LLM which tracks in *batch* fit the game. Returns valid indices."""
    numbered = "\n".join(f"{i}. {row['title']}" for i, row in enumerate(batch))
    user_prompt = (
        f"Game description:\n{lore_md_lite}\n\n"
        f"Track list:\n{numbered}\n\n"
        "Which tracks fit this game? Return JSON."
    )
    try:
        raw = llamacpp_call(
            llamacpp_url, _SYSTEM_PROMPT, user_prompt, context_size, is_json=True
        )
        data = json.loads(raw)
        return [
            int(i)
            for i in data.get("indices", [])
            if str(i).lstrip("-").isdigit() and 0 <= int(i) < len(batch)
        ]
    except Exception as exc:
        print(f"[music] LLM batch selection failed: {exc}")
        return []


OGA_BASE_URL = "https://opengameart.org"
PAGE_FETCH_TIMEOUT = 15  # seconds


def _fetch_track_page_info(href: str) -> dict:
    """Fetch an opengameart.org track page and extract description + attribution."""
    url = OGA_BASE_URL + href.strip()
    info = {"page_url": url, "description": "", "attribution": "", "license": ""}
    try:
        resp = requests.get(url, timeout=PAGE_FETCH_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # The track details live in div.group-right.right-column
        column = soup.find(
            "div", class_=lambda c: c and "group-right" in c and "right-column" in c
        )
        if not column:
            print(f"[music] right-column not found on {url}")
            return info

        # ── description ──────────────────────────────────────────────────
        # Grab all paragraph text before the 'Attribution Instructions' field
        desc_parts: list[str] = []
        for tag in column.find_all(["p", "div"], recursive=True):
            text = tag.get_text(" ", strip=True)
            if not text or "Attribution Instructions" in text:
                break
            # skip very short noise fragments
            if len(text) > 20:
                desc_parts.append(text)
        info["description"] = " ".join(
            dict.fromkeys(desc_parts)
        )  # deduplicate order-preserved

        # ── attribution ───────────────────────────────────────────────────
        # Look for "Copyright/Attribution Notice" or "Attribution Instructions"
        # label; extract the full text of the field, not just a snippet.
        for label in column.find_all(
            string=re.compile(
                r"Copyright/Attribution Notice|Attribution Instructions", re.I
            )
        ):
            label_el = label.find_parent()
            if not label_el:
                continue
            field_wrapper = label_el.find_parent()
            if field_wrapper:
                items = field_wrapper.find(class_=re.compile(r"field-item"))
                if items:
                    info["attribution"] = items.get_text(" ", strip=True)
                    break
            # fallback: gather all sibling text after the label element
            siblings = list(label_el.next_siblings)
            text = " ".join(
                s.get_text(" ", strip=True)
                if hasattr(s, "get_text")
                else str(s).strip()
                for s in siblings
            ).strip()
            if text:
                info["attribution"] = text
            break

        # ── license ──────────────────────────────────────────────────────
        # Extract the full license text rather than just the link text.
        for label in column.find_all(string=re.compile(r"\bLicense\b", re.I)):
            label_el = label.find_parent()
            if not label_el:
                continue
            field_wrapper = label_el.find_parent()
            if field_wrapper:
                items = field_wrapper.find(class_=re.compile(r"field-item"))
                if items:
                    info["license"] = items.get_text(" ", strip=True)
                    break
            # fallback: gather all sibling text after the label element
            siblings = list(label_el.next_siblings)
            text = " ".join(
                s.get_text(" ", strip=True)
                if hasattr(s, "get_text")
                else str(s).strip()
                for s in siblings
            ).strip()
            if text:
                info["license"] = text
            break

    except Exception as exc:
        print(f"[music] Failed to fetch page info for {url}: {exc}")
    return info


def _safe_filename(title: str) -> str:
    """Turn a track title into a safe OGG filename."""
    name = re.sub(r"[^\w\s-]", "", title)[:60].strip().replace(" ", "_")
    return f"{name}.ogg"


def _download_track(row: dict, dest_dir) -> str | None:
    """Download one OGG file. Returns the filename on success, None on failure."""
    url = row["ogg_url"].strip()
    filename = _safe_filename(row["title"])
    dest = dest_dir / filename
    if dest.exists():
        print(f"[music] Already exists, skipping: {filename}")
        return filename
    try:
        resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        print(f"[music] Downloaded: {filename} ({len(resp.content) // 1024} KB)")
        return filename
    except Exception as exc:
        print(f"[music] Download failed for {url}: {exc}")
        return None


# ── Node ──────────────────────────────────────────────────────────────────────


def music_downloader_node(state: GraphState) -> GraphState:
    project_id = state["project_id"]
    game_type = state["type"]
    print(f"[{project_id}, {game_type}] Selecting & downloading music tracks...")

    set_project_step(project_id, STEP_MUSIC_DOWNLOADER)
    t_start = record_step_start(project_id, STEP_MUSIC_DOWNLOADER)

    try:
        # ── 1. Load track catalogue ───────────────────────────────────────
        if not os.path.exists(MUSIC_CSV_PATH):
            raise FileNotFoundError(
                f"Music catalogue CSV not found at {MUSIC_CSV_PATH}. "
                "Set MUSIC_CSV_PATH or place the file there."
            )
        all_tracks = _load_csv(MUSIC_CSV_PATH)
        print(f"[music] {len(all_tracks)} tracks loaded from catalogue")

        # ── 2. Build compact game summary for the LLM ────────────────────
        lore_md = read_text(project_id, "lore.md")
        # use the text before "## 3. TIMERS (Global & Local)"
        lore_md_lite = lore_md.split("## 3. TIMERS (Global & Local)")[0]

        # ── 3. Start llamacpp worker ──────────────────────────────────────
        profile_id, context_size, llm_config = get_project_llm_profile(
            project_id, STEP_MUSIC_DOWNLOADER
        )
        ContainerManager.start_llamacpp_worker(llm_config, profile_id)
        llamacpp_url = os.getenv("LLAMACPP_LLM_URL", "http://llamacpp:8090")
        print(f"[music] Waiting for LLM at {llamacpp_url}...")
        llamacpp_wait_until_loaded(llamacpp_url, timeout=300)

        # ── 4. Batch-select candidate tracks ─────────────────────────────
        selected: list[dict] = []
        total_batches = (len(all_tracks) + MUSIC_BATCH_SIZE - 1) // MUSIC_BATCH_SIZE
        for batch_num, batch_start in enumerate(
            range(0, len(all_tracks), MUSIC_BATCH_SIZE), start=1
        ):
            if len(selected) >= MUSIC_MAX_CANDIDATES:
                break
            batch = all_tracks[batch_start : batch_start + MUSIC_BATCH_SIZE]
            indices = _select_batch(llamacpp_url, context_size, lore_md_lite, batch)
            for i in indices:
                if len(selected) < MUSIC_MAX_CANDIDATES:
                    selected.append(batch[i])
            print(
                f"[music] Batch {batch_num}/{total_batches}: "
                f"{len(indices)} selected, {len(selected)} total so far"
            )

        print(f"[music] {len(selected)} candidate tracks selected by LLM")

        # ── 5. Fetch page info & download OGG files ───────────────────
        audio_dir = get_audio_path(project_id)
        manifest: list[dict] = []
        for row in selected:
            href = row.get("href", "")
            page_info = _fetch_track_page_info(href) if href else {}
            filename = _download_track(row, audio_dir)
            if filename:
                manifest.append(
                    {
                        "title": row["title"],
                        "href": href,
                        "page_url": page_info.get("page_url", ""),
                        "ogg_url": row["ogg_url"],
                        "filename": filename,
                        "description": page_info.get("description", ""),
                        "license": page_info.get("license", ""),
                        "attribution": page_info.get("attribution", ""),
                    }
                )

        # ── 6. Write manifest ─────────────────────────────────────────────
        write_json(project_id, "music_tracks.json", {"tracks": manifest})
        print(
            f"[music] Done — {len(manifest)} track(s) downloaded, "
            "manifest written to music_tracks.json"
        )

        record_step_end(project_id, STEP_MUSIC_DOWNLOADER, t_start)

    except Exception as exc:
        record_step_end(project_id, STEP_MUSIC_DOWNLOADER, t_start)
        record_step_retry(project_id, STEP_MUSIC_DOWNLOADER, str(exc))
        raise

    return state
