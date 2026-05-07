from shared.constants import GAME_TYPE_POINT_AND_CLICK
from nodes.point_and_click.asset_config_generator import (
    generate_asset_config as _pac_generate_asset_config,
)

_REGISTRY: dict[str, dict] = {
    GAME_TYPE_POINT_AND_CLICK: {
        "generate_asset_config": _pac_generate_asset_config,
    },
    # GAME_TYPE_HIDDEN_OBJECTS: {
    #     "generate_asset_config": _ho_generate_asset_config,
    # },
}


def _get_entry(game_type: str) -> dict:
    entry = _REGISTRY.get(game_type)
    if entry is None:
        supported = ", ".join(_REGISTRY.keys())
        raise ValueError(
            f"Unsupported game type: {game_type!r}. Supported: {supported}"
        )
    return entry


def get_game_type_validators(game_type: str):
    """Return (build_checklist, validate_config) for the given game type."""
    entry = _get_entry(game_type)
    return entry["build_checklist"], entry["validate_config"]


def get_asset_config_generator(game_type: str):
    """Return generate_asset_config(voiceover_md, art_info) -> dict for the given game type."""
    return _get_entry(game_type)["generate_asset_config"]
