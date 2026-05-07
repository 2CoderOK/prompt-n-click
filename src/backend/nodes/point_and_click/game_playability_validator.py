"""
game_playability_validator.py

Verifies that a game_config can actually be completed by performing a symbolic
BFS over the game state graph.  No game engine is needed — we simulate clicks
by evaluating conditions and effects directly.

State space
-----------
  A state is a 3-tuple:
    room      : str
    inventory : frozenset[str]          — item IDs currently held
    flags     : frozenset[tuple]        — (flag_name, bool) pairs

Semantics
---------
  • For each clickable in the current room the **first** matching interaction
    fires (mirrors the Phaser game engine behaviour).
  • Timers can expire at any point once their start_conditions are satisfied
    and stop_conditions are not — the timeout_effects are treated as an
    additional edge in the state graph.
  • Game-over rooms are terminal (not explored further).
  • Victory rooms are terminal and mark the game as solvable.
  • reset_game_state effects are skipped (they live on game-over / victory
    restart buttons and are not part of normal play).

Public API
----------
  check_playability(config: dict) -> dict
    {
      "solvable":     bool,
      "winning_path": list[str],   # human-readable action sequence to victory
      "errors":       list[str],   # hard issues (broken refs, unsettable flags …)
      "warnings":     list[str],   # soft issues (dead ends, unreachable rooms …)
    }
"""

from __future__ import annotations

from collections import deque
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Room classification
# ──────────────────────────────────────────────────────────────────────────────

_GAMEOVER_PATTERNS = ("gameover", "game_over")
_VICTORY_PATTERNS = ("victory",)


def _is_gameover(room_id: str) -> bool:
    return any(p in room_id for p in _GAMEOVER_PATTERNS)


def _is_victory(room_id: str) -> bool:
    return any(p in room_id for p in _VICTORY_PATTERNS)


def _is_terminal(room_id: str) -> bool:
    return _is_gameover(room_id) or _is_victory(room_id)


# ──────────────────────────────────────────────────────────────────────────────
# Immutable game state
# ──────────────────────────────────────────────────────────────────────────────


class _State:
    __slots__ = ("room", "inventory", "flags")

    def __init__(self, room: str, inventory: frozenset, flags: frozenset) -> None:
        self.room = room
        self.inventory = inventory  # frozenset[str]
        self.flags = flags  # frozenset[tuple[str, bool]]

    # Hashable so it can live in a set / dict
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _State):
            return NotImplemented
        return (
            self.room == other.room
            and self.inventory == other.inventory
            and self.flags == other.flags
        )

    def __hash__(self) -> int:
        return hash((self.room, self.inventory, self.flags))

    def flags_dict(self) -> dict:
        return dict(self.flags)


# ──────────────────────────────────────────────────────────────────────────────
# Condition / effect helpers
# ──────────────────────────────────────────────────────────────────────────────


def _match(conditions: list, flags: dict) -> bool:
    """Return True when every condition in the list is satisfied."""
    return all(flags.get(c["flag"]) == c["is"] for c in conditions)


def _apply(interaction: dict, state: _State) -> tuple[_State, Optional[str]]:
    """
    Apply the effects of *interaction* to *state*.
    Returns (new_state, target_room_or_None).
    """
    flags = dict(state.flags)
    inventory = set(state.inventory)
    new_room: Optional[str] = None

    for eff in interaction.get("effects", []):
        if "set_flag" in eff:
            flags[eff["set_flag"]] = eff["value"]
        elif "move_item_to_inventory" in eff:
            inventory.add(eff["move_item_to_inventory"])
        elif "change_room" in eff:
            new_room = eff["change_room"]
        # reset_game_state → skip (terminal-room restart button, not reachable play)

    return (
        _State(
            room=new_room if new_room else state.room,
            inventory=frozenset(inventory),
            flags=frozenset(flags.items()),
        ),
        new_room,
    )


def _action_label(room_id: str, clickable: dict, interaction: dict) -> str:
    """Build a human-readable description of a BFS edge."""
    name = clickable.get("name") or clickable.get("id", "?")
    parts = [f"[{room_id}] click '{name}'"]
    for eff in interaction.get("effects", []):
        if "set_flag" in eff:
            parts.append(f"set {eff['set_flag']}={eff['value']}")
        elif "move_item_to_inventory" in eff:
            parts.append(f"pick up {eff['move_item_to_inventory']}")
        elif "change_room" in eff:
            parts.append(f"→ {eff['change_room']}")
    return " | ".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Structural pre-checks (before BFS)
# ──────────────────────────────────────────────────────────────────────────────


