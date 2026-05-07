"""
asset_config_generator.py

Builds assets_config.json from voiceover.md and art_info.json.

Output sections
---------------
  dialogs     — all voiced lines from Sections 2 & 3 of voiceover.md
                (file IDs that start with "voice_"); keyed without the prefix.
  backgrounds — all background entries from art_info.json except bg_menu
                (the menu screen is rendered separately, not via the game asset loader).
  actors      — all actor entries from art_info.json.
  items       — all item entries from art_info.json.

Public API
----------
  generate_asset_config(voiceover_md: str, art_info: dict) -> dict
"""

import re

# bg_menu is the main-menu splash screen; it is loaded by the menu scene
# directly and does not participate in the in-game asset config.
_EXCLUDED_BACKGROUND_IDS: frozenset[str] = frozenset({"bg_poster"})
_EXCLUDED_BACKGROUND_NAMES: frozenset[str] = frozenset({"Game Poster"})

# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────


def _id_to_name(asset_id: str, prefix: str) -> str:
    """Strip *prefix* from *asset_id* and convert snake_case to Title Case.

    Examples
    --------
    >>> _id_to_name("bg_command_hub", "bg_")
    'Command Hub'
    >>> _id_to_name("bg_gameover_security_purge", "bg_")
    'Gameover Security Purge'
    >>> _id_to_name("actor_omega", "actor_")
    'Omega'
    >>> _id_to_name("item_red_emergency_lever", "item_")
    'Red Emergency Lever'
    """
    without_prefix = (
        asset_id[len(prefix) :] if asset_id.startswith(prefix) else asset_id
    )
    return " ".join(word.capitalize() for word in without_prefix.split("_"))


def _parse_dialogs(voiceover_md: str) -> dict:
    """Extract all (file_id, line) pairs where file_id starts with 'voice_'.

    Section 1 (VOICE REFERENCES) uses 'actor_*_ref' file IDs and is skipped.
    Sections 2 (CUTSCENES) and 3 (GAMEPLAY DIALOGUE) use 'dialog_*' file IDs
    and are included.

    Each dialog entry is stored as an array of line objects so the game engine
    can queue sequential lines.  The dict key is the bare file_id (e.g.
    'dialog_room1_entry') and each element carries 'text' and 'voice' where
    'voice' is '{file_id}_{index}.mp3' (matching voiceover_jobs output).
    """
    block_re = re.compile(
        r"\*\s*\*\*Actor:\*\*\s*(.*?)\n"
        r"\s*\*\s*\*\*Voice Desc:\*\*\s*(.*?)\n"
        r"\s*\*\s*\*\*File ID:\*\*\s*(\S+)\n"
        r"((?:\s*\*\s*\*\*Line(?:\s+\d+)?:\*\*\s*\"[^\"]*\"\n?)+)",
        re.IGNORECASE,
    )
    line_re = re.compile(r'\*\*Line(?:\s+\d+)?:\*\*\s*"([^"]+)"', re.IGNORECASE)

    dialogs: dict = {}
    for actor, _voice_desc, file_id, lines_block in block_re.findall(voiceover_md):
        if "_ref" in file_id.lower():
            continue  # skip reference recordings
        lines = line_re.findall(lines_block)
        if not lines:
            continue
        actor_clean = actor.strip()
        dialogs[file_id] = [
            {
                "actor": actor_clean,
                "text": line_text,
                "audio_file": f"{file_id}_{idx}.mp3",
            }
            for idx, line_text in enumerate(lines)
        ]
    return dialogs


def _parse_backgrounds(art_info: dict) -> dict:
    backgrounds: dict = {}
    for bg in art_info.get("backgrounds", []):
        bg_id = bg["id"]
        bg_name = bg["name"] if bg["name"] else _id_to_name(bg_id, "bg_")
        if bg_id in _EXCLUDED_BACKGROUND_IDS or bg_name in _EXCLUDED_BACKGROUND_NAMES:
            continue

        backgrounds[bg_id] = {"image": f"{bg_id}.png", "name": bg_name}
    return backgrounds


def _parse_actors(art_info: dict) -> dict:
    actors: dict = {}
    for actor in art_info.get("actors", []):
        actor_id = actor["id"]
        actors[actor_id] = {
            "image": f"{actor_id}_alpha.png",
            "name": actor["name"] if actor["name"] else _id_to_name(actor_id, "actor_"),
        }
    return actors


def _parse_items(art_info: dict) -> dict:
    items: dict = {}
    for item in art_info.get("items", []):
        item_id = item["id"]
        items[item_id] = {
            "image": f"{item_id}_alpha.png",
            "name": item["name"] if item["name"] else _id_to_name(item_id, "item_"),
        }
    return items


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def generate_asset_config(voiceover_md: str, art_info: dict) -> dict:
    """Build and return the assets_config structure.

    Parameters
    ----------
    voiceover_md:
        Raw text content of voiceover.md.
    art_info:
        Parsed dict from art_info.json.

    Returns
    -------
    dict with keys: dialogs, backgrounds, actors, items.
    """
    return {
        "dialogs": _parse_dialogs(voiceover_md),
        "backgrounds": _parse_backgrounds(art_info),
        "actors": _parse_actors(art_info),
        "items": _parse_items(art_info),
    }
