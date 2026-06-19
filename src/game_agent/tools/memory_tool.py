from __future__ import annotations

from typing import Any, Optional

from src.game_agent.local_memory import LocalPlayerMemory


def read_player_memory(user_id: str) -> dict[str, Any]:
    """Read remembered player preferences for prompt injection and UI display."""
    return LocalPlayerMemory().get(user_id)


def save_player_memory(user_id: str, profile: Optional[dict[str, Any]] = None, note: str = "") -> dict[str, Any]:
    """Save structured profile fields and optional free-form notes."""
    store = LocalPlayerMemory()
    saved = store.update(user_id, profile or {})
    if note:
        saved = store.append_note(user_id, note)
    return saved


def memory_tool(user_id: str, action: str = "read", profile: Optional[dict[str, Any]] = None, note: str = "") -> dict[str, Any]:
    """Tool entrypoint for reading or writing local player memory."""
    if action == "write":
        memory = save_player_memory(user_id=user_id, profile=profile, note=note)
    else:
        memory = read_player_memory(user_id=user_id)
    return {"tool": "memory_tool", "action": action, "user_id": user_id, "memory": memory}
