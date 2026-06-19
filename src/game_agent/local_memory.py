from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MEMORY_FILE = Path("player_memory.json")


class LocalPlayerMemory:
    """Small JSON-backed player profile store for the companion agent."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or MEMORY_FILE

    def _load_all(self) -> dict[str, dict[str, Any]]:
        """Read all player profiles from disk."""
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _save_all(self, data: dict[str, dict[str, Any]]) -> None:
        """Persist all player profiles atomically enough for local demo usage."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, user_id: str) -> dict[str, Any]:
        """Return a player's remembered profile."""
        return self._load_all().get(user_id, {})

    def update(self, user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        """Merge new profile fields into an existing player memory."""
        data = self._load_all()
        current = data.get(user_id, {})
        for key, value in profile.items():
            if value not in ("", None, [], {}):
                current[key] = value
        data[user_id] = current
        self._save_all(data)
        return current

    def append_note(self, user_id: str, note: str) -> dict[str, Any]:
        """Append a free-form preference or play note to the player's profile."""
        data = self._load_all()
        current = data.get(user_id, {})
        notes = current.get("notes", [])
        if not isinstance(notes, list):
            notes = []
        if note.strip():
            notes.append(note.strip())
        current["notes"] = notes[-20:]
        data[user_id] = current
        self._save_all(data)
        return current

    def list_all(self) -> dict[str, dict[str, Any]]:
        """Expose all local profiles for debugging and admin views."""
        return self._load_all()