def _structural_checks(config: dict) -> tuple[list[str], list[str]]:
    """
    Fast static checks that do not require graph traversal.
    Returns (errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    rooms = config.get("rooms", {})
    initial = config.get("initial_state", {})
    initial_flags: dict = initial.get("flags", {})
    timers: list = config.get("timers", [])

    # ── 1. All change_room targets must exist ──────────────────────────────
    for rid, room in rooms.items():
        for clickable in room.get("clickables", []):
            for interaction in clickable.get("interactions", []):
                for eff in interaction.get("effects", []):
                    target = eff.get("change_room")
                    if target and target not in rooms:
                        errors.append(
                            f"Room '{rid}' → clickable '{clickable.get('id')}': "
                            f"change_room target '{target}' does not exist"
                        )

    for timer in timers:
        for eff in timer.get("timeout_effects", []):
            target = eff.get("change_room")
            if target and target not in rooms:
                errors.append(
                    f"Timer '{timer.get('id')}' timeout_effects: "
                    f"change_room target '{target}' does not exist"
                )

    # ── 2. Collect every value each flag can be SET to via any effect ──────
    settable: dict[str, set] = {}  # flag_name → set of values writable by effects
    for rid, room in rooms.items():
        for clickable in room.get("clickables", []):
            for interaction in clickable.get("interactions", []):
                for eff in interaction.get("effects", []):
                    if "set_flag" in eff:
                        settable.setdefault(eff["set_flag"], set()).add(eff["value"])

    # ── 3. Flags required by conditions but never set to the required value ─
    #       (if the initial value already satisfies the condition, skip it)
    for rid, room in rooms.items():
        for clickable in room.get("clickables", []):
            for interaction in clickable.get("interactions", []):
                for cond in interaction.get("conditions", []):
                    flag = cond["flag"]
                    required = cond["is"]
                    if flag not in initial_flags:
                        warnings.append(
                            f"Room '{rid}' → clickable '{clickable.get('id')}': "
                            f"condition uses undeclared flag '{flag}'"
                        )
                    elif initial_flags.get(
                        flag
                    ) != required and required not in settable.get(flag, set()):
                        errors.append(
                            f"Flag '{flag}' must equal '{required}' for clickable "
                            f"'{clickable.get('id')}' in room '{rid}', but no effect "
                            f"ever sets it to that value — condition can never be satisfied"
                        )

    # ── 4. Items in item_locations must be giveable from their room ─────────
    item_locations: dict = initial.get("item_locations", {})
    for item_id, room_id in item_locations.items():
        room = rooms.get(room_id)
        if not room:
            errors.append(
                f"item_locations: item '{item_id}' is placed in non-existent room '{room_id}'"
            )
            continue
        giveable = any(
            eff.get("move_item_to_inventory") == item_id
            for clickable in room.get("clickables", [])
            for interaction in clickable.get("interactions", [])
            for eff in interaction.get("effects", [])
        )
        if not giveable:
            errors.append(
                f"Item '{item_id}' is placed in '{room_id}' (item_locations) "
                f"but no clickable in that room has a move_item_to_inventory effect for it"
            )

    # ── 5. Rooms with no incoming change_room and not the start room ────────
    start_room = initial.get("current_room", "")
    reachable_targets: set[str] = {start_room}
    for rid, room in rooms.items():
        for clickable in room.get("clickables", []):
            for interaction in clickable.get("interactions", []):
                for eff in interaction.get("effects", []):
                    t = eff.get("change_room")
                    if t:
                        reachable_targets.add(t)
    for timer in timers:
        for eff in timer.get("timeout_effects", []):
            t = eff.get("change_room")
            if t:
                reachable_targets.add(t)

    for rid in rooms:
        if rid not in reachable_targets:
            warnings.append(
                f"Room '{rid}' is never the target of any change_room effect "
                f"(it may be unreachable)"
            )

    return errors, warnings


# ──────────────────────────────────────────────────────────────────────────────
# BFS
# ──────────────────────────────────────────────────────────────────────────────

_MAX_STATES = 50_000  # Safety cap; real games are far smaller


def _bfs(config: dict) -> tuple[bool, list[str], list[str], list[str]]:
    """
    Explore the state graph via BFS.
    Returns (solvable, winning_path, errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    rooms: dict = config.get("rooms", {})
    initial: dict = config.get("initial_state", {})
    timers: list = config.get("timers", [])

    start_room: str = initial.get("current_room", "menu_screen")
    start_flags: frozenset = frozenset(initial.get("flags", {}).items())
    start_inventory: frozenset = frozenset(initial.get("inventory", []))

    init_state = _State(start_room, start_inventory, start_flags)

    queue: deque[_State] = deque([init_state])
    visited: set[_State] = {init_state}
    # parent maps each state to (parent_state, action_label) for path reconstruction
    parent: dict[_State, Optional[tuple[_State, str]]] = {init_state: None}

    victory_state: Optional[_State] = None
    stuck_rooms: list[str] = []
    state_count = 0

    while queue:
        state = queue.popleft()
        state_count += 1

        if state_count > _MAX_STATES:
            warnings.append(
                f"BFS halted: explored {_MAX_STATES:,} states without reaching a conclusion. "
                "The state space may be too large or the game contains a loop. "
                "Analysis may be incomplete."
            )
            break

        # ── Terminal rooms ───────────────────────────────────────────────────
        if _is_victory(state.room):
            victory_state = state
            break  # Found the winning path — stop

        if _is_gameover(state.room):
            continue  # Dead end — don't explore further

        # ── Unknown room ─────────────────────────────────────────────────────
        room = rooms.get(state.room)
        if room is None:
            errors.append(f"BFS reached unknown room '{state.room}'")
            continue

        flags = state.flags_dict()
        progress_made = False

        # ── Clickable interactions (first matching per clickable) ─────────────
        for clickable in room.get("clickables", []):
            for interaction in clickable.get("interactions", []):
                if _match(interaction.get("conditions", []), flags):
                    new_state, _ = _apply(interaction, state)
                    label = _action_label(state.room, clickable, interaction)
                    if new_state not in visited:
                        visited.add(new_state)
                        parent[new_state] = (state, label)
                        queue.append(new_state)
                    if new_state != state:
                        progress_made = True
                    break  # First matching interaction only

        # ── Timer timeouts ────────────────────────────────────────────────────
        for timer in timers:
            start_conds: list = timer.get("start_conditions", [])
            stop_conds: list = timer.get("stop_conditions", [])
            timer_active = _match(start_conds, flags)
            timer_stopped = bool(stop_conds) and _match(stop_conds, flags)

            if timer_active and not timer_stopped:
                t_flags = dict(state.flags)
                t_inventory = set(state.inventory)
                t_room = state.room
                for eff in timer.get("timeout_effects", []):
                    if "set_flag" in eff:
                        t_flags[eff["set_flag"]] = eff["value"]
                    elif "change_room" in eff:
                        t_room = eff["change_room"]
                timeout_state = _State(
                    t_room, frozenset(t_inventory), frozenset(t_flags.items())
                )
                label = f"[TIMER TIMEOUT] {timer.get('id', '?')} → {t_room}"
                if timeout_state not in visited:
                    visited.add(timeout_state)
                    parent[timeout_state] = (state, label)
                    queue.append(timeout_state)

        # ── Dead-end detection ────────────────────────────────────────────────
        if not progress_made and not _is_terminal(state.room):
            stuck_rooms.append(state.room)

    # ── Reconstruct winning path ──────────────────────────────────────────────
    winning_path: list[str] = []
    if victory_state is not None:
        cur: Optional[_State] = victory_state
        while parent.get(cur) is not None:
            par, label = parent[cur]  # type: ignore[misc]
            winning_path.append(label)
            cur = par
        winning_path.reverse()

    if stuck_rooms:
        unique_stuck = sorted(set(stuck_rooms))
        warnings.append(
            f"Dead-end state(s) detected in room(s): {unique_stuck}. "
            "The player may become permanently stuck depending on action order."
        )

    return victory_state is not None, winning_path, errors, warnings


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def check_playability(config: dict) -> dict:
    """
    Validate that the game can be completed.

    Runs structural pre-checks then a BFS over the full state graph.

    Args:
        config: Parsed game_config dict.

    Returns:
        {
            "solvable":     bool        — True if a path to victory was found.
            "winning_path": list[str]   — Ordered list of actions leading to victory.
            "errors":       list[str]   — Hard errors: broken refs, unsatisfiable
                                          conditions, items never obtainable, etc.
            "warnings":     list[str]   — Soft issues: dead ends, unreachable rooms.
        }
    """
    errors: list[str] = []
    warnings: list[str] = []

    struct_errors, struct_warnings = _structural_checks(config)
    errors.extend(struct_errors)
    warnings.extend(struct_warnings)

    solvable, winning_path, bfs_errors, bfs_warnings = _bfs(config)
    errors.extend(bfs_errors)
    warnings.extend(bfs_warnings)

    if not solvable:
        errors.append(
            "Game is NOT solvable: BFS found no path from the start room "
            "to any victory room — check flag logic, missing effects, and "
            "item/door dependencies"
        )

    return {
        "solvable": solvable,
        "winning_path": winning_path,
        "errors": errors,
        "warnings": warnings,
    }
